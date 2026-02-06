"""
Actions API: compute trigger (Step 5.4), list/detail/PATCH (Step 5.5), remediation-preview (Step 8.4).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.action import Action
from backend.models.action_finding import ActionFinding
from backend.models.aws_account import AwsAccount
from backend.models.user import User
from backend.routers.aws_accounts import get_account_for_tenant, get_tenant, resolve_tenant_id
from backend.services.aws import assume_role
from backend.services.exception_service import get_exception_state_for_response
from backend.utils.sqs import build_compute_actions_job_payload, parse_queue_region

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actions", tags=["actions"])


# ---------------------------------------------------------------------------
# POST /actions/compute (Step 5.4)
# ---------------------------------------------------------------------------

class ComputeActionsRequest(BaseModel):
    """Optional scope for action computation."""

    account_id: Optional[str] = Field(default=None, description="AWS account ID (12 digits). Omit for tenant-wide.")
    region: Optional[str] = Field(default=None, description="AWS region. Requires account_id if set.")


class ComputeActionsResponse(BaseModel):
    """Response for successful compute trigger (202 Accepted)."""

    message: str = "Action computation job queued"
    tenant_id: str = Field(..., description="Tenant UUID")
    scope: dict = Field(default_factory=dict, description="Scope used: account_id and/or region if provided")


# ---------------------------------------------------------------------------
# GET /actions, GET /actions/{id}, PATCH /actions/{id} (Step 5.5)
# ---------------------------------------------------------------------------

class ActionListItem(BaseModel):
    """Single action in list response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    action_type: str
    target_id: str
    account_id: str
    region: str | None
    priority: int
    status: str
    title: str
    control_id: str | None
    resource_id: str | None
    updated_at: str | None
    finding_count: int
    # Step 6.3: exception state (on-read expiry)
    exception_id: str | None = None
    exception_expires_at: str | None = None
    exception_expired: bool | None = None


class ActionsListResponse(BaseModel):
    """Paginated list of actions."""

    items: list[ActionListItem]
    total: int


class ActionDetailFinding(BaseModel):
    """Finding summary in action detail."""

    id: str
    finding_id: str
    severity_label: str
    title: str
    resource_id: str | None
    account_id: str
    region: str
    updated_at: str | None


class ActionDetailResponse(BaseModel):
    """Full action with linked findings."""

    id: str
    tenant_id: str
    action_type: str
    target_id: str
    account_id: str
    region: str | None
    priority: int
    status: str
    title: str
    description: str | None
    control_id: str | None
    resource_id: str | None
    resource_type: str | None
    created_at: str | None
    updated_at: str | None
    findings: list[ActionDetailFinding]
    # Step 6.3: exception state (on-read expiry)
    exception_id: str | None = None
    exception_expires_at: str | None = None
    exception_expired: bool | None = None


class PatchActionRequest(BaseModel):
    """Request body for PATCH /actions/{id}."""

    status: Literal["in_progress", "resolved", "suppressed"] = Field(..., description="New workflow status")


class RemediationPreviewResponse(BaseModel):
    """Response for GET /actions/{id}/remediation-preview (Step 8.4 dry-run)."""

    compliant: bool = Field(..., description="True if already compliant; no fix needed")
    message: str = Field(..., description="Human-readable pre-check result")
    will_apply: bool = Field(..., description="True if not compliant and fix would be applied")


def _action_to_list_item(
    action: Action,
    exception_state: dict | None = None,
) -> ActionListItem:
    """Build list item from Action; action_finding_links must be loaded."""
    state = exception_state or {}
    return ActionListItem(
        id=str(action.id),
        action_type=action.action_type,
        target_id=action.target_id,
        account_id=action.account_id,
        region=action.region,
        priority=action.priority,
        status=action.status,
        title=action.title,
        control_id=action.control_id,
        resource_id=action.resource_id,
        updated_at=action.updated_at.isoformat() if action.updated_at else None,
        finding_count=len(action.action_finding_links or []),
        exception_id=state.get("exception_id"),
        exception_expires_at=state.get("exception_expires_at"),
        exception_expired=state.get("exception_expired"),
    )


