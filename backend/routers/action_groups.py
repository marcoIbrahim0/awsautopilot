from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Mapping, NoReturn, Optional

import boto3
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user, get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.action import Action
from backend.models.action_group import ActionGroup
from backend.models.action_group_membership import ActionGroupMembership
from backend.models.action_group_run import ActionGroupRun
from backend.models.aws_account import AwsAccount
from backend.models.enums import ActionGroupRunStatus
from backend.models.remediation_run import RemediationRun
from backend.models.user import User
from backend.routers.aws_accounts import get_tenant, resolve_tenant_id
from backend.services.action_groups import get_group_detail, list_groups_with_counters
from backend.services.bundle_reporting_tokens import (
    BundleReportingTokenSecretNotConfiguredError,
    issue_group_run_reporting_token,
)
from backend.services.grouped_bundle_run_persistence import (
    enqueue_group_bundle_run_or_503,
    persist_group_bundle_run,
)
from backend.services.grouped_bundle_conflicts import (
    GroupedBundleRunRecord,
    find_active_grouped_duplicate,
    find_latest_successful_grouped_duplicate,
)
from backend.services.grouped_remediation_runs import (
    GroupedActionScope,
    GroupedRemediationRunValidationError,
    build_grouped_run_persistence_plan,
    normalize_grouped_request_from_action_group,
)
from backend.services.root_key_resolution_adapter import (
    build_root_key_execution_authority_error,
    is_root_key_action_type,
)
from backend.services.remediation_strategy import strategy_required_for_action_type

router = APIRouter(prefix="/action-groups", tags=["action-groups"])
logger = logging.getLogger("backend.routers.action_groups")


class ActionGroupCountersResponse(BaseModel):
    run_successful: int
    run_not_successful: int
    metadata_only: int
    not_run_yet: int
    total_actions: int


class ActionGroupListItemResponse(BaseModel):
    id: str
    group_key: str
    action_type: str
    account_id: str
    region: str | None
    created_at: str | None
    updated_at: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)
    counters: ActionGroupCountersResponse


class ActionGroupsListResponse(BaseModel):
    items: list[ActionGroupListItemResponse]
    total: int


class ActionGroupMemberLatestRunResponse(BaseModel):
    id: str | None = None
    status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class ActionGroupMemberResponse(BaseModel):
    action_id: str
    title: str
    control_id: str | None
    resource_id: str | None
    action_status: str
    priority: int
    assigned_at: str | None
    status_bucket: str
    last_attempt_at: str | None
    last_confirmed_at: str | None
    last_confirmation_source: str | None
    pending_confirmation: bool = False
    pending_confirmation_started_at: str | None = None
    pending_confirmation_deadline_at: str | None = None
    pending_confirmation_message: str | None = None
    pending_confirmation_severity: str | None = None
    status_message: str | None = None
    status_severity: str | None = None
    followup_kind: str | None = None
    latest_run: ActionGroupMemberLatestRunResponse


class ActionGroupDetailResponse(BaseModel):
    id: str
    tenant_id: str
    group_key: str
    action_type: str
    account_id: str
    region: str | None
    created_at: str | None
    updated_at: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)
    counters: ActionGroupCountersResponse
    members: list[ActionGroupMemberResponse]
    can_generate_bundle: bool = True
    blocked_reason: str | None = None
    blocked_detail: str | None = None
    blocked_by_run_id: str | None = None


class ActionGroupRunListItemResponse(BaseModel):
    id: str
    remediation_run_id: str | None
    initiated_by_user_id: str | None
    mode: str
    status: str
    started_at: str | None
    finished_at: str | None
    reporting_source: str
    created_at: str
    updated_at: str
    results: list["ActionGroupRunResultResponse"] = Field(default_factory=list)


class ActionGroupRunResultResponse(BaseModel):
    action_id: str
    execution_status: str
    execution_error_code: str | None
    execution_error_message: str | None
    result_type: str | None
    support_tier: str | None
    reason: str | None
    blocked_reasons: list[str] = Field(default_factory=list)
    execution_started_at: str | None
    execution_finished_at: str | None


