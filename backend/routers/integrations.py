from __future__ import annotations

import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models.tenant_integration_setting import TenantIntegrationSetting
from backend.models.user import User
from backend.services.integration_sync import (
    dispatch_sync_tasks,
    list_integration_settings,
    normalize_provider,
    plan_manual_action_sync,
    process_inbound_event,
    resolve_jira_setting_for_signature,
    upsert_integration_setting,
)
from backend.services.jira_admin import JiraAdminError, sync_jira_webhook, validate_jira_configuration

router = APIRouter(prefix="/integrations", tags=["integrations"])


class IntegrationHealthResponse(BaseModel):
    status: str
    credentials_valid: bool | None = None
    project_valid: bool | None = None
    issue_type_valid: bool | None = None
    transition_map_valid: bool | None = None
    webhook_registered: bool | None = None
    signed_webhook_enabled: bool | None = None
    webhook_mode: str | None = None
    last_validated_at: str | None = None
    last_validation_error: str | None = None
    last_inbound_at: str | None = None
    last_outbound_at: str | None = None
    last_provider_error: str | None = None
    last_provider_error_at: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class IntegrationSettingsItemResponse(BaseModel):
    provider: str
    enabled: bool
    outbound_enabled: bool
    inbound_enabled: bool
    auto_create: bool
    reopen_on_regression: bool
    config: dict[str, Any] = Field(default_factory=dict)
    secret_configured: bool
    webhook_configured: bool
    health: IntegrationHealthResponse | None = None


class IntegrationSettingsListResponse(BaseModel):
    items: list[IntegrationSettingsItemResponse]


class IntegrationSettingsUpdateRequest(BaseModel):
    enabled: bool | None = None
    outbound_enabled: bool | None = None
    inbound_enabled: bool | None = None
    auto_create: bool | None = None
    reopen_on_regression: bool | None = None
    config: dict[str, Any] | None = None
    secret_config: dict[str, Any] | None = None
    clear_secret_config: bool = False


class TriggerIntegrationSyncRequest(BaseModel):
    provider: str = Field(..., description="Provider identifier: jira, servicenow, or slack.")


class TriggerIntegrationSyncResponse(BaseModel):
    provider: str
    task_ids: list[str] = Field(default_factory=list)
    queued: int
    failed_to_enqueue: int


class IntegrationWebhookResponse(BaseModel):
    provider: str
    replayed: bool
    applied: bool
    action_id: str | None = None
    action_status: str | None = None
    owner_key: str | None = None
    receipt_status: str


class JiraCanarySyncRequest(BaseModel):
    action_id: str | None = None


class JiraUtilityResponse(BaseModel):
    provider: str
    message: str
    item: IntegrationSettingsItemResponse
    task_ids: list[str] = Field(default_factory=list)
    queued: int = 0
    failed_to_enqueue: int = 0


def _require_admin(user: User) -> None:
    if getattr(user.role, "value", user.role) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can manage integrations.")


@router.get("/settings", response_model=IntegrationSettingsListResponse)
async def get_integration_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IntegrationSettingsListResponse:
    items = await db.run_sync(lambda session: list_integration_settings(session, current_user.tenant_id))
    return IntegrationSettingsListResponse(items=[IntegrationSettingsItemResponse(**item.__dict__) for item in items])