def _action_to_detail_response(
    action: Action,
    exception_state: dict | None = None,
) -> ActionDetailResponse:
    """Build detail response from Action; action_finding_links and finding must be loaded."""
    state = exception_state or {}
    findings = []
    for link in action.action_finding_links or []:
        f = link.finding
        if f is None:
            continue
        findings.append(
            ActionDetailFinding(
                id=str(f.id),
                finding_id=f.finding_id,
                severity_label=f.severity_label,
                title=f.title,
                resource_id=f.resource_id,
                account_id=f.account_id,
                region=f.region,
                updated_at=f.updated_at.isoformat() if f.updated_at else None,
            )
        )
    return ActionDetailResponse(
        id=str(action.id),
        tenant_id=str(action.tenant_id),
        action_type=action.action_type,
        target_id=action.target_id,
        account_id=action.account_id,
        region=action.region,
        priority=action.priority,
        status=action.status,
        title=action.title,
        description=action.description,
        control_id=action.control_id,
        resource_id=action.resource_id,
        resource_type=action.resource_type,
        created_at=action.created_at.isoformat() if action.created_at else None,
        updated_at=action.updated_at.isoformat() if action.updated_at else None,
        findings=findings,
        exception_id=state.get("exception_id"),
        exception_expires_at=state.get("exception_expires_at"),
        exception_expired=state.get("exception_expired"),
    )


