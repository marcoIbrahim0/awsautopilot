"""Communication and governance layer API."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_current_user, get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.action import Action
from backend.models.exception import Exception
from backend.models.governance_notification import GovernanceNotification
from backend.models.remediation_run import RemediationRun
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.routers.aws_accounts import get_tenant, resolve_tenant_id
from backend.services.exception_governance import (
    get_exception_lifecycle_status,
    is_reminder_due,
    is_revalidation_due,
    schedule_next_revalidation_at,
    schedule_next_reminder_at,
)
from backend.services.governance_notifications import (
    GovernanceNotificationError,
    dispatch_governance_notification,
)

router = APIRouter(prefix="/governance", tags=["governance"])

GOVERNANCE_CONTRACT_VERSION = "2026-03-02"
_IDEMPOTENCY_MAX_LEN = 128
_STAGE_VALUES = {"pre_change", "in_progress", "action_required", "completion"}
_STATUS_VALUES = {"pending", "sent", "failed", "skipped"}
_CHANNEL_VALUES = {"in_app", "email", "slack", "webhook"}
_RUN_ACTIVE_STATUSES = {"pending", "running", "awaiting_approval"}
_RUN_STATUS_ORDER = ["pending", "running", "awaiting_approval", "success", "failed", "cancelled"]


class GovernanceError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class GovernanceErrorResponse(BaseModel):
    correlation_id: str
    contract_version: str
    error: GovernanceError


class GovernanceNotificationDispatchRequest(BaseModel):
    stage: str = Field(..., description="pre_change | in_progress | action_required | completion")
    detail: str | None = Field(default=None, description="Optional detail rendered across channels")
    action_url: str | None = Field(default=None, description="Optional app URL for action")
    channels: list[str] | None = Field(default=None, description="Optional override channel list")


class GovernanceDispatchSummary(BaseModel):
    delivered: int
    replayed: int
    skipped: int


class GovernanceNotificationDispatchResponse(BaseModel):
    correlation_id: str
    contract_version: str
    run_id: str
    stage: str
    summary: GovernanceDispatchSummary


class GovernanceExceptionUpdateRequest(BaseModel):
    owner_user_id: str | None = Field(default=None, description="Owner user UUID (tenant scoped)")
    approval_metadata: dict[str, Any] | None = Field(default=None, description="Approval metadata")
    reminder_interval_days: int | None = Field(default=None, ge=1, le=365)
    revalidation_interval_days: int | None = Field(default=None, ge=1, le=365)
    expires_at: str | None = Field(default=None, description="Optional ISO8601 expiry override")


class GovernanceExceptionRevalidateRequest(BaseModel):
    detail: str | None = Field(default=None, description="Completion detail for revalidation event")
    expires_at: str | None = Field(default=None, description="Optional new expiry timestamp")


class GovernanceExceptionSnapshot(BaseModel):
    id: str
    owner_user_id: str | None
    approval_metadata: dict[str, Any] | None
    reminder_interval_days: int | None
    next_reminder_at: str | None
    last_reminded_at: str | None
    revalidation_interval_days: int | None
    next_revalidation_at: str | None
    last_revalidated_at: str | None
    expires_at: str
    lifecycle_status: str


class GovernanceExceptionResponse(BaseModel):
    correlation_id: str
    contract_version: str
    exception: GovernanceExceptionSnapshot


class GovernanceReminderDispatchRequest(BaseModel):
    max_items: int = Field(default=50, ge=1, le=500)


class GovernanceReminderDispatchResponse(BaseModel):
    correlation_id: str
    contract_version: str
    processed: int
    delivered: int
    replayed: int
    skipped: int


class GovernanceNotificationItem(BaseModel):
    id: str
    stage: str
    channel: str
    target_type: str
    target_id: str | None
    status: str
    delivered_at: str | None
    created_at: str


class GovernanceNotificationListResponse(BaseModel):
    items: list[GovernanceNotificationItem]
    total: int


class GovernanceRunStatesByAccount(BaseModel):
    account_id: str
    states: dict[str, int]


class GovernanceSLABreachItem(BaseModel):
    run_id: str
    account_id: str
    status: str
    age_minutes: int


class GovernanceComplianceTrendItem(BaseModel):
    day: str
    resolved_actions: int
    successful_runs: int
    expired_exceptions: int


class GovernanceDashboardResponse(BaseModel):
    correlation_id: str
    contract_version: str
    generated_at: str
    run_states_tenant: dict[str, int]
    run_states_by_account: list[GovernanceRunStatesByAccount]
    open_exceptions: dict[str, int]
    sla_breaches: list[GovernanceSLABreachItem]
    compliance_closure_trends: list[GovernanceComplianceTrendItem]


def _ensure_enabled() -> None:
    if not getattr(settings, "COMMUNICATION_GOVERNANCE_ENABLED", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Governance layer disabled")


def _ensure_admin(current_user: User) -> None:
    if getattr(current_user.role, "value", current_user.role) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can perform this operation")


def _new_correlation_id(header_value: str | None) -> str:
    value = (header_value or "").strip()
    return value or uuid.uuid4().hex


def _set_headers(response: Response, correlation_id: str) -> None:
    response.headers["X-Correlation-Id"] = correlation_id
    response.headers["X-Governance-Contract-Version"] = GOVERNANCE_CONTRACT_VERSION


def _validate_contract_header(contract_version_header: str | None) -> None:
    version = (contract_version_header or "").strip()
    if version and version != GOVERNANCE_CONTRACT_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "unsupported_contract_version",
                "detail": f"Expected {GOVERNANCE_CONTRACT_VERSION}",
            },
        )


def _require_idempotency_key(idempotency_key_header: str | None) -> str:
    normalized = (idempotency_key_header or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "missing_idempotency_key", "detail": "Idempotency-Key header is required"},
        )
    if len(normalized) > _IDEMPOTENCY_MAX_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_idempotency_key", "detail": "Idempotency-Key is too long"},
        )
    return normalized


def _parse_optional_uuid(raw_value: str | None, field_name: str) -> uuid.UUID | None:
    if raw_value is None:
        return None
    value = raw_value.strip()
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"invalid_{field_name}", "detail": f"{field_name} must be a valid UUID"},
        ) from exc


def _parse_optional_timestamp(raw_value: str | None, field_name: str) -> datetime | None:
    if raw_value is None:
        return None
    value = raw_value.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"invalid_{field_name}", "detail": f"{field_name} must be ISO8601"},
        ) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _exception_snapshot(exception: Exception) -> GovernanceExceptionSnapshot:
    return GovernanceExceptionSnapshot(
        id=str(exception.id),
        owner_user_id=str(exception.owner_user_id) if exception.owner_user_id else None,
        approval_metadata=exception.approval_metadata if isinstance(exception.approval_metadata, dict) else None,
        reminder_interval_days=exception.reminder_interval_days,
        next_reminder_at=exception.next_reminder_at.isoformat() if exception.next_reminder_at else None,
        last_reminded_at=exception.last_reminded_at.isoformat() if exception.last_reminded_at else None,
        revalidation_interval_days=exception.revalidation_interval_days,
        next_revalidation_at=exception.next_revalidation_at.isoformat() if exception.next_revalidation_at else None,
        last_revalidated_at=exception.last_revalidated_at.isoformat() if exception.last_revalidated_at else None,
        expires_at=exception.expires_at.isoformat(),
        lifecycle_status=get_exception_lifecycle_status(exception),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_channel_override(channels: list[str] | None) -> list[str] | None:
    if channels is None:
        return None
    normalized: list[str] = []
    for channel in channels:
        value = (channel or "").strip()
        if value not in _CHANNEL_VALUES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_channel", "detail": f"Unsupported channel: {value}"},
            )
        if value not in normalized:
            normalized.append(value)
    return normalized


@router.post("/remediation-runs/{run_id}/notifications", response_model=GovernanceNotificationDispatchResponse)
async def notify_remediation_run_stage(
    run_id: Annotated[str, Path(description="Remediation run UUID")],
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: GovernanceNotificationDispatchRequest = Body(...),
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Governance-Contract-Version")] = None,
) -> GovernanceNotificationDispatchResponse:
    _ensure_enabled()
    _ensure_admin(current_user)
    _validate_contract_header(contract_version_header)
    idempotency_key = _require_idempotency_key(idempotency_key_header)

    stage = (body.stage or "").strip()
    if stage not in _STAGE_VALUES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_stage"})

    correlation_id = _new_correlation_id(correlation_id_header)
    _set_headers(response, correlation_id)

    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_run_id"}) from exc

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    run_result = await db.execute(
        select(RemediationRun)
        .where(RemediationRun.id == run_uuid, RemediationRun.tenant_id == current_user.tenant_id)
        .options(selectinload(RemediationRun.action))
    )
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remediation run not found")

    target_label = run.action.title if run.action and run.action.title else f"Remediation run {run.id}"
    action_url = (body.action_url or "").strip() or f"{settings.FRONTEND_URL.rstrip('/')}/remediation-runs/{run.id}"

    try:
        summary = await dispatch_governance_notification(
            db,
            tenant=tenant,
            stage=stage,
            target_type="remediation_run",
            target_id=run.id,
            target_label=target_label,
            detail=body.detail,
            action_url=action_url,
            idempotency_key=idempotency_key,
            channels=_normalize_channel_override(body.channels),
        )
    except GovernanceNotificationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "notification_dispatch_failed", "detail": str(exc)},
        ) from exc

    await db.commit()
    return GovernanceNotificationDispatchResponse(
        correlation_id=correlation_id,
        contract_version=GOVERNANCE_CONTRACT_VERSION,
        run_id=str(run.id),
        stage=stage,
        summary=GovernanceDispatchSummary(
            delivered=summary.delivered,
            replayed=summary.replayed,
            skipped=summary.skipped,
        ),
    )


@router.patch("/exceptions/{exception_id}", response_model=GovernanceExceptionResponse)
async def update_exception_governance(
    exception_id: Annotated[str, Path(description="Exception UUID")],
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: GovernanceExceptionUpdateRequest = Body(...),
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Governance-Contract-Version")] = None,
) -> GovernanceExceptionResponse:
    _ensure_enabled()
    _ensure_admin(current_user)
    _validate_contract_header(contract_version_header)
    _require_idempotency_key(idempotency_key_header)

    correlation_id = _new_correlation_id(correlation_id_header)
    _set_headers(response, correlation_id)

    try:
        exception_uuid = uuid.UUID(exception_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_exception_id"}) from exc

    result = await db.execute(
        select(Exception)
        .where(Exception.id == exception_uuid, Exception.tenant_id == current_user.tenant_id)
        .options(selectinload(Exception.owner), selectinload(Exception.approved_by))
    )
    exception = result.scalar_one_or_none()
    if not exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found")

    owner_uuid = _parse_optional_uuid(body.owner_user_id, "owner_user_id") if body.owner_user_id is not None else None
    if body.owner_user_id is not None:
        if owner_uuid is None:
            exception.owner_user_id = None
        else:
            owner_result = await db.execute(
                select(User).where(User.id == owner_uuid, User.tenant_id == current_user.tenant_id)
            )
            owner = owner_result.scalar_one_or_none()
            if not owner:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "invalid_owner_user_id", "detail": "Owner must belong to tenant"},
                )
            exception.owner_user_id = owner.id

    now = datetime.now(timezone.utc)
    expires_at = _parse_optional_timestamp(body.expires_at, "expires_at") if body.expires_at is not None else None
    if expires_at and expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_expires_at"})
    if expires_at is not None:
        exception.expires_at = expires_at

    if body.approval_metadata is not None:
        approval_metadata = dict(body.approval_metadata)
        approval_metadata["updated_by_user_id"] = str(current_user.id)
        approval_metadata["updated_at"] = now.isoformat()
        exception.approval_metadata = approval_metadata

    if body.reminder_interval_days is not None:
        exception.reminder_interval_days = body.reminder_interval_days
    if body.revalidation_interval_days is not None:
        exception.revalidation_interval_days = body.revalidation_interval_days

    if body.reminder_interval_days is not None or expires_at is not None:
        exception.next_reminder_at = schedule_next_reminder_at(
            expires_at=exception.expires_at,
            interval_days=exception.reminder_interval_days,
            now=now,
            last_reminded_at=exception.last_reminded_at,
        )
    if body.revalidation_interval_days is not None or expires_at is not None:
        exception.next_revalidation_at = schedule_next_revalidation_at(
            expires_at=exception.expires_at,
            interval_days=exception.revalidation_interval_days,
            now=now,
            last_revalidated_at=exception.last_revalidated_at,
        )

    await db.commit()
    await db.refresh(exception)

    return GovernanceExceptionResponse(
        correlation_id=correlation_id,
        contract_version=GOVERNANCE_CONTRACT_VERSION,
        exception=_exception_snapshot(exception),
    )


@router.post("/exceptions/{exception_id}/revalidate", response_model=GovernanceExceptionResponse)
async def revalidate_exception(
    exception_id: Annotated[str, Path(description="Exception UUID")],
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: GovernanceExceptionRevalidateRequest = Body(default_factory=GovernanceExceptionRevalidateRequest),
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Governance-Contract-Version")] = None,
) -> GovernanceExceptionResponse:
    _ensure_enabled()
    _ensure_admin(current_user)
    _validate_contract_header(contract_version_header)
    idempotency_key = _require_idempotency_key(idempotency_key_header)

    correlation_id = _new_correlation_id(correlation_id_header)
    _set_headers(response, correlation_id)

    try:
        exception_uuid = uuid.UUID(exception_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_exception_id"}) from exc

    result = await db.execute(
        select(Exception)
        .where(Exception.id == exception_uuid, Exception.tenant_id == current_user.tenant_id)
        .options(selectinload(Exception.owner), selectinload(Exception.approved_by))
    )
    exception = result.scalar_one_or_none()
    if not exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found")

    now = datetime.now(timezone.utc)
    expires_override = _parse_optional_timestamp(body.expires_at, "expires_at") if body.expires_at is not None else None
    if expires_override is not None:
        if expires_override <= now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_expires_at"})
        exception.expires_at = expires_override

    exception.last_revalidated_at = now
    exception.next_revalidation_at = schedule_next_revalidation_at(
        expires_at=exception.expires_at,
        interval_days=exception.revalidation_interval_days,
        now=now,
        last_revalidated_at=now,
    )

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    detail = (body.detail or "").strip() or "Exception was revalidated by owner/admin."
    try:
        await dispatch_governance_notification(
            db,
            tenant=tenant,
            stage="completion",
            target_type="exception",
            target_id=exception.id,
            target_label=f"Exception {exception.id}",
            detail=detail,
            action_url=f"{settings.FRONTEND_URL.rstrip('/')}/exceptions",
            idempotency_key=f"{idempotency_key}:revalidate",
            channels=None,
        )
    except GovernanceNotificationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "notification_dispatch_failed", "detail": str(exc)},
        ) from exc

    await db.commit()
    await db.refresh(exception)

    return GovernanceExceptionResponse(
        correlation_id=correlation_id,
        contract_version=GOVERNANCE_CONTRACT_VERSION,
        exception=_exception_snapshot(exception),
    )


@router.post("/exceptions/reminders/dispatch", response_model=GovernanceReminderDispatchResponse)
async def dispatch_due_exception_reminders(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: GovernanceReminderDispatchRequest = Body(default_factory=GovernanceReminderDispatchRequest),
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Governance-Contract-Version")] = None,
) -> GovernanceReminderDispatchResponse:
    _ensure_enabled()
    _ensure_admin(current_user)
    _validate_contract_header(contract_version_header)
    idempotency_key = _require_idempotency_key(idempotency_key_header)

    correlation_id = _new_correlation_id(correlation_id_header)
    _set_headers(response, correlation_id)

    max_items = min(body.max_items, int(getattr(settings, "COMMUNICATION_GOVERNANCE_REMINDER_BATCH_LIMIT", 100) or 100))
    now = datetime.now(timezone.utc)

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    due_result = await db.execute(
        select(Exception)
        .where(Exception.tenant_id == current_user.tenant_id)
        .where(
            or_(
                Exception.expires_at <= now,
                and_(Exception.next_reminder_at.is_not(None), Exception.next_reminder_at <= now),
                and_(Exception.next_revalidation_at.is_not(None), Exception.next_revalidation_at <= now),
            )
        )
        .order_by(Exception.expires_at.asc())
        .limit(max_items)
    )
    exceptions = due_result.scalars().all()

    processed = 0
    delivered = 0
    replayed = 0
    skipped = 0
    for exception in exceptions:
        lifecycle = get_exception_lifecycle_status(exception, now=now)
        detail = (
            "Exception expired and must be resolved immediately."
            if lifecycle == "expired"
            else "Exception needs governance action (reminder/revalidation due)."
        )
        suffix_dt = exception.next_reminder_at or exception.next_revalidation_at or exception.expires_at
        suffix = suffix_dt.isoformat() if suffix_dt else "no-schedule"
        event_key = f"{idempotency_key}:{exception.id}:{lifecycle}:{suffix}"

        try:
            summary = await dispatch_governance_notification(
                db,
                tenant=tenant,
                stage="action_required",
                target_type="exception",
                target_id=exception.id,
                target_label=f"Exception {exception.id}",
                detail=detail,
                action_url=f"{settings.FRONTEND_URL.rstrip('/')}/exceptions",
                idempotency_key=event_key,
                channels=None,
            )
        except GovernanceNotificationError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"error": "notification_dispatch_failed", "detail": str(exc)},
            ) from exc

        processed += 1
        delivered += summary.delivered
        replayed += summary.replayed
        skipped += summary.skipped

        if is_reminder_due(exception, now=now):
            exception.last_reminded_at = now
            exception.next_reminder_at = schedule_next_reminder_at(
                expires_at=exception.expires_at,
                interval_days=exception.reminder_interval_days,
                now=now,
                last_reminded_at=now,
            )
        if is_revalidation_due(exception, now=now):
            exception.next_revalidation_at = schedule_next_revalidation_at(
                expires_at=exception.expires_at,
                interval_days=exception.revalidation_interval_days,
                now=now,
                last_revalidated_at=exception.last_revalidated_at,
            )

    await db.commit()
    return GovernanceReminderDispatchResponse(
        correlation_id=correlation_id,
        contract_version=GOVERNANCE_CONTRACT_VERSION,
        processed=processed,
        delivered=delivered,
        replayed=replayed,
        skipped=skipped,
    )


@router.get("/notifications", response_model=GovernanceNotificationListResponse)
async def list_governance_notifications(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    tenant_id: Annotated[str | None, Query(description="Tenant UUID when unauthenticated local mode")] = None,
    channel: Annotated[str | None, Query(description="Optional channel filter")] = "in_app",
    status_filter: Annotated[str | None, Query(alias="status", description="pending|sent|failed|skipped")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Governance-Contract-Version")] = None,
) -> GovernanceNotificationListResponse:
    _ensure_enabled()
    _validate_contract_header(contract_version_header)
    correlation_id = _new_correlation_id(correlation_id_header)
    _set_headers(response, correlation_id)

    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    query = select(GovernanceNotification).where(GovernanceNotification.tenant_id == tenant_uuid)
    if channel is not None:
        channel_value = (channel or "").strip()
        if channel_value not in _CHANNEL_VALUES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_channel"})
        query = query.where(GovernanceNotification.channel == channel_value)
    if status_filter is not None:
        status_value = (status_filter or "").strip()
        if status_value not in _STATUS_VALUES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_status"})
        query = query.where(GovernanceNotification.status == status_value)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0

    rows_result = await db.execute(
        query.order_by(GovernanceNotification.created_at.desc()).limit(limit).offset(offset)
    )
    rows = rows_result.scalars().all()

    items = [
        GovernanceNotificationItem(
            id=str(row.id),
            stage=row.stage,
            channel=row.channel,
            target_type=row.target_type,
            target_id=str(row.target_id) if row.target_id else None,
            status=row.status,
            delivered_at=row.delivered_at.isoformat() if row.delivered_at else None,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]
    return GovernanceNotificationListResponse(items=items, total=total)


@router.get("/dashboard", response_model=GovernanceDashboardResponse)
async def governance_dashboard(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    tenant_id: Annotated[str | None, Query(description="Tenant UUID when unauthenticated local mode")] = None,
    window_days: Annotated[int, Query(ge=7, le=90)] = 14,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Governance-Contract-Version")] = None,
) -> GovernanceDashboardResponse:
    _ensure_enabled()
    _validate_contract_header(contract_version_header)
    correlation_id = _new_correlation_id(correlation_id_header)
    _set_headers(response, correlation_id)

    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    now = datetime.now(timezone.utc)
    start_day = (now - timedelta(days=window_days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    sla_minutes = max(1, int(getattr(settings, "COMMUNICATION_GOVERNANCE_SLA_BREACH_MINUTES", 120) or 120))

    tenant_states = {status_name: 0 for status_name in _RUN_STATUS_ORDER}
    account_states: dict[str, dict[str, int]] = {}
    run_state_rows = await db.execute(
        select(Action.account_id, RemediationRun.status)
        .select_from(RemediationRun)
        .join(Action, RemediationRun.action_id == Action.id, isouter=True)
        .where(RemediationRun.tenant_id == tenant_uuid)
    )
    for account_id, run_status in run_state_rows.all():
        status_value = getattr(run_status, "value", str(run_status))
        if status_value not in tenant_states:
            continue
        tenant_states[status_value] += 1
        account_key = account_id or "unknown"
        if account_key not in account_states:
            account_states[account_key] = {name: 0 for name in _RUN_STATUS_ORDER}
        account_states[account_key][status_value] += 1

    exceptions_result = await db.execute(select(Exception).where(Exception.tenant_id == tenant_uuid))
    exceptions_rows = exceptions_result.scalars().all()
    open_exceptions_count = 0
    action_required_count = 0
    expiring_count = 0
    for exception in exceptions_rows:
        lifecycle = get_exception_lifecycle_status(exception, now=now)
        if lifecycle in {"active", "expiring", "action_required"}:
            open_exceptions_count += 1
        if lifecycle == "action_required":
            action_required_count += 1
        if lifecycle == "expiring":
            expiring_count += 1

    breach_cutoff = now - timedelta(minutes=sla_minutes)
    breach_rows = await db.execute(
        select(RemediationRun, Action.account_id)
        .select_from(RemediationRun)
        .join(Action, RemediationRun.action_id == Action.id, isouter=True)
        .where(RemediationRun.tenant_id == tenant_uuid)
        .where(RemediationRun.status.in_(_RUN_ACTIVE_STATUSES))
        .where(RemediationRun.created_at <= breach_cutoff)
        .order_by(RemediationRun.created_at.asc())
        .limit(200)
    )
    sla_breaches = []
    for run, account_id in breach_rows.all():
        age_minutes = int((now - run.created_at).total_seconds() // 60)
        sla_breaches.append(
            GovernanceSLABreachItem(
                run_id=str(run.id),
                account_id=account_id or "unknown",
                status=getattr(run.status, "value", str(run.status)),
                age_minutes=age_minutes,
            )
        )

    trend_map: dict[str, GovernanceComplianceTrendItem] = {}
    for day_offset in range(window_days):
        day = (start_day + timedelta(days=day_offset)).date().isoformat()
        trend_map[day] = GovernanceComplianceTrendItem(
            day=day,
            resolved_actions=0,
            successful_runs=0,
            expired_exceptions=0,
        )

    action_rows = await db.execute(
        select(Action.updated_at, Action.status)
        .where(Action.tenant_id == tenant_uuid)
        .where(Action.updated_at >= start_day)
    )
    for updated_at, action_status in action_rows.all():
        status_value = getattr(action_status, "value", str(action_status))
        if status_value not in {"resolved", "suppressed"}:
            continue
        day_key = _as_utc(updated_at).date().isoformat()
        if day_key in trend_map:
            trend_map[day_key].resolved_actions += 1

    run_rows = await db.execute(
        select(RemediationRun.completed_at, RemediationRun.status)
        .where(RemediationRun.tenant_id == tenant_uuid)
        .where(RemediationRun.completed_at.is_not(None))
        .where(RemediationRun.completed_at >= start_day)
    )
    for completed_at, run_status in run_rows.all():
        status_value = getattr(run_status, "value", str(run_status))
        if status_value != "success":
            continue
        day_key = _as_utc(completed_at).date().isoformat()
        if day_key in trend_map:
            trend_map[day_key].successful_runs += 1

    expired_rows = await db.execute(
        select(Exception.expires_at)
        .where(Exception.tenant_id == tenant_uuid)
        .where(Exception.expires_at >= start_day)
        .where(Exception.expires_at <= now)
    )
    for (expires_at,) in expired_rows.all():
        day_key = _as_utc(expires_at).date().isoformat()
        if day_key in trend_map:
            trend_map[day_key].expired_exceptions += 1

    by_account = [
        GovernanceRunStatesByAccount(account_id=account_id, states=states)
        for account_id, states in sorted(account_states.items(), key=lambda item: item[0])
    ]
    trend_items = [trend_map[key] for key in sorted(trend_map.keys())]

    return GovernanceDashboardResponse(
        correlation_id=correlation_id,
        contract_version=GOVERNANCE_CONTRACT_VERSION,
        generated_at=now.isoformat(),
        run_states_tenant=tenant_states,
        run_states_by_account=by_account,
        open_exceptions={
            "open_total": open_exceptions_count,
            "action_required": action_required_count,
            "expiring": expiring_count,
        },
        sla_breaches=sla_breaches,
        compliance_closure_trends=trend_items,
    )
