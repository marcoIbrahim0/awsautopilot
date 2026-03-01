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
from sqlalchemy import String, and_, case, cast, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload

from backend.auth import get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.action import Action
from backend.models.action_finding import ActionFinding
from backend.models.action_group import ActionGroup
from backend.models.action_group_membership import ActionGroupMembership
from backend.models.aws_account import AwsAccount
from backend.models.finding import Finding
from backend.models.user import User
from backend.routers.aws_accounts import get_account_for_tenant, get_tenant, resolve_tenant_id
from backend.services.aws import assume_role
from backend.services.exception_service import get_exception_state_for_response, get_exception_states_for_entities
from backend.services.direct_fix_bridge import (
    DirectFixModuleUnavailable,
    get_supported_direct_fix_action_types,
    run_remediation_preview_bridge,
)
from backend.services.remediation_risk import evaluate_strategy_impact
from backend.services.remediation_runtime_checks import collect_runtime_risk_signals
from backend.services.remediation_strategy import (
    list_mode_options_for_action_type,
    list_strategies_for_action_type,
    validate_strategy,
)
from backend.services.root_credentials_workflow import (
    ROOT_CREDENTIALS_REQUIRED_MESSAGE,
    ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
    is_root_credentials_required_action,
)
from backend.utils.sqs import (
    build_compute_actions_job_payload,
    build_reconcile_inventory_shard_job_payload,
    parse_queue_region,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actions", tags=["actions"])

_RUNTIME_RISK_OPTION_STRATEGIES = frozenset(
    {
        "s3_bucket_block_public_access_standard",
        "s3_migrate_cloudfront_oac_private",
    }
)


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


class ReconcileActionsRequest(BaseModel):
    """Scope for action reconciliation enqueue."""

    account_id: str = Field(..., description="AWS account ID (12 digits).")
    region: Optional[str] = Field(
        default=None,
        description="AWS region. If omitted, all configured regions for the account are reconciled.",
    )


class ReconcileActionsResponse(BaseModel):
    """Response for successful reconcile enqueue (202 Accepted)."""

    message: str = "Action reconciliation jobs queued"
    tenant_id: str = Field(..., description="Tenant UUID")
    scope: dict = Field(default_factory=dict, description="Scope used: account_id and/or region if provided")
    enqueued_jobs: int = Field(..., description="Number of reconcile shard jobs enqueued")


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
    what_is_wrong: str
    what_the_fix_does: str
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


_ACTION_FIX_SUMMARY_BY_TYPE: dict[str, str] = {
    "s3_block_public_access": "Enables account-level S3 Block Public Access to stop broad public exposure.",
    "enable_security_hub": "Enables Security Hub and default standards to restore security visibility.",
    "enable_guardduty": "Enables GuardDuty detector coverage in the target region.",
    "s3_bucket_block_public_access": "Adds bucket-level public access blocks to prevent public ACL/policy exposure.",
    "s3_bucket_encryption": "Enforces default server-side encryption on the affected S3 bucket.",
    "sg_restrict_public_ports": "Restricts risky inbound security-group rules on unauthorized public ports.",
    "cloudtrail_enabled": "Enables CloudTrail so account activity is logged for audit and detection.",
    "aws_config_enabled": "Enables AWS Config recorder and delivery channel for continuous config tracking.",
    "ssm_block_public_sharing": "Disables public sharing for SSM documents to reduce unauthorized exposure.",
    "ebs_snapshot_block_public_access": "Blocks public sharing of EBS snapshots for this account and region.",
    "ebs_default_encryption": "Enables EBS default encryption for newly created volumes.",
    "s3_bucket_require_ssl": "Adds policy enforcement so bucket access requires TLS/SSL.",
    "iam_root_access_key_absent": "Guides removal of root user access keys and restoration of safer IAM access.",
    "s3_bucket_access_logging": "Configures server access logging to improve traceability of bucket access.",
    "s3_bucket_lifecycle_configuration": "Applies lifecycle rules to enforce retention and cost-control posture.",
    "s3_bucket_encryption_kms": "Enforces SSE-KMS encryption policy for the affected S3 bucket.",
}


def _action_target_label(action: Action) -> str:
    if action.resource_id:
        return action.resource_id
    if action.target_id:
        return action.target_id
    return "the affected resource"


def _build_what_is_wrong(action: Action) -> str:
    description = (action.description or "").strip()
    if description:
        return description
    title = (action.title or "").strip()
    if title:
        return title
    control = (action.control_id or "Unknown control").strip()
    return f"{control} is failing for {_action_target_label(action)}."


def _build_what_the_fix_does(action: Action) -> str:
    known = _ACTION_FIX_SUMMARY_BY_TYPE.get((action.action_type or "").strip())
    if known:
        return known
    control = (action.control_id or "the failing control").strip()
    return f"Applies the configured remediation workflow to address {control} findings."


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
    exception_only: bool


class RemediationOptionsResponse(BaseModel):
    """Available remediation options for an action, including risk signals."""

    action_id: str
    action_type: str
    mode_options: list[Literal["pr_only", "direct_fix"]]
    strategies: list[RemediationOptionResponse]
    manual_high_risk: bool = False
    pre_execution_notice: str | None = None
    runbook_url: str | None = None


def _mode_options_for_action(action_type: str) -> list[Literal["pr_only", "direct_fix"]]:
    strategies = list_strategies_for_action_type(action_type)
    if strategies:
        return list_mode_options_for_action_type(action_type)

    # Backward-compatible behavior for action types not yet migrated to strategy catalog.
    mode_options: list[Literal["pr_only", "direct_fix"]] = ["pr_only"]
    if action_type in get_supported_direct_fix_action_types():
        mode_options.append("direct_fix")
    return mode_options


def _action_to_list_item(
    action: Action,
    exception_state: dict | None = None,
    finding_count: int | None = None,
    status_override: str | None = None,
) -> ActionListItem:
    """Build list item from Action; finding_count may be supplied from SQL aggregation."""
    state = exception_state or {}
    resolved_finding_count = finding_count
    if resolved_finding_count is None:
        resolved_finding_count = len(action.action_finding_links or [])
    return ActionListItem(
        id=str(action.id),
        action_type=action.action_type,
        target_id=action.target_id,
        account_id=action.account_id,
        region=action.region,
        priority=action.priority,
        status=status_override or action.status,
        title=action.title,
        control_id=action.control_id,
        resource_id=action.resource_id,
        updated_at=action.updated_at.isoformat() if action.updated_at else None,
        finding_count=resolved_finding_count,
        exception_id=state.get("exception_id"),
        exception_expires_at=state.get("exception_expires_at"),
        exception_expired=state.get("exception_expired"),
    )


def _finding_effective_status_sql_expr() -> object:
    """SQL expression for user-facing finding status (shadow-aware)."""
    shadow_status = func.upper(func.coalesce(Finding.shadow_status_normalized, ""))
    canonical_status = func.upper(func.coalesce(Finding.status, ""))
    return case(
        (shadow_status == "RESOLVED", "RESOLVED"),
        ((shadow_status == "OPEN") & (canonical_status == "RESOLVED"), "NEW"),
        else_=canonical_status,
    )


def _action_has_effective_open_finding_expr(tenant_uuid: Any) -> object:
    """Correlated SQL expression: action has at least one effective-open linked finding."""
    return exists(
        select(1)
        .select_from(ActionFinding)
        .join(Finding, Finding.id == ActionFinding.finding_id)
        .where(ActionFinding.action_id == Action.id)
        .where(Finding.tenant_id == tenant_uuid)
        .where(_finding_effective_status_sql_expr() != "RESOLVED")
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


def _build_batch_target_id_from_fields(
    action_type: str,
    account_id: str,
    region: str | None,
    status: str,
) -> str:
    resolved_region = region or "global"
    return f"batch|{action_type}|{account_id}|{resolved_region}|{status}"


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
        what_is_wrong=_build_what_is_wrong(action),
        what_the_fix_does=_build_what_the_fix_does(action),
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

    finding_counts = (
        select(
            ActionFinding.action_id.label("action_id"),
            func.count(ActionFinding.finding_id).label("finding_count"),
        )
        .group_by(ActionFinding.action_id)
        .subquery()
    )
    finding_count_expr = func.coalesce(finding_counts.c.finding_count, 0)
    use_effective_visibility = settings.ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED
    effective_open_expr = _action_has_effective_open_finding_expr(tenant_uuid)
    normalized_status_filter = status_filter.strip().lower() if status_filter is not None else None

    filters = [Action.tenant_id == tenant_uuid]
    if settings.ONLY_IN_SCOPE_CONTROLS:
        filters.append(Action.action_type != "pr_only")
    if account_id is not None:
        filters.append(Action.account_id == account_id)
    if region is not None:
        filters.append(Action.region == region)
    if control_id is not None:
        filters.append(Action.control_id == control_id.strip())
    if resource_id is not None:
        filters.append(Action.resource_id == resource_id.strip())
    if action_type is not None:
        filters.append(Action.action_type == action_type.strip())
    if normalized_status_filter is not None:
        if use_effective_visibility and normalized_status_filter == "open":
            filters.append(
                or_(
                    Action.status == "open",
                    and_(Action.status == "resolved", effective_open_expr),
                )
            )
        elif use_effective_visibility and normalized_status_filter == "resolved":
            filters.append(and_(Action.status == "resolved", ~effective_open_expr))
        else:
            filters.append(Action.status == normalized_status_filter)
    if not include_orphans:
        filters.append(finding_count_expr > 0)

    if group_by == "batch":
        group_filters = [ActionGroup.tenant_id == tenant_uuid]
        if settings.ONLY_IN_SCOPE_CONTROLS:
            group_filters.append(ActionGroup.action_type != "pr_only")
        if account_id is not None:
            group_filters.append(ActionGroup.account_id == account_id)
        if region is not None:
            group_filters.append(ActionGroup.region == region)
        if action_type is not None:
            group_filters.append(ActionGroup.action_type == action_type.strip())

        if use_effective_visibility:
            open_count_expr = func.sum(
                case(
                    (
                        or_(
                            Action.status == "open",
                            and_(Action.status == "resolved", effective_open_expr),
                        ),
                        1,
                    ),
                    else_=0,
                )
            )
            resolved_count_expr = func.sum(
                case(
                    (and_(Action.status == "resolved", ~effective_open_expr), 1),
                    else_=0,
                )
            )
        else:
            open_count_expr = func.sum(case((Action.status == "open", 1), else_=0))
            resolved_count_expr = func.sum(case((Action.status == "resolved", 1), else_=0))
        in_progress_count_expr = func.sum(case((Action.status == "in_progress", 1), else_=0))
        suppressed_count_expr = func.sum(case((Action.status == "suppressed", 1), else_=0))

        grouped_query = (
            select(
                cast(ActionGroup.id, String).label("id"),
                ActionGroup.action_type.label("action_type"),
                ActionGroup.account_id.label("account_id"),
                ActionGroup.region.label("region"),
                func.max(Action.priority).label("priority"),
                func.max(Action.updated_at).label("updated_at"),
                func.max(Action.control_id).label("control_id"),
                func.count(Action.id).label("action_count"),
                func.coalesce(func.sum(finding_count_expr), 0).label("finding_count"),
                func.coalesce(open_count_expr, 0).label("open_count"),
                func.coalesce(in_progress_count_expr, 0).label("in_progress_count"),
                func.coalesce(resolved_count_expr, 0).label("resolved_count"),
                func.coalesce(suppressed_count_expr, 0).label("suppressed_count"),
            )
            .select_from(ActionGroup)
            .join(
                ActionGroupMembership,
                (ActionGroupMembership.group_id == ActionGroup.id)
                & (ActionGroupMembership.tenant_id == ActionGroup.tenant_id),
            )
            .join(
                Action,
                (Action.id == ActionGroupMembership.action_id)
                & (Action.tenant_id == ActionGroupMembership.tenant_id),
            )
            .outerjoin(finding_counts, Action.id == finding_counts.c.action_id)
            .where(*group_filters)
            .group_by(ActionGroup.id, ActionGroup.action_type, ActionGroup.account_id, ActionGroup.region)
        )

        if normalized_status_filter is not None:
            status_value = normalized_status_filter
            if status_value == "open":
                grouped_query = grouped_query.having(func.coalesce(open_count_expr, 0) > 0)
            elif status_value == "in_progress":
                grouped_query = grouped_query.having(func.coalesce(in_progress_count_expr, 0) > 0)
            elif status_value == "resolved":
                grouped_query = grouped_query.having(
                    func.coalesce(open_count_expr, 0) == 0,
                    func.coalesce(in_progress_count_expr, 0) == 0,
                    func.coalesce(resolved_count_expr, 0) > 0,
                )
            elif status_value == "suppressed":
                grouped_query = grouped_query.having(
                    func.coalesce(open_count_expr, 0) == 0,
                    func.coalesce(in_progress_count_expr, 0) == 0,
                    func.coalesce(resolved_count_expr, 0) == 0,
                    func.coalesce(suppressed_count_expr, 0) > 0,
                )

        if not include_orphans:
            grouped_query = grouped_query.having(func.coalesce(func.sum(finding_count_expr), 0) > 0)

        count_query = select(func.count()).select_from(grouped_query.order_by(None).subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        grouped_query = grouped_query.order_by(
            func.max(Action.priority).desc(),
            func.max(Action.updated_at).desc().nullslast(),
        ).limit(limit).offset(offset)
        rows = (await db.execute(grouped_query)).all()

        paged_items = []
        for row in rows:
            open_count = int(row.open_count or 0)
            in_progress_count = int(row.in_progress_count or 0)
            resolved_count = int(row.resolved_count or 0)
            suppressed_count = int(row.suppressed_count or 0)
            total_actions = int(row.action_count or 0)
            derived_status = "open"
            if normalized_status_filter is not None:
                derived_status = normalized_status_filter
            elif open_count > 0:
                derived_status = "open"
            elif in_progress_count > 0:
                derived_status = "in_progress"
            elif resolved_count > 0 and (resolved_count + suppressed_count) == total_actions:
                derived_status = "resolved"
            elif suppressed_count > 0 and suppressed_count == total_actions:
                derived_status = "suppressed"

            paged_items.append(
                ActionListItem(
                    id=str(row.id),
                    action_type=row.action_type,
                    target_id=_build_batch_target_id_from_fields(
                        row.action_type,
                        row.account_id,
                        row.region,
                        derived_status,
                    ),
                    account_id=row.account_id,
                    region=row.region,
                    priority=int(row.priority or 0),
                    status=derived_status,
                    title=_batch_title(row.action_type, total_actions),
                    control_id=row.control_id,
                    resource_id=None,
                    updated_at=row.updated_at.isoformat() if row.updated_at else None,
                    finding_count=int(row.finding_count or 0),
                    is_batch=True,
                    batch_action_count=total_actions,
                    batch_finding_count=int(row.finding_count or 0),
                )
            )
        logger.info(
            "Listed %d batch action groups for tenant %s (total=%d)",
            len(paged_items),
            tenant_uuid,
            total,
        )
        return ActionsListResponse(items=paged_items, total=total)

    if use_effective_visibility:
        query = (
            select(
                Action,
                finding_count_expr.label("finding_count"),
                effective_open_expr.label("has_effective_open_findings"),
            )
            .outerjoin(finding_counts, Action.id == finding_counts.c.action_id)
            .where(*filters)
        )
    else:
        query = (
            select(
                Action,
                finding_count_expr.label("finding_count"),
            )
            .outerjoin(finding_counts, Action.id == finding_counts.c.action_id)
            .where(*filters)
        )
    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Action.priority.desc(), Action.updated_at.desc().nullslast()).limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()
    actions = [row[0] for row in rows]
    finding_counts_by_action = {row[0].id: int(row[1] or 0) for row in rows}
    effective_open_by_action: dict[uuid.UUID, bool] = {}
    if use_effective_visibility:
        effective_open_by_action = {row[0].id: bool(row[2]) for row in rows}
    exception_state_by_action = await get_exception_states_for_entities(
        db,
        tenant_id=tenant_uuid,
        entity_type="action",
        entity_ids=[action.id for action in actions],
    )

    items = [
        _action_to_list_item(
            action,
            exception_state=exception_state_by_action.get(action.id),
            finding_count=finding_counts_by_action.get(action.id, 0),
            status_override=(
                "open"
                if use_effective_visibility
                and action.status == "resolved"
                and effective_open_by_action.get(action.id, False)
                else None
            ),
        )
        for action in actions
    ]
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
            selectinload(Action.action_finding_links)
            .selectinload(ActionFinding.finding)
            .load_only(
                Finding.id,
                Finding.finding_id,
                Finding.severity_label,
                Finding.title,
                Finding.resource_id,
                Finding.account_id,
                Finding.region,
                Finding.updated_at,
            ),
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
    root_required = is_root_credentials_required_action(action.action_type)
    pre_execution_notice = ROOT_CREDENTIALS_REQUIRED_MESSAGE if root_required else None
    runbook_url = ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH if root_required else None
    mode_options = _mode_options_for_action(action.action_type)
    if not strategies:
        return RemediationOptionsResponse(
            action_id=str(action.id),
            action_type=action.action_type,
            mode_options=mode_options,
            strategies=[],
            manual_high_risk=root_required,
            pre_execution_notice=pre_execution_notice,
            runbook_url=runbook_url,
        )

    option_items: list[RemediationOptionResponse] = []
    for strategy in strategies:
        # Defensive validation: ensures registry entries stay internally consistent.
        validate_strategy(action.action_type, strategy["strategy_id"], strategy["mode"])
        runtime_signals: dict[str, Any] = {}
        if strategy["strategy_id"] in _RUNTIME_RISK_OPTION_STRATEGIES:
            runtime_signals = collect_runtime_risk_signals(
                action=action,
                strategy=strategy,
                strategy_inputs={},
                account=account,
            )
        risk_snapshot = evaluate_strategy_impact(
            action,
            strategy,
            {},
            account=account,
            runtime_signals=runtime_signals,
        )
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
                exception_only=strategy["exception_only"],
            )
        )

    return RemediationOptionsResponse(
        action_id=str(action.id),
        action_type=action.action_type,
        mode_options=mode_options,
        strategies=option_items,
        manual_high_risk=root_required,
        pre_execution_notice=pre_execution_notice,
        runbook_url=runbook_url,
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
        Literal["direct_fix", "pr_only"],
        Query(description="Remediation mode. Accepts values advertised in remediation-options mode_options."),
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

    if mode == "pr_only":
        return RemediationPreviewResponse(
            compliant=False,
            message="Preview for mode 'pr_only' is informational only. Generate a PR bundle to review the change set.",
            will_apply=False,
        )

    supported_direct_fix_action_types = get_supported_direct_fix_action_types()
    if not supported_direct_fix_action_types:
        return RemediationPreviewResponse(
            compliant=False,
            message="Direct-fix preview is unavailable in this API deployment. Use PR bundle mode.",
            will_apply=False,
        )
    if action.action_type not in supported_direct_fix_action_types:
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
            run_remediation_preview_bridge,
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
    except DirectFixModuleUnavailable as e:
        return RemediationPreviewResponse(
            compliant=False,
            message=str(e),
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
            selectinload(Action.action_finding_links)
            .selectinload(ActionFinding.finding)
            .load_only(
                Finding.id,
                Finding.finding_id,
                Finding.severity_label,
                Finding.title,
                Finding.resource_id,
                Finding.account_id,
                Finding.region,
                Finding.updated_at,
            ),
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
            selectinload(Action.action_finding_links)
            .selectinload(ActionFinding.finding)
            .load_only(
                Finding.id,
                Finding.finding_id,
                Finding.severity_label,
                Finding.title,
                Finding.resource_id,
                Finding.account_id,
                Finding.region,
                Finding.updated_at,
            ),
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


# ---------------------------------------------------------------------------
# POST /actions/reconcile
# ---------------------------------------------------------------------------

@router.post(
    "/reconcile",
    response_model=ReconcileActionsResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger action reconciliation",
    description=(
        "Enqueue inventory reconciliation shard jobs for the current tenant and account. "
        "If region is omitted, all configured account regions are enqueued."
    ),
    responses={
        404: {"description": "Tenant or account not found"},
        400: {"description": "Invalid scope (e.g. unknown region for account)"},
        503: {"description": "Queue unavailable or SQS send failed"},
    },
)
async def trigger_action_reconcile(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    body: ReconcileActionsRequest = Body(...),
) -> ReconcileActionsResponse:
    """Enqueue one reconciliation sweep per (region, service) for an account in the current tenant."""
    if not settings.has_inventory_reconcile_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Action reconciliation unavailable",
                "detail": "Queue URL not configured. Set SQS_INVENTORY_RECONCILE_QUEUE_URL.",
            },
        )

    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    account = await get_account_for_tenant(tenant_uuid, body.account_id, db)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Account not found",
                "detail": "No AWS account found with the given ID for this tenant.",
            },
        )

    account_regions = list(account.regions or [])
    if body.region is not None and body.region not in set(account_regions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Bad request",
                "detail": "region must be one of the account's configured regions.",
            },
        )

    target_regions = [body.region] if body.region else (account_regions or [settings.AWS_REGION])
    services = settings.control_plane_inventory_services_list
    max_resources = int(settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD or 500)

    queue_url = settings.SQS_INVENTORY_RECONCILE_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    now = datetime.now(timezone.utc).isoformat()
    enqueued_jobs = 0

    try:
        for region in target_regions:
            for service in services:
                payload = build_reconcile_inventory_shard_job_payload(
                    tenant_id=tenant_uuid,
                    account_id=body.account_id,
                    region=region,
                    service=service,
                    created_at=now,
                    sweep_mode="global",
                    max_resources=max_resources,
                )
                sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
                enqueued_jobs += 1
    except ClientError as e:
        logger.exception("SQS send_message failed for action_reconcile: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Action reconciliation unavailable",
                "detail": "Could not enqueue reconcile jobs. Please try again later.",
            },
        ) from e

    scope: dict[str, str] = {"account_id": body.account_id}
    if body.region:
        scope["region"] = body.region

    return ReconcileActionsResponse(
        message="Action reconciliation jobs queued",
        tenant_id=str(tenant_uuid),
        scope=scope,
        enqueued_jobs=enqueued_jobs,
    )