@router.get("", response_model=ActionsListResponse)
async def list_actions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    account_id: Annotated[str | None, Query(description="Filter by AWS account ID")] = None,
    region: Annotated[str | None, Query(description="Filter by AWS region")] = None,
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="Filter by status (open, in_progress, resolved, suppressed)"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Max items per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
) -> ActionsListResponse:
    """
    List actions with optional filters and pagination.
    Returns actions scoped to the tenant; each item includes finding_count.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    query = (
        select(Action)
        .where(Action.tenant_id == tenant_uuid)
        .options(selectinload(Action.action_finding_links))
    )
    if account_id is not None:
        query = query.where(Action.account_id == account_id)
    if region is not None:
        query = query.where(Action.region == region)
    if status_filter is not None:
        query = query.where(Action.status == status_filter.strip().lower())

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Action.priority.desc(), Action.updated_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    actions = result.scalars().unique().all()

    items = []
    for a in actions:
        exception_state = await get_exception_state_for_response(
            db, tenant_uuid, "action", a.id
        )
        items.append(_action_to_list_item(a, exception_state))
    logger.info("Listed %d actions for tenant %s (total=%d)", len(items), tenant_uuid, total)
    return ActionsListResponse(items=items, total=total)


@router.get("/{action_id}", response_model=ActionDetailResponse)
async def get_action(
    action_id: Annotated[str, Path(description="Action UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> ActionDetailResponse:
    """
    Get a single action by ID with linked findings.
    Tenant-scoped; 404 if not found.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    try:
        action_uuid = uuid.UUID(action_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid action_id", "detail": "action_id must be a valid UUID"},
        )

    result = await db.execute(
        select(Action)
        .where(Action.id == action_uuid, Action.tenant_id == tenant_uuid)
        .options(
            selectinload(Action.action_finding_links).selectinload(ActionFinding.finding),
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Action not found", "detail": f"No action found with ID {action_id}"},
        )

    exception_state = await get_exception_state_for_response(
        db, tenant_uuid, "action", action.id
    )
    return _action_to_detail_response(action, exception_state)


# ---------------------------------------------------------------------------
# GET /actions/{id}/remediation-preview (Step 8.4 dry-run)
# ---------------------------------------------------------------------------

@router.get(
    "/{action_id}/remediation-preview",
    response_model=RemediationPreviewResponse,
    summary="Remediation preview (dry-run)",
    description="Run pre-check only for direct fix. Returns compliant, message, will_apply. Requires WriteRole.",
    responses={
        400: {"description": "Action not fixable or WriteRole not configured"},
        404: {"description": "Action not found"},
    },
)
async def get_remediation_preview(
    action_id: Annotated[str, Path(description="Action UUID")],
    mode: Annotated[
        Literal["direct_fix"],
        Query(description="Remediation mode; only direct_fix supported for preview"),
    ] = "direct_fix",
    db: Annotated[AsyncSession, Depends(get_db)] = ...,
    current_user: Annotated[Optional[User], Depends(get_optional_user)] = ...,
    tenant_id: Annotated[Optional[str], Query(description="Tenant ID. Optional when authenticated.")] = None,
) -> RemediationPreviewResponse:
    """
    Pre-check only (dry-run) for direct fix. Shows current state before user approves.
    Requires action to be fixable and account to have WriteRole.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    try:
        action_uuid = uuid.UUID(action_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid action_id", "detail": "action_id must be a valid UUID"},
        )

    result = await db.execute(
        select(Action).where(Action.id == action_uuid, Action.tenant_id == tenant_uuid)
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Action not found", "detail": f"No action found with ID {action_id}"},
        )

    from worker.services.direct_fix import SUPPORTED_ACTION_TYPES, run_remediation_preview

    if action.action_type not in SUPPORTED_ACTION_TYPES:
        return RemediationPreviewResponse(
            compliant=False,
            message=f"Action type '{action.action_type}' does not support direct fix.",
            will_apply=False,
        )

    acc_result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_uuid,
            AwsAccount.account_id == action.account_id,
        )
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        return RemediationPreviewResponse(
            compliant=False,
            message="AWS account not found for this action.",
            will_apply=False,
        )
    if not account.role_write_arn:
        return RemediationPreviewResponse(
            compliant=False,
            message="WriteRole not configured. Add WriteRole in account settings.",
            will_apply=False,
        )

    try:
        wr_session = await asyncio.to_thread(
            assume_role,
            role_arn=account.role_write_arn,
            external_id=account.external_id,
        )
        preview = await asyncio.to_thread(
            run_remediation_preview,
            wr_session,
            action.action_type,
            action.account_id,
            action.region,
        )
        return RemediationPreviewResponse(
            compliant=preview.compliant,
            message=preview.message,
            will_apply=preview.will_apply,
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        return RemediationPreviewResponse(
            compliant=False,
            message=f"Could not assume WriteRole: {code}",
            will_apply=False,
        )
    except Exception as e:
        logger.exception("Remediation preview failed for action %s: %s", action_id, e)
        return RemediationPreviewResponse(
            compliant=False,
            message=f"Preview failed: {e}",
            will_apply=False,
        )


@router.patch("/{action_id}", response_model=ActionDetailResponse)
async def patch_action(
    action_id: Annotated[str, Path(description="Action UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    body: PatchActionRequest = Body(...),
) -> ActionDetailResponse:
    """
    Update action status (in_progress, resolved, suppressed).
    Returns the updated action with linked findings.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    try:
        action_uuid = uuid.UUID(action_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid action_id", "detail": "action_id must be a valid UUID"},
        )

    result = await db.execute(
        select(Action)
        .where(Action.id == action_uuid, Action.tenant_id == tenant_uuid)
        .options(
            selectinload(Action.action_finding_links).selectinload(ActionFinding.finding),
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Action not found", "detail": f"No action found with ID {action_id}"},
        )

    action.status = body.status
    await db.commit()

    # Re-query with relationships so response has findings
    result2 = await db.execute(
        select(Action)
        .where(Action.id == action_uuid, Action.tenant_id == tenant_uuid)
        .options(
            selectinload(Action.action_finding_links).selectinload(ActionFinding.finding),
        )
    )
    action = result2.scalar_one_or_none()
    exception_state = await get_exception_state_for_response(
        db, tenant_uuid, "action", action.id
    )
    return _action_to_detail_response(action, exception_state)


# ---------------------------------------------------------------------------
# POST /actions/compute (Step 5.4)
# ---------------------------------------------------------------------------

@router.post(
    "/compute",
    response_model=ComputeActionsResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger action computation",
    description="Enqueue a compute_actions job for the current tenant. Omit body for tenant-wide; optionally scope by account_id and/or region.",
    responses={
        404: {"description": "Tenant or account not found"},
        400: {"description": "Invalid scope (e.g. region without account_id, or account/region not in tenant)"},
        503: {"description": "Queue unavailable or SQS send failed"},
    },
)
async def trigger_compute_actions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    body: Optional[ComputeActionsRequest] = Body(default=None),
) -> ComputeActionsResponse:
    """
    Enqueue one compute_actions job. Resolves tenant from JWT or tenant_id query.
    Optional body: account_id and/or region to scope computation.
    """
    if not settings.has_ingest_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Action computation unavailable",
                "detail": "Queue URL not configured. Set SQS_INGEST_QUEUE_URL.",
            },
        )

    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    account_id: Optional[str] = None
    region: Optional[str] = None
    scope: dict = {}

    if body:
        if body.region is not None and body.account_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Bad request",
                    "detail": "region requires account_id. Omit region or provide account_id.",
                },
            )
        account_id = body.account_id
        region = body.region
        if account_id is not None:
            scope["account_id"] = account_id
            acc = await get_account_for_tenant(tenant_uuid, account_id, db)
            if not acc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "Account not found",
                        "detail": "No AWS account found with the given ID for this tenant.",
                    },
                )
            if region is not None:
                scope["region"] = region
                allowed = set(acc.regions or [])
                if region not in allowed:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error": "Bad request",
                            "detail": "region must be one of the account's configured regions.",
                        },
                    )

    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    now = datetime.now(timezone.utc).isoformat()
    payload = build_compute_actions_job_payload(tenant_uuid, now, account_id=account_id, region=region)

    try:
        resp = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
        _ = resp["MessageId"]
    except ClientError as e:
        logger.exception("SQS send_message failed for compute_actions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Action computation unavailable",
                "detail": "Could not enqueue job. Please try again later.",
            },
        ) from e

    return ComputeActionsResponse(
        message="Action computation job queued",
        tenant_id=str(tenant_uuid),
        scope=scope,
    )