class ActionGroupRunsResponse(BaseModel):
    items: list[ActionGroupRunListItemResponse]
    total: int


class ActionGroupRepoTargetRequest(BaseModel):
    provider: str | None = Field(default=None, min_length=1, max_length=64)
    repository: str = Field(..., min_length=1, max_length=255)
    base_branch: str = Field(..., min_length=1, max_length=255)
    head_branch: str | None = Field(default=None, min_length=1, max_length=255)
    root_path: str | None = Field(default=None, min_length=1, max_length=512)


class ActionGroupActionOverrideRequest(BaseModel):
    action_id: str = Field(..., description="UUID of the grouped action to override.")
    strategy_id: str | None = Field(None, description="Optional strategy override for this grouped action.")
    profile_id: str | None = Field(None, description="Optional remediation profile override for this grouped action.")
    strategy_inputs: dict[str, Any] | None = Field(
        None,
        description="Optional strategy_inputs override for this grouped action.",
    )


class CreateActionGroupBundleRunRequest(BaseModel):
    strategy_id: str | None = None
    strategy_inputs: dict[str, Any] | None = None
    action_overrides: list[ActionGroupActionOverrideRequest] = Field(default_factory=list)
    risk_acknowledged: bool = False
    bucket_creation_acknowledged: bool = False
    pr_bundle_variant: str | None = None
    repo_target: ActionGroupRepoTargetRequest | None = None


class CreateActionGroupBundleRunResponse(BaseModel):
    group_run_id: str
    remediation_run_id: str
    reporting_token: str
    reporting_callback_url: str
    status: str


