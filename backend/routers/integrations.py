from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models.user import User
from backend.services.integration_sync import (
    dispatch_sync_tasks,
    list_integration_settings,
    normalize_provider,
    plan_manual_action_sync,
    process_inbound_event,
    upsert_integration_setting,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


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
    return IntegrationSettingsItemResponse(
        provider=setting.provider,
        enabled=bool(setting.enabled),
        outbound_enabled=bool(setting.outbound_enabled),
        inbound_enabled=bool(setting.inbound_enabled),
        auto_create=bool(setting.auto_create),
        reopen_on_regression=bool(setting.reopen_on_regression),
        config=setting.config_json if isinstance(setting.config_json, dict) else {},
        secret_configured=bool(setting.secret_json),
        webhook_configured=bool((setting.secret_json or {}).get("webhook_token")),
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
    response: Response,
    body: Annotated[dict[str, Any], Body(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
    webhook_token: Annotated[str | None, Header(alias="X-Integration-Webhook-Token")] = None,
    external_event_id: Annotated[str | None, Header(alias="X-External-Event-Id")] = None,
) -> IntegrationWebhookResponse:
    try:
        normalized_provider = normalize_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    token = str(webhook_token or "").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing integration webhook token.")
    try:
        result = await db.run_sync(
            lambda session: process_inbound_event(
                session,
                provider=normalized_provider,
                webhook_token=token,
                event=body,
                event_id=external_event_id,
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
