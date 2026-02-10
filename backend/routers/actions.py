"""
Actions API: compute trigger (Step 5.4), list/detail/PATCH (Step 5.5), remediation-preview (Step 8.4).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Optional

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
from backend.services.remediation_risk import evaluate_strategy_impact
from backend.services.remediation_strategy import (
    list_mode_options_for_action_type,
    list_strategies_for_action_type,
    validate_strategy,
)
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
    # Optional execution-group fields (group_by=batch)
    is_batch: bool = False
    batch_action_count: int | None = None
    batch_finding_count: int | None = None


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


class DependencyCheckResponse(BaseModel):
    """One dependency check entry for remediation strategy safety."""

    code: str
    status: Literal["pass", "warn", "unknown", "fail"]
    message: str


class RemediationOptionResponse(BaseModel):
    """One remediation strategy option for an action."""

    strategy_id: str
    label: str
    mode: Literal["pr_only", "direct_fix"]
    risk_level: Literal["low", "medium", "high"]
    recommended: bool
    requires_inputs: bool
    input_schema: dict[str, Any]
    dependency_checks: list[DependencyCheckResponse]
    warnings: list[str]
    supports_exception_flow: bool


class RemediationOptionsResponse(BaseModel):
    """Available remediation options for an action, including risk signals."""

    action_id: str
    action_type: str
    mode_options: list[Literal["pr_only", "direct_fix"]]
    strategies: list[RemediationOptionResponse]


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


_BATCH_TITLE_BY_ACTION_TYPE = {
    "s3_block_public_access": "S3 account public access hardening",
    "enable_security_hub": "Enable Security Hub",
    "enable_guardduty": "Enable GuardDuty",
    "s3_bucket_block_public_access": "Enforce S3 bucket public access hardening",
    "s3_bucket_encryption": "Enforce S3 bucket encryption",
    "s3_bucket_access_logging": "Enable S3 bucket access logging",
    "s3_bucket_lifecycle_configuration": "Configure S3 bucket lifecycle",
    "s3_bucket_encryption_kms": "Enforce S3 bucket SSE-KMS encryption",
    "sg_restrict_public_ports": "Restrict security-group public ports",
    "cloudtrail_enabled": "Enable CloudTrail",
    "aws_config_enabled": "Enable AWS Config recording",
    "ssm_block_public_sharing": "Block public SSM document sharing",
    "ebs_snapshot_block_public_access": "Restrict EBS snapshot public sharing",
    "ebs_default_encryption": "Enable EBS default encryption",
    "s3_bucket_require_ssl": "Enforce SSL-only S3 access",
    "iam_root_access_key_absent": "Remove IAM root access keys",
}


_MIN_UPDATED_AT = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _batch_title(action_type: str, action_count: int) -> str:
    base = _BATCH_TITLE_BY_ACTION_TYPE.get(action_type, f"{action_type}")
    return f"{base} ({action_count} action{'s' if action_count != 1 else ''})"


def _build_batch_target_id(action: Action) -> str:
    region = action.region or "global"
    return f"batch|{action.action_type}|{action.account_id}|{region}|{action.status}"


def _batch_sort_key(item: ActionListItem) -> tuple[int, str]:
    return (
        item.priority,
        item.updated_at or "",
    )


def _normalize_updated_at(value: datetime | None) -> datetime:
    if value is None:
        return _MIN_UPDATED_AT
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _group_actions_into_batches(actions: list[Action]) -> list[ActionListItem]:
    """
    Build execution-group list items from individual actions.

    Grouping key: (action_type, account_id, region, status).
    """
    grouped: defaultdict[tuple[str, str, str | None, str], list[Action]] = defaultdict(list)
    for action in actions:
        grouped[(action.action_type, action.account_id, action.region, action.status)].append(action)

    items: list[ActionListItem] = []
    for key, group in grouped.items():
        action_type, account_id, region, status = key
        representative = max(group, key=lambda a: (a.priority, _normalize_updated_at(a.updated_at)))
        max_priority = max(a.priority for a in group)
        max_updated_at = max((_normalize_updated_at(a.updated_at) for a in group), default=None)
        total_findings = sum(len(a.action_finding_links or []) for a in group)
        action_count = len(group)

        # Skip orphan groups (no linked findings). These typically occur when a
        # recompute remaps findings away from older actions; they should not
        # appear as execution groups in the UI.
        if total_findings == 0:
            continue

        items.append(
            ActionListItem(
                id=str(representative.id),
                action_type=action_type,
                target_id=_build_batch_target_id(representative),
                account_id=account_id,
                region=region,
                priority=max_priority,
                status=status,
                title=_batch_title(action_type, action_count),
                control_id=representative.control_id,
                resource_id=None,
                updated_at=max_updated_at.isoformat() if max_updated_at else None,
                finding_count=total_findings,
                is_batch=True,
                batch_action_count=action_count,
                batch_finding_count=total_findings,
            )
        )

    items.sort(key=_batch_sort_key, reverse=True)
    return items


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
    control_id: Annotated[str | None, Query(description="Filter by control ID (e.g., S3.1)")] = None,
    resource_id: Annotated[str | None, Query(description="Filter by resource ID")] = None,
    action_type: Annotated[str | None, Query(description="Filter by remediation action type")] = None,
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="Filter by status (open, in_progress, resolved, suppressed)"),
    ] = None,
    group_by: Annotated[
        Literal["resource", "batch"],
        Query(description="List mode: 'resource' for individual actions, 'batch' for execution groups."),
    ] = "resource",
    include_orphans: Annotated[
        bool,
        Query(description="Include actions with zero linked findings. Defaults to false."),
    ] = False,
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
    if control_id is not None:
        query = query.where(Action.control_id == control_id.strip())
    if resource_id is not None:
        query = query.where(Action.resource_id == resource_id.strip())
    if action_type is not None:
        query = query.where(Action.action_type == action_type.strip())
    if status_filter is not None:
        query = query.where(Action.status == status_filter.strip().lower())
    if not include_orphans:
        query = query.where(
            select(ActionFinding.action_id)
            .where(ActionFinding.action_id == Action.id)
            .exists()
        )

    if group_by == "batch":
        result = await db.execute(query)
        actions = result.scalars().unique().all()
        batch_items = _group_actions_into_batches(actions)
        total = len(batch_items)
        paged_items = batch_items[offset: offset + limit]
        logger.info(
            "Listed %d batch action groups for tenant %s (total=%d)",
            len(paged_items),
            tenant_uuid,
            total,
        )
        return ActionsListResponse(items=paged_items, total=total)

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
# GET /actions/{id}/remediation-options
# ---------------------------------------------------------------------------

@router.get(
    "/{action_id}/remediation-options",
    response_model=RemediationOptionsResponse,
    summary="List remediation options",
    description=(
        "Return available remediation strategies for an action, including dependency checks, "
        "warnings, and whether risk acknowledgement is expected."
    ),
)
async def get_remediation_options(
    action_id: Annotated[str, Path(description="Action UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> RemediationOptionsResponse:
    """List strategy options and risk checks for one action."""
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    try:
        action_uuid = uuid.UUID(action_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid action_id", "detail": "action_id must be a valid UUID"},
        )

    action_result = await db.execute(
        select(Action).where(Action.id == action_uuid, Action.tenant_id == tenant_uuid)
    )
    action = action_result.scalar_one_or_none()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Action not found", "detail": f"No action found with ID {action_id}"},
        )

    account: AwsAccount | None = None
    account_result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_uuid,
            AwsAccount.account_id == action.account_id,
        )
    )
    account = account_result.scalar_one_or_none()

    strategies = list_strategies_for_action_type(action.action_type)
    if not strategies:
        # Backward-compatible behavior for action types not yet migrated to strategy catalog.
        mode_options: list[Literal["pr_only", "direct_fix"]] = ["pr_only"]
        from worker.services.direct_fix import SUPPORTED_ACTION_TYPES

        if action.action_type in SUPPORTED_ACTION_TYPES:
            mode_options.append("direct_fix")
        return RemediationOptionsResponse(
            action_id=str(action.id),
            action_type=action.action_type,
            mode_options=mode_options,
            strategies=[],
        )

    option_items: list[RemediationOptionResponse] = []
    for strategy in strategies:
        # Defensive validation: ensures registry entries stay internally consistent.
        validate_strategy(action.action_type, strategy["strategy_id"], strategy["mode"])
        risk_snapshot = evaluate_strategy_impact(action, strategy, {}, account=account)
        checks: list[DependencyCheckResponse] = [
            DependencyCheckResponse(
                code=check["code"],
                status=check["status"],
                message=check["message"],
            )
            for check in risk_snapshot["checks"]
        ]
        option_items.append(
            RemediationOptionResponse(
                strategy_id=strategy["strategy_id"],
                label=strategy["label"],
                mode=strategy["mode"],
                risk_level=strategy["risk_level"],
                recommended=strategy["recommended"],
                requires_inputs=strategy["requires_inputs"],
                input_schema=strategy["input_schema"],
                dependency_checks=checks,
                warnings=risk_snapshot["warnings"],
                supports_exception_flow=strategy["supports_exception_flow"],
            )
        )

    mode_options = list_mode_options_for_action_type(action.action_type)
    return RemediationOptionsResponse(
        action_id=str(action.id),
        action_type=action.action_type,
        mode_options=mode_options,
        strategies=option_items,
    )


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
    strategy_id: Annotated[
        str | None,
        Query(description="Optional remediation strategy ID for direct-fix preview."),
    ] = None,
    strategy_inputs_json: Annotated[
        str | None,
        Query(alias="strategy_inputs", description="Optional JSON object string for strategy inputs."),
    ] = None,
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

    parsed_strategy_inputs: dict[str, Any] | None = None
    if strategy_inputs_json:
        try:
            raw = json.loads(strategy_inputs_json)
            if isinstance(raw, dict):
                parsed_strategy_inputs = raw
            else:
                raise ValueError("strategy_inputs must be a JSON object")
        except Exception as exc:
            return RemediationPreviewResponse(
                compliant=False,
                message=f"Invalid strategy_inputs: {exc}",
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
            strategy_id,
            parsed_strategy_inputs,
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