@router.patch("/settings/{provider}", response_model=IntegrationSettingsItemResponse)
async def patch_integration_settings(
    provider: Annotated[str, Path(description="Integration provider.")],
    request: IntegrationSettingsUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IntegrationSettingsItemResponse:
    _require_admin(current_user)
    try:
        normalized_provider = normalize_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except JiraAdminError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    setting = await db.run_sync(
        lambda session: upsert_integration_setting(
            session,
            tenant_id=current_user.tenant_id,
            provider=normalized_provider,
            enabled=request.enabled,
            outbound_enabled=request.outbound_enabled,
            inbound_enabled=request.inbound_enabled,
            auto_create=request.auto_create,
            reopen_on_regression=request.reopen_on_regression,
            config=request.config,
            secret_config=request.secret_config,
            clear_secret_config=request.clear_secret_config,
        )
    )
    await db.commit()
    return await _integration_setting_item(
        db,
        tenant_id=current_user.tenant_id,
        provider=normalized_provider,
    )


@router.post("/actions/{action_id}/sync", response_model=TriggerIntegrationSyncResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_action_sync(
    action_id: Annotated[str, Path(description="Action UUID")],
    request: TriggerIntegrationSyncRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TriggerIntegrationSyncResponse:
    _require_admin(current_user)
    try:
        action_uuid = uuid.UUID(action_id)
        normalized_provider = normalize_provider(request.provider)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        task_ids = await db.run_sync(
            lambda session: plan_manual_action_sync(
                session,
                tenant_id=current_user.tenant_id,
                action_id=action_uuid,
                provider=normalized_provider,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    dispatch = dispatch_sync_tasks(task_ids, tenant_id=current_user.tenant_id)
    return TriggerIntegrationSyncResponse(
        provider=normalized_provider,
        task_ids=[str(task_id) for task_id in task_ids],
        queued=int(dispatch["enqueued"]),
        failed_to_enqueue=int(dispatch["failed"]),
    )


@router.post("/webhooks/{provider}", response_model=IntegrationWebhookResponse)
async def ingest_integration_webhook(
    provider: Annotated[str, Path(description="Integration provider.")],
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    webhook_token: Annotated[str | None, Header(alias="X-Integration-Webhook-Token")] = None,
    external_event_id: Annotated[str | None, Header(alias="X-External-Event-Id")] = None,
    hub_signature: Annotated[str | None, Header(alias="X-Hub-Signature")] = None,
) -> IntegrationWebhookResponse:
    try:
        normalized_provider = normalize_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    raw_body = await request.body()
    body = _parse_json_body(raw_body)
    resolved_setting = None
    token = str(webhook_token or "").strip()
    if normalized_provider == "jira":
        resolved_setting = await db.run_sync(
            lambda session: resolve_jira_setting_for_signature(session, body=raw_body, signature_header=hub_signature)
        )
    if resolved_setting is None and not token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing integration webhook authentication.")
    try:
        result = await db.run_sync(
            lambda session: process_inbound_event(
                session,
                provider=normalized_provider,
                webhook_token=token,
                event=body,
                event_id=external_event_id,
                setting=resolved_setting,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    await db.commit()
    response.status_code = status.HTTP_200_OK
    return IntegrationWebhookResponse(
        provider=result.provider,
        replayed=result.replayed,
        applied=result.applied,
        action_id=str(result.action_id) if result.action_id else None,
        action_status=result.action_status,
        owner_key=result.owner_key,
        receipt_status=result.receipt_status,
    )


@router.post("/settings/jira/validate", response_model=JiraUtilityResponse)
async def validate_jira_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JiraUtilityResponse:
    _require_admin(current_user)
    item = await _run_jira_admin_action(
        db,
        tenant_id=current_user.tenant_id,
        action=lambda session, setting: validate_jira_configuration(setting),
    )
    return JiraUtilityResponse(provider="jira", message="Jira validation completed.", item=item)


@router.post("/settings/jira/webhook/sync", response_model=JiraUtilityResponse)
async def sync_jira_settings_webhook(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[dict[str, Any], Body(default_factory=dict)],
) -> JiraUtilityResponse:
    _require_admin(current_user)
    rotate_secret = bool(body.get("rotate_secret"))
    result, item = await _run_jira_admin_action(
        db,
        tenant_id=current_user.tenant_id,
        action=lambda session, setting: sync_jira_webhook(setting, rotate_secret=rotate_secret),
        return_result=True,
    )
    message = "Jira webhook synced." if not rotate_secret else "Jira webhook synced and secret rotated."
    return JiraUtilityResponse(provider="jira", message=message, item=item, task_ids=[], queued=0, failed_to_enqueue=0)


@router.post("/settings/jira/canary-sync", response_model=JiraUtilityResponse)
async def run_jira_canary_sync(
    request: JiraCanarySyncRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JiraUtilityResponse:
    _require_admin(current_user)
    item = await _integration_setting_item(db, tenant_id=current_user.tenant_id, provider="jira")
    config = item.config
    action_id = str(request.action_id or config.get("canary_action_id") or "").strip()
    if not action_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Set a Jira canary action ID before running canary sync.")
    try:
        action_uuid = uuid.UUID(action_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Jira canary action ID must be a valid UUID.") from exc
    task_ids = await db.run_sync(
        lambda session: plan_manual_action_sync(
            session,
            tenant_id=current_user.tenant_id,
            action_id=action_uuid,
            provider="jira",
        )
    )
    await db.commit()
    dispatch = dispatch_sync_tasks(task_ids, tenant_id=current_user.tenant_id)
    item = await _integration_setting_item(db, tenant_id=current_user.tenant_id, provider="jira")
    return JiraUtilityResponse(
        provider="jira",
        message="Jira canary sync queued.",
        item=item,
        task_ids=[str(task_id) for task_id in task_ids],
        queued=int(dispatch["enqueued"]),
        failed_to_enqueue=int(dispatch["failed"]),
    )


def _parse_json_body(raw_body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook body must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook body must be a JSON object.")
    return payload


async def _run_jira_admin_action(
    db: AsyncSession,
    *,
    tenant_id,
    action,
    return_result: bool = False,
):
    try:
        result = await db.run_sync(lambda session: action(session, _require_jira_setting(session, tenant_id=tenant_id)))
    except JiraAdminError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    item = await _integration_setting_item(db, tenant_id=tenant_id, provider="jira")
    if return_result:
        return result, item
    return item


def _require_jira_setting(session, *, tenant_id):
    setting = session.execute(
        select(TenantIntegrationSetting).where(
            TenantIntegrationSetting.tenant_id == tenant_id,
            TenantIntegrationSetting.provider == "jira",
        )
    ).scalar_one_or_none()
    if setting is None:
        raise JiraAdminError("jira_not_configured", "Jira settings have not been saved for this tenant.")
    return setting


async def _integration_setting_item(
    db: AsyncSession,
    *,
    tenant_id,
    provider: str,
) -> IntegrationSettingsItemResponse:
    items = await db.run_sync(lambda session: list_integration_settings(session, tenant_id))
    for item in items:
        if item.provider == provider:
            return IntegrationSettingsItemResponse(**item.__dict__)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{provider.title()} settings not found.",
    )
