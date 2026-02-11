from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

import boto3
from botocore.exceptions import ClientError
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
from backend.models.enums import ActionGroupRunStatus, RemediationRunMode, RemediationRunStatus
from backend.models.remediation_run import RemediationRun
from backend.models.user import User
from backend.routers.aws_accounts import get_tenant, resolve_tenant_id
from backend.services.action_groups import get_group_detail, list_groups_with_counters
from backend.services.bundle_reporting_tokens import issue_group_run_reporting_token
from backend.utils.sqs import build_remediation_run_job_payload, parse_queue_region

router = APIRouter(prefix="/action-groups", tags=["action-groups"])


class ActionGroupCountersResponse(BaseModel):
    run_successful: int
    run_not_successful: int
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


class ActionGroupRunsResponse(BaseModel):
    items: list[ActionGroupRunListItemResponse]
    total: int


class CreateActionGroupBundleRunRequest(BaseModel):
    strategy_id: str | None = None
    strategy_inputs: dict[str, Any] | None = None
    risk_acknowledged: bool = False
    pr_bundle_variant: str | None = None


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
    await get_tenant(tenant_uuid, db)
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
                latest_run=ActionGroupMemberLatestRunResponse(
                    id=member.get("latest_run_id"),
                    status=member.get("latest_run_status"),
                    started_at=_as_iso(member.get("latest_run_started_at")),
                    finished_at=_as_iso(member.get("latest_run_finished_at")),
                ),
            )
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
            not_run_yet=int(counters.get("not_run_yet") or 0),
            total_actions=int(counters.get("total_actions") or 0),
        ),
        members=members,
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

    items = [
        ActionGroupRunListItemResponse(
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
        )
        for row in rows
    ]
    return ActionGroupRunsResponse(items=items, total=total)


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
    try:
        group_uuid = uuid.UUID(group_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group_id") from exc
    request_body = body or CreateActionGroupBundleRunRequest()

    group = (
        await db.execute(
            select(ActionGroup).where(ActionGroup.id == group_uuid, ActionGroup.tenant_id == current_user.tenant_id)
        )
    ).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action group not found")

    action_rows = (
        await db.execute(
            select(Action)
            .join(
                ActionGroupMembership,
                (ActionGroupMembership.action_id == Action.id)
                & (ActionGroupMembership.tenant_id == Action.tenant_id),
            )
            .where(
                ActionGroupMembership.tenant_id == current_user.tenant_id,
                ActionGroupMembership.group_id == group.id,
            )
            .order_by(Action.priority.desc(), Action.updated_at.desc().nullslast(), Action.created_at.desc())
        )
    ).scalars().all()
    if not action_rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action group has no members")

    representative = action_rows[0]
    action_ids = [action.id for action in action_rows]

    group_run_id = uuid.uuid4()
    group_run = ActionGroupRun(
        id=group_run_id,
        tenant_id=current_user.tenant_id,
        group_id=group.id,
        initiated_by_user_id=current_user.id,
        mode="download_bundle",
        status=ActionGroupRunStatus.queued,
        reporting_source="system",
    )
    callback_url = f"{settings.API_PUBLIC_URL.rstrip('/')}/api/internal/group-runs/report"
    token, token_jti, _ = issue_group_run_reporting_token(
        tenant_id=current_user.tenant_id,
        group_run_id=group_run.id,
        group_id=group.id,
        allowed_action_ids=action_ids,
    )
    group_run.report_token_jti = token_jti

    artifacts: dict[str, Any] = {
        "group_bundle": {
            "group_id": str(group.id),
            "group_key": group.group_key,
            "action_type": group.action_type,
            "account_id": group.account_id,
            "region": group.region,
            "action_count": len(action_ids),
            "action_ids": [str(action_id) for action_id in action_ids],
            "group_run_id": str(group_run.id),
            "reporting": {
                "callback_url": callback_url,
                "token": token,
                "reporting_source": "bundle_callback",
            },
        }
    }
    if request_body.strategy_id:
        artifacts["selected_strategy"] = request_body.strategy_id
    if request_body.strategy_inputs:
        artifacts["strategy_inputs"] = request_body.strategy_inputs
    if request_body.risk_acknowledged:
        artifacts["risk_acknowledged"] = True
    if request_body.pr_bundle_variant:
        artifacts["pr_bundle_variant"] = request_body.pr_bundle_variant

    remediation_run = RemediationRun(
        tenant_id=current_user.tenant_id,
        action_id=representative.id,
        mode=RemediationRunMode.pr_only,
        status=RemediationRunStatus.pending,
        approved_by_user_id=current_user.id,
        artifacts=artifacts,
    )
    db.add(group_run)
    db.add(remediation_run)
    await db.flush()
    group_run.remediation_run_id = remediation_run.id
    await db.commit()
    await db.refresh(group_run)
    await db.refresh(remediation_run)

    payload = build_remediation_run_job_payload(
        run_id=remediation_run.id,
        tenant_id=current_user.tenant_id,
        action_id=representative.id,
        mode=remediation_run.mode.value,
        created_at=datetime.now(timezone.utc).isoformat(),
        pr_bundle_variant=request_body.pr_bundle_variant,
        strategy_id=request_body.strategy_id,
        strategy_inputs=request_body.strategy_inputs,
        risk_acknowledged=request_body.risk_acknowledged,
        group_action_ids=action_ids,
    )
    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    sqs = boto3.client("sqs", region_name=parse_queue_region(queue_url))
    try:
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not enqueue group bundle run job.",
        ) from exc

    return CreateActionGroupBundleRunResponse(
        group_run_id=str(group_run.id),
        remediation_run_id=str(remediation_run.id),
        reporting_token=token,
        reporting_callback_url=callback_url,
        status=group_run.status.value,
    )