def _as_iso(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        return str(value)
    except Exception:
        return None


def _as_action_group_execution_status(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _group_run_result_type(raw_result: Mapping[str, Any]) -> str:
    result_type = raw_result.get("result_type")
    if isinstance(result_type, str) and result_type:
        return result_type
    return "executable"


def _blocked_reasons_from_raw_result(raw_result: Mapping[str, Any], *, result_type: str) -> list[str]:
    if result_type != "non_executable":
        return []
    blocked_reasons = raw_result.get("blocked_reasons")
    if not isinstance(blocked_reasons, list):
        return []
    return [item for item in blocked_reasons if isinstance(item, str)]


def _serialize_action_group_run_result(row: object) -> ActionGroupRunResultResponse:
    raw_result = row.raw_result if isinstance(getattr(row, "raw_result", None), Mapping) else {}
    result_type = _group_run_result_type(raw_result)
    return ActionGroupRunResultResponse(
        action_id=str(row.action_id),
        execution_status=_as_action_group_execution_status(row.execution_status),
        execution_error_code=row.execution_error_code,
        execution_error_message=row.execution_error_message,
        result_type=result_type,
        support_tier=raw_result.get("support_tier") if result_type == "non_executable" else None,
        reason=raw_result.get("reason") if result_type == "non_executable" else None,
        blocked_reasons=_blocked_reasons_from_raw_result(raw_result, result_type=result_type),
        execution_started_at=_as_iso(row.execution_started_at),
        execution_finished_at=_as_iso(row.execution_finished_at),
    )


def _serialize_action_group_run(row: ActionGroupRun) -> ActionGroupRunListItemResponse:
    return ActionGroupRunListItemResponse(
        id=str(row.id),
        remediation_run_id=str(row.remediation_run_id) if row.remediation_run_id else None,
        initiated_by_user_id=str(row.initiated_by_user_id) if row.initiated_by_user_id else None,
        mode=row.mode,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        started_at=_as_iso(row.started_at),
        finished_at=_as_iso(row.finished_at),
        reporting_source=row.reporting_source,
        created_at=_as_iso(row.created_at) or "",
        updated_at=_as_iso(row.updated_at) or "",
        results=[_serialize_action_group_run_result(result) for result in row.results],
    )


def _parse_group_uuid_or_400(group_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(group_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group_id") from exc


def _reporting_callback_url() -> str:
    return f"{settings.API_PUBLIC_URL.rstrip('/')}/api/internal/group-runs/report"


def _raise_action_group_grouped_validation_error(exc: GroupedRemediationRunValidationError) -> NoReturn:
    if exc.code == "exception_only_strategy":
        detail = {
            "error": "Exception-only strategy",
            "detail": str(exc),
            "exception_flow": exc.details.get("exception_flow") if isinstance(exc.details, dict) else {},
        }
    elif exc.code == "dependency_check_failed":
        detail = _grouped_risk_error_detail(exc, error="Dependency check failed")
    elif exc.code == "risk_ack_required":
        detail = _grouped_risk_error_detail(exc, error="Risk acknowledgement required")
    elif exc.code == "duplicate_action_override":
        detail = {"error": "Duplicate action_overrides entry", "detail": str(exc)}
    elif exc.code == "override_action_not_in_group":
        detail = {"error": "Invalid action_overrides[].action_id", "detail": str(exc)}
    elif exc.code == "invalid_override_strategy":
        detail = {"error": "Invalid strategy selection", "detail": str(exc)}
    elif exc.code == "invalid_override_profile":
        detail = {"error": "Invalid profile_id", "detail": str(exc)}
    elif exc.code == "missing_grouped_strategy_id":
        detail = {"error": "Missing strategy_id", "detail": str(exc)}
    elif exc.code == "strategy_conflict":
        detail = {"error": "Strategy conflict", "detail": str(exc)}
    elif exc.code == "invalid_pr_bundle_variant":
        detail = {"error": "Invalid pr_bundle_variant", "detail": str(exc)}
    else:
        detail = {"error": "Invalid grouped remediation request", "detail": str(exc), "reason": exc.code}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _grouped_risk_error_detail(
    exc: GroupedRemediationRunValidationError,
    *,
    error: str,
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "error": error,
        "detail": (
            "One or more dependency checks blocked this remediation strategy."
            if error == "Dependency check failed"
            else "This remediation strategy has warning/unknown dependency checks. Set risk_acknowledged=true after review."
        ),
    }
    risk_snapshot = exc.details.get("risk_snapshot") if isinstance(exc.details, dict) else None
    if isinstance(risk_snapshot, dict):
        detail["risk_snapshot"] = risk_snapshot
    return detail


def _raise_root_key_execution_authority(strategy_id: str | None) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=build_root_key_execution_authority_error(strategy_id=strategy_id),
    )


def _normalize_group_request_or_400(body: CreateActionGroupBundleRunRequest, *, action_type: str):
    try:
        normalized = normalize_grouped_request_from_action_group(body)
    except GroupedRemediationRunValidationError as exc:
        _raise_action_group_grouped_validation_error(exc)
    has_top_level_strategy = bool(normalized.strategy_id or normalized.pr_bundle_variant)
    if (strategy_required_for_action_type(action_type) or normalized.action_overrides) and not has_top_level_strategy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Missing strategy_id",
                "detail": (
                    f"strategy_id is required for action_type '{action_type}'. "
                    "Fetch options via GET /api/actions/{id}/remediation-options."
                ),
            },
        )
    return normalized


async def _load_action_group_or_404(db: AsyncSession, *, group_id: uuid.UUID, tenant_id: uuid.UUID) -> ActionGroup:
    group = (
        await db.execute(select(ActionGroup).where(ActionGroup.id == group_id, ActionGroup.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action group not found")
    return group


async def _load_group_actions_or_404(db: AsyncSession, *, tenant_id: uuid.UUID, group_id: uuid.UUID) -> list[Action]:
    actions = (
        await db.execute(
            select(Action)
            .join(
                ActionGroupMembership,
                (ActionGroupMembership.action_id == Action.id)
                & (ActionGroupMembership.tenant_id == Action.tenant_id),
            )
            .where(ActionGroupMembership.tenant_id == tenant_id, ActionGroupMembership.group_id == group_id)
            .order_by(Action.priority.desc(), Action.updated_at.desc().nullslast(), Action.created_at.desc())
        )
    ).scalars().all()
    if not actions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action group has no members")
    return actions


async def _load_group_account(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_id: str,
) -> AwsAccount | None:
    result = await db.execute(
        select(AwsAccount).where(AwsAccount.tenant_id == tenant_id, AwsAccount.account_id == account_id)
    )
    return result.scalar_one_or_none()


def _create_group_run_with_token(
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    group: ActionGroup,
    action_ids: list[uuid.UUID],
) -> tuple[ActionGroupRun, str, str]:
    group_run = ActionGroupRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        group_id=group.id,
        initiated_by_user_id=user_id,
        mode="download_bundle",
        status=ActionGroupRunStatus.queued,
        reporting_source="system",
    )
    callback_url = _reporting_callback_url()
    try:
        token, token_jti, _ = issue_group_run_reporting_token(
            tenant_id=tenant_id,
            group_run_id=group_run.id,
            group_id=group.id,
            allowed_action_ids=action_ids,
        )
    except BundleReportingTokenSecretNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    group_run.report_token_jti = token_jti
    return group_run, token, callback_url


def _grouped_request_signature(plan: Any, *, group_key: str) -> dict[str, Any]:
    from backend.services.remediation_run_queue_contract import normalize_grouped_run_request_signature

    return normalize_grouped_run_request_signature(
        group_key=group_key,
        strategy_id=plan.request.strategy_id,
        strategy_inputs=plan.request.strategy_inputs,
        pr_bundle_variant=plan.request.pr_bundle_variant,
        repo_target=plan.request.repo_target,
        action_resolutions=plan.action_resolutions,
    )


def _grouped_conflict_detail(conflict: Any) -> dict[str, Any]:
    detail = {
        "error": (
            "PR bundle already created"
            if conflict.reason == "grouped_bundle_already_created_no_changes"
            else "Duplicate pending run"
        ),
        "detail": conflict.detail,
        "reason": conflict.reason,
        "existing_run_id": conflict.run_id,
        "existing_run_status": conflict.run_status,
    }
    if conflict.group_run_id:
        detail["existing_group_run_id"] = conflict.group_run_id
    return detail


def _build_grouped_run_record(group_run: ActionGroupRun, remediation_run: RemediationRun) -> GroupedBundleRunRecord:
    return GroupedBundleRunRecord(
        run_id=str(remediation_run.id),
        action_id=str(remediation_run.action_id),
        mode=remediation_run.mode.value if hasattr(remediation_run.mode, "value") else str(remediation_run.mode),
        status=remediation_run.status.value if hasattr(remediation_run.status, "value") else str(remediation_run.status),
        created_at=remediation_run.created_at,
        artifacts=remediation_run.artifacts if isinstance(remediation_run.artifacts, dict) else None,
        started_at=remediation_run.started_at,
        updated_at=remediation_run.updated_at,
        group_run_id=str(group_run.id),
    )


async def _load_grouped_run_records(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
) -> list[GroupedBundleRunRecord]:
    rows = (
        await db.execute(
            select(ActionGroupRun, RemediationRun)
            .join(RemediationRun, RemediationRun.id == ActionGroupRun.remediation_run_id)
            .where(ActionGroupRun.tenant_id == tenant_id, ActionGroupRun.group_id == group_id)
        )
    ).all()
    return [_build_grouped_run_record(group_run, remediation_run) for group_run, remediation_run in rows]


def _grouped_bundle_conflict(
    records: list[GroupedBundleRunRecord],
    *,
    request_signature: Mapping[str, Any],
) -> Any | None:
    now = datetime.now(timezone.utc)
    active = find_active_grouped_duplicate(records, request_signature=request_signature, now=now)
    if active is not None:
        return active
    return find_latest_successful_grouped_duplicate(records, request_signature=request_signature)


async def _group_bundle_generation_state(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    group: ActionGroup,
    actions: list[Action],
    account: AwsAccount | None,
    tenant_settings: Mapping[str, Any] | None,
) -> tuple[bool, str | None, str | None, str | None]:
    try:
        request = _normalize_group_request_or_400(CreateActionGroupBundleRunRequest(), action_type=group.action_type)
        plan = _build_action_group_plan_or_400(
            group=group,
            request=request,
            actions=actions,
            group_run=ActionGroupRun(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                group_id=group.id,
                mode="download_bundle",
                status=ActionGroupRunStatus.queued,
                reporting_source="system",
            ),
            token="availability-only",
            callback_url="availability-only",
            account=account,
            tenant_settings=tenant_settings,
        )
    except HTTPException:
        return True, None, None, None
    conflict = _grouped_bundle_conflict(
        await _load_grouped_run_records(db, tenant_id=tenant_id, group_id=group.id),
        request_signature=_grouped_request_signature(plan, group_key=group.group_key),
    )
    if conflict is None:
        return True, None, None, None
    return False, conflict.reason, conflict.detail, conflict.group_run_id


def _group_bundle_seed(group: ActionGroup, *, group_run: ActionGroupRun, token: str, callback_url: str) -> dict[str, Any]:
    return {
        "group_id": str(group.id),
        "group_key": group.group_key,
        "group_run_id": str(group_run.id),
        "reporting": {
            "callback_url": callback_url,
            "token": token,
            "reporting_source": "bundle_callback",
        },
    }


def _build_action_group_plan_or_400(
    *,
    group: ActionGroup,
    request: Any,
    actions: list[Action],
    group_run: ActionGroupRun,
    token: str,
    callback_url: str,
    account: AwsAccount | None,
    tenant_settings: Mapping[str, Any] | None,
):
    try:
        return build_grouped_run_persistence_plan(
            request=request,
            scope=GroupedActionScope(
                action_type=group.action_type,
                account_id=group.account_id,
                region=group.region,
                group_id=str(group.id),
                group_key=group.group_key,
            ),
            actions=actions,
            group_bundle_seed=_group_bundle_seed(group, group_run=group_run, token=token, callback_url=callback_url),
            account=account,
            tenant_settings=tenant_settings,
        )
    except GroupedRemediationRunValidationError as exc:
        _raise_action_group_grouped_validation_error(exc)


@router.get("", response_model=ActionGroupsListResponse)
async def list_action_groups(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[Optional[str], Query(description="Tenant UUID for non-auth mode")] = None,
    account_id: Annotated[str | None, Query(description="Optional account filter")] = None,
    region: Annotated[str | None, Query(description="Optional region filter")] = None,
    action_type: Annotated[str | None, Query(description="Optional action_type filter")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ActionGroupsListResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    listing = await list_groups_with_counters(
        db,
        tenant_id=tenant_uuid,
        account_id=account_id,
        region=region,
        action_type=action_type,
        limit=limit,
        offset=offset,
    )
    items = [
        ActionGroupListItemResponse(
            id=item["id"],
            group_key=item["group_key"],
            action_type=item["action_type"],
            account_id=item["account_id"],
            region=item["region"],
            created_at=_as_iso(item.get("created_at")),
            updated_at=_as_iso(item.get("updated_at")),
            metadata=item.get("metadata") or {},
            counters=ActionGroupCountersResponse(
                run_successful=int(item.get("run_successful") or 0),
                run_not_successful=int(item.get("run_not_successful") or 0),
                metadata_only=int(item.get("metadata_only") or 0),
                not_run_yet=int(item.get("not_run_yet") or 0),
                total_actions=int(item.get("total_actions") or 0),
            ),
        )
        for item in listing.get("items", [])
    ]
    return ActionGroupsListResponse(items=items, total=int(listing.get("total") or 0))


@router.get("/{group_id}", response_model=ActionGroupDetailResponse)
async def get_action_group_detail(
    group_id: Annotated[str, Path(description="Action group UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[Optional[str], Query(description="Tenant UUID for non-auth mode")] = None,
) -> ActionGroupDetailResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant(tenant_uuid, db)
    try:
        group_uuid = uuid.UUID(group_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group_id") from exc

    detail = await get_group_detail(db, tenant_id=tenant_uuid, group_id=group_uuid)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action group not found")

    group = detail["group"]
    counters = detail["counters"]
    members = []
    for member in detail["members"]:
        members.append(
            ActionGroupMemberResponse(
                action_id=member["action_id"],
                title=member.get("title") or "",
                control_id=member.get("control_id"),
                resource_id=member.get("resource_id"),
                action_status=member.get("action_status") or "open",
                priority=int(member.get("priority") or 0),
                assigned_at=_as_iso(member.get("assigned_at")),
                status_bucket=str(member.get("status_bucket") or "not_run_yet"),
                last_attempt_at=_as_iso(member.get("last_attempt_at")),
                last_confirmed_at=_as_iso(member.get("last_confirmed_at")),
                last_confirmation_source=member.get("last_confirmation_source"),
                pending_confirmation=bool(member.get("pending_confirmation")),
                pending_confirmation_started_at=_as_iso(member.get("pending_confirmation_started_at")),
                pending_confirmation_deadline_at=_as_iso(member.get("pending_confirmation_deadline_at")),
                pending_confirmation_message=member.get("pending_confirmation_message"),
                pending_confirmation_severity=member.get("pending_confirmation_severity"),
                status_message=member.get("status_message"),
                status_severity=member.get("status_severity"),
                followup_kind=member.get("followup_kind"),
                latest_run=ActionGroupMemberLatestRunResponse(
                    id=member.get("latest_run_id"),
                    status=member.get("latest_run_status"),
                    started_at=_as_iso(member.get("latest_run_started_at")),
                    finished_at=_as_iso(member.get("latest_run_finished_at")),
                ),
            )
        )

    group_model = await _load_action_group_or_404(db, group_id=group_uuid, tenant_id=tenant_uuid)
    group_actions = await _load_group_actions_or_404(db, tenant_id=tenant_uuid, group_id=group_uuid)
    account = await _load_group_account(db, tenant_id=tenant_uuid, account_id=group_model.account_id)
    can_generate_bundle, blocked_reason, blocked_detail, blocked_by_run_id = await _group_bundle_generation_state(
        db,
        tenant_id=tenant_uuid,
        group=group_model,
        actions=group_actions,
        account=account,
        tenant_settings=getattr(tenant, "remediation_settings", None),
    )

    return ActionGroupDetailResponse(
        id=str(group["id"]),
        tenant_id=str(group["tenant_id"]),
        group_key=str(group["group_key"]),
        action_type=str(group["action_type"]),
        account_id=str(group["account_id"]),
        region=group.get("region"),
        created_at=_as_iso(group.get("created_at")),
        updated_at=_as_iso(group.get("updated_at")),
        metadata=group.get("metadata") or {},
        counters=ActionGroupCountersResponse(
            run_successful=int(counters.get("run_successful") or 0),
            run_not_successful=int(counters.get("run_not_successful") or 0),
            metadata_only=int(counters.get("metadata_only") or 0),
            not_run_yet=int(counters.get("not_run_yet") or 0),
            total_actions=int(counters.get("total_actions") or 0),
        ),
        members=members,
        can_generate_bundle=can_generate_bundle,
        blocked_reason=blocked_reason,
        blocked_detail=blocked_detail,
        blocked_by_run_id=blocked_by_run_id,
    )


@router.get("/{group_id}/runs", response_model=ActionGroupRunsResponse)
async def get_action_group_runs(
    group_id: Annotated[str, Path(description="Action group UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[Optional[str], Query(description="Tenant UUID for non-auth mode")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ActionGroupRunsResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)
    try:
        group_uuid = uuid.UUID(group_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group_id") from exc

    total_result = await db.execute(
        select(func.count(ActionGroupRun.id)).where(
            ActionGroupRun.tenant_id == tenant_uuid,
            ActionGroupRun.group_id == group_uuid,
        )
    )
    total = int(total_result.scalar() or 0)

    rows = (
        await db.execute(
            select(ActionGroupRun)
            .where(ActionGroupRun.tenant_id == tenant_uuid, ActionGroupRun.group_id == group_uuid)
            .order_by(ActionGroupRun.created_at.desc(), ActionGroupRun.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()

    items = [_serialize_action_group_run(row) for row in rows]
    return ActionGroupRunsResponse(items=items, total=total)


@router.get("/{group_id}/runs/{run_id}", response_model=ActionGroupRunListItemResponse)
async def get_action_group_run(
    group_id: Annotated[str, Path(description="Action group UUID")],
    run_id: Annotated[str, Path(description="Action group run UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[Optional[str], Query(description="Tenant UUID for non-auth mode")] = None,
) -> ActionGroupRunListItemResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)
    try:
        group_uuid = uuid.UUID(group_id)
        run_uuid = uuid.UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group_id or run_id") from exc

    row = (
        await db.execute(
            select(ActionGroupRun).where(
                ActionGroupRun.tenant_id == tenant_uuid,
                ActionGroupRun.group_id == group_uuid,
                ActionGroupRun.id == run_uuid,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action group run not found")
    return _serialize_action_group_run(row)


@router.post(
    "/{group_id}/bundle-run",
    response_model=CreateActionGroupBundleRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_action_group_bundle_run(
    group_id: Annotated[str, Path(description="Action group UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: CreateActionGroupBundleRunRequest | None = Body(default=None),
) -> CreateActionGroupBundleRunResponse:
    if not settings.has_ingest_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingest queue URL not configured. Set SQS_INGEST_QUEUE_URL.",
    )
    group_uuid = _parse_group_uuid_or_400(group_id)
    request_body = body or CreateActionGroupBundleRunRequest()
    tenant = await get_tenant(current_user.tenant_id, db)
    group = await _load_action_group_or_404(db, group_id=group_uuid, tenant_id=current_user.tenant_id)
    action_rows = await _load_group_actions_or_404(db, tenant_id=current_user.tenant_id, group_id=group.id)
    normalized_request = _normalize_group_request_or_400(request_body, action_type=group.action_type)
    if is_root_key_action_type(group.action_type):
        _raise_root_key_execution_authority(normalized_request.strategy_id)
    account = await _load_group_account(db, tenant_id=current_user.tenant_id, account_id=group.account_id)
    group_run, token, callback_url = _create_group_run_with_token(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        group=group,
        action_ids=[action.id for action in action_rows],
    )
    plan = _build_action_group_plan_or_400(
        group=group,
        request=normalized_request,
        actions=action_rows,
        group_run=group_run,
        token=token,
        callback_url=callback_url,
        account=account,
        tenant_settings=getattr(tenant, "remediation_settings", None),
    )
    requires_bucket_creation_ack = any(
        entry.strategy_id == "cloudtrail_enable_guided"
        and entry.strategy_inputs.get("create_bucket_if_missing") is True
        for entry in plan.action_resolutions
    )
    if requires_bucket_creation_ack and not request_body.bucket_creation_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Bucket creation acknowledgement required",
                "detail": (
                    "This CloudTrail remediation may create a new S3 bucket and bucket policy for log delivery. "
                    "Set bucket_creation_acknowledged=true after review."
                ),
            },
        )
    conflict = _grouped_bundle_conflict(
        await _load_grouped_run_records(db, tenant_id=current_user.tenant_id, group_id=group.id),
        request_signature=_grouped_request_signature(plan, group_key=group.group_key),
    )
    if conflict is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_grouped_conflict_detail(conflict))
    remediation_run = await persist_group_bundle_run(
        db,
        group_run=group_run,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        representative_action_id=plan.representative_action_id,
        artifacts=dict(plan.artifacts),
    )
    await enqueue_group_bundle_run_or_503(
        db=db,
        plan=plan,
        group_run=group_run,
        remediation_run=remediation_run,
        tenant_id=current_user.tenant_id,
        client_factory=boto3.client,
    )

    return CreateActionGroupBundleRunResponse(
        group_run_id=str(group_run.id),
        remediation_run_id=str(remediation_run.id),
        reporting_token=token,
        reporting_callback_url=callback_url,
        status=group_run.status.value,
    )
