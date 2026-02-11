from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.aws_account import AwsAccount
from backend.models.aws_account_reconcile_settings import AwsAccountReconcileSettings
from backend.models.finding import Finding
from backend.models.tenant import Tenant
from backend.models.tenant_reconcile_run import TenantReconcileRun
from backend.models.tenant_reconcile_run_shard import TenantReconcileRunShard
from backend.models.user import User
from backend.routers.aws_accounts import get_account_for_tenant, get_tenant, resolve_tenant_id
from backend.services.tenant_reconciliation import (
    create_reconciliation_run,
    ensure_tenant_reconciliation_enabled,
    normalize_max_resources,
    normalize_regions,
    normalize_services,
    normalize_sweep_mode,
    run_preflight_for_services,
)

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])

_ACCESS_DENIED_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedAccess",
    "UnauthorizedOperation",
}


def _status_value(raw: object) -> str:
    if raw is None:
        return ""
    value = getattr(raw, "value", None)
    if isinstance(value, str):
        return value
    return str(raw)


def _dt_iso(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class ReconciliationPreflightRequest(BaseModel):
    account_id: str = Field(..., pattern=r"^\d{12}$")
    regions: list[str] | None = None
    services: list[str] | None = None


class ServicePreflightResult(BaseModel):
    service: str
    ok: bool
    missing_permissions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReconciliationPreflightResponse(BaseModel):
    account_id: str
    region_used: str
    services: list[str]
    ok: bool
    assume_role_ok: bool
    assume_role_error: str | None = None
    missing_permissions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    service_checks: list[ServicePreflightResult] = Field(default_factory=list)


class ReconciliationRunRequest(BaseModel):
    account_id: str = Field(..., pattern=r"^\d{12}$")
    regions: list[str] | None = None
    services: list[str] | None = None
    max_resources: int | None = Field(default=None, ge=1, le=5000)
    sweep_mode: str | None = Field(default="global")
    require_preflight_pass: bool = True
    force: bool = False


class ReconciliationRunResponse(BaseModel):
    run_id: str
    account_id: str
    status: str
    submitted_at: str
    total_shards: int
    enqueued_shards: int
    failed_shards: int
    preflight: ReconciliationPreflightResponse | None = None


class ReconciliationRunItem(BaseModel):
    id: str
    account_id: str
    trigger_type: str
    status: str
    services: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    sweep_mode: str
    max_resources: int | None = None
    total_shards: int
    enqueued_shards: int
    running_shards: int
    succeeded_shards: int
    failed_shards: int
    last_error: str | None = None
    submitted_at: str
    started_at: str | None = None
    completed_at: str | None = None


class ReconciliationAlert(BaseModel):
    code: str
    count: int
    detail: str


class ReconciliationStatusSummary(BaseModel):
    total_runs: int
    queued_runs: int
    running_runs: int
    succeeded_runs: int
    partial_failed_runs: int
    failed_runs: int
    success_rate: float
    lag_since_last_success_minutes: float | None = None
    last_error: str | None = None
    failure_reasons: dict[str, int] = Field(default_factory=dict)
    alerts: list[ReconciliationAlert] = Field(default_factory=list)


class ReconciliationStatusResponse(BaseModel):
    generated_at: str
    account_id: str | None = None
    summary: ReconciliationStatusSummary
    runs: list[ReconciliationRunItem] = Field(default_factory=list)


class CoverageTopControl(BaseModel):
    control_id: str
    unmatched_count: int


class ReconciliationCoverageResponse(BaseModel):
    generated_at: str
    account_id: str | None = None
    in_scope_total: int
    in_scope_matched: int
    in_scope_unmatched: int
    coverage_rate: float
    in_scope_new_total: int
    in_scope_new_matched: int
    in_scope_new_coverage_rate: float
    top_unmatched_controls: list[CoverageTopControl] = Field(default_factory=list)


class ReconciliationSettingsResponse(BaseModel):
    account_id: str
    enabled: bool
    interval_minutes: int
    services: list[str]
    regions: list[str]
    max_resources: int
    sweep_mode: str
    cooldown_minutes: int
    last_enqueued_at: str | None = None
    last_run_id: str | None = None


class ReconciliationSettingsUpdateRequest(BaseModel):
    enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=10080)
    services: list[str] | None = None
    regions: list[str] | None = None
    max_resources: int | None = Field(default=None, ge=1, le=5000)
    sweep_mode: str | None = None
    cooldown_minutes: int | None = Field(default=None, ge=1, le=1440)


async def _resolve_tenant_and_account(
    *,
    db: AsyncSession,
    account_id: str,
    current_user: Optional[User],
    tenant_id: Optional[str],
) -> tuple[uuid.UUID, Tenant, AwsAccount]:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant(tenant_uuid, db)
    account = await get_account_for_tenant(tenant_uuid, account_id, db)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AWS account {account_id} not found for tenant",
        )
    return tenant_uuid, tenant, account


def _settings_response_from_row(
    *,
    account: AwsAccount,
    settings_row: AwsAccountReconcileSettings | None,
) -> ReconciliationSettingsResponse:
    default_services = settings.control_plane_inventory_services_list
    default_regions = account.regions or [settings.AWS_REGION]
    default_max_resources = int(settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD or 500)
    if settings_row is None:
        return ReconciliationSettingsResponse(
            account_id=account.account_id,
            enabled=False,
            interval_minutes=max(60, int(settings.TENANT_RECONCILIATION_SCHEDULE_MIN_INTERVAL_MINUTES)),
            services=default_services,
            regions=default_regions,
            max_resources=default_max_resources,
            sweep_mode="global",
            cooldown_minutes=30,
            last_enqueued_at=None,
            last_run_id=None,
        )
    return ReconciliationSettingsResponse(
        account_id=account.account_id,
        enabled=bool(settings_row.enabled),
        interval_minutes=int(settings_row.interval_minutes),
        services=[str(value) for value in (settings_row.services or default_services)],
        regions=[str(value) for value in (settings_row.regions or default_regions)],
        max_resources=int(settings_row.max_resources or default_max_resources),
        sweep_mode=normalize_sweep_mode(settings_row.sweep_mode),
        cooldown_minutes=int(settings_row.cooldown_minutes or 30),
        last_enqueued_at=_dt_iso(settings_row.last_enqueued_at),
        last_run_id=str(settings_row.last_run_id) if settings_row.last_run_id else None,
    )


@router.post(
    "/preflight",
    response_model=ReconciliationPreflightResponse,
    status_code=status.HTTP_200_OK,
)
async def preflight_reconciliation(
    body: ReconciliationPreflightRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> ReconciliationPreflightResponse:
    tenant_uuid, tenant, account = await _resolve_tenant_and_account(
        db=db,
        account_id=body.account_id,
        current_user=current_user,
        tenant_id=tenant_id,
    )
    ensure_tenant_reconciliation_enabled(tenant_uuid)

    services = normalize_services(body.services)
    regions = normalize_regions(body.regions, account.regions)
    result = await run_preflight_for_services(
        account=account,
        tenant=tenant,
        services=services,
        regions=regions,
    )
    service_checks = [
        ServicePreflightResult(
            service=str(item.get("service") or ""),
            ok=bool(item.get("ok")),
            missing_permissions=[str(v) for v in (item.get("missing_permissions") or [])],
            warnings=[str(v) for v in (item.get("warnings") or [])],
        )
        for item in (result.get("service_checks") or [])
        if isinstance(item, dict)
    ]
    return ReconciliationPreflightResponse(
        account_id=account.account_id,
        region_used=(regions or [settings.AWS_REGION])[0],
        services=services,
        ok=bool(result.get("ok")),
        assume_role_ok=bool(result.get("assume_role_ok")),
        assume_role_error=(str(result.get("assume_role_error")) if result.get("assume_role_error") else None),
        missing_permissions=[str(v) for v in (result.get("missing_permissions") or [])],
        warnings=[str(v) for v in (result.get("warnings") or [])],
        service_checks=service_checks,
    )


@router.post(
    "/run",
    response_model=ReconciliationRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_reconciliation(
    body: ReconciliationRunRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> ReconciliationRunResponse:
    tenant_uuid, tenant, account = await _resolve_tenant_and_account(
        db=db,
        account_id=body.account_id,
        current_user=current_user,
        tenant_id=tenant_id,
    )
    ensure_tenant_reconciliation_enabled(tenant_uuid)

    status_value = _status_value(account.status).lower()
    if status_value != "validated":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account must be validated before starting reconciliation.",
        )

    services = normalize_services(body.services)
    regions = normalize_regions(body.regions, account.regions)
    max_resources = normalize_max_resources(body.max_resources)
    sweep_mode = normalize_sweep_mode(body.sweep_mode)

    preflight_response: ReconciliationPreflightResponse | None = None
    if body.require_preflight_pass:
        preflight_result = await run_preflight_for_services(
            account=account,
            tenant=tenant,
            services=services,
            regions=regions,
        )
        preflight_response = ReconciliationPreflightResponse(
            account_id=account.account_id,
            region_used=(regions or [settings.AWS_REGION])[0],
            services=services,
            ok=bool(preflight_result.get("ok")),
            assume_role_ok=bool(preflight_result.get("assume_role_ok")),
            assume_role_error=(
                str(preflight_result.get("assume_role_error")) if preflight_result.get("assume_role_error") else None
            ),
            missing_permissions=[str(v) for v in (preflight_result.get("missing_permissions") or [])],
            warnings=[str(v) for v in (preflight_result.get("warnings") or [])],
            service_checks=[
                ServicePreflightResult(
                    service=str(item.get("service") or ""),
                    ok=bool(item.get("ok")),
                    missing_permissions=[str(v) for v in (item.get("missing_permissions") or [])],
                    warnings=[str(v) for v in (item.get("warnings") or [])],
                )
                for item in (preflight_result.get("service_checks") or [])
                if isinstance(item, dict)
            ],
        )
        if not preflight_response.ok:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "preflight_failed",
                    "message": "Preflight failed. Fix IAM permissions or submit with require_preflight_pass=false.",
                    "preflight": preflight_response.model_dump(),
                },
            )

    run = await create_reconciliation_run(
        db=db,
        tenant=tenant,
        account=account,
        requested_by=current_user,
        trigger_type="manual",
        services=services,
        regions=regions,
        sweep_mode=sweep_mode,
        max_resources=max_resources,
        cooldown_seconds=0 if body.force else int(settings.TENANT_RECONCILIATION_COOLDOWN_SECONDS or 0),
    )
    return ReconciliationRunResponse(
        run_id=str(run.id),
        account_id=run.account_id,
        status=run.status,
        submitted_at=run.submitted_at.isoformat() if run.submitted_at else datetime.now(timezone.utc).isoformat(),
        total_shards=int(run.total_shards or 0),
        enqueued_shards=int(run.enqueued_shards or 0),
        failed_shards=int(run.failed_shards or 0),
        preflight=preflight_response,
    )


@router.get(
    "/status",
    response_model=ReconciliationStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_reconciliation_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    account_id: Annotated[str | None, Query(pattern=r"^\d{12}$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReconciliationStatusResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)
    ensure_tenant_reconciliation_enabled(tenant_uuid)

    if account_id:
        account = await get_account_for_tenant(tenant_uuid, account_id, db)
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AWS account not found for tenant.")

    filters = [TenantReconcileRun.tenant_id == tenant_uuid]
    if account_id:
        filters.append(TenantReconcileRun.account_id == account_id)

    run_rows = (
        await db.execute(
            select(TenantReconcileRun)
            .where(*filters)
            .order_by(TenantReconcileRun.submitted_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    runs = [
        ReconciliationRunItem(
            id=str(row.id),
            account_id=row.account_id,
            trigger_type=row.trigger_type,
            status=row.status,
            services=[str(v) for v in (row.services or [])],
            regions=[str(v) for v in (row.regions or [])],
            sweep_mode=row.sweep_mode,
            max_resources=row.max_resources,
            total_shards=int(row.total_shards or 0),
            enqueued_shards=int(row.enqueued_shards or 0),
            running_shards=int(row.running_shards or 0),
            succeeded_shards=int(row.succeeded_shards or 0),
            failed_shards=int(row.failed_shards or 0),
            last_error=row.last_error,
            submitted_at=row.submitted_at.isoformat() if row.submitted_at else datetime.now(timezone.utc).isoformat(),
            started_at=_dt_iso(row.started_at),
            completed_at=_dt_iso(row.completed_at),
        )
        for row in run_rows
    ]

    status_rows = (
        await db.execute(
            select(TenantReconcileRun.status, func.count())
            .where(*filters)
            .group_by(TenantReconcileRun.status)
        )
    ).all()
    status_counts = {str(raw_status or ""): int(count or 0) for raw_status, count in status_rows}
    total_runs = int(sum(status_counts.values()))
    queued_runs = int(status_counts.get("queued", 0))
    running_runs = int(status_counts.get("running", 0))
    succeeded_runs = int(status_counts.get("succeeded", 0))
    partial_failed_runs = int(status_counts.get("partial_failed", 0))
    failed_runs = int(status_counts.get("failed", 0))

    completed_runs = succeeded_runs + partial_failed_runs + failed_runs
    success_rate = float(succeeded_runs / completed_runs) if completed_runs > 0 else 0.0

    last_success = (
        await db.execute(
            select(func.max(TenantReconcileRun.completed_at))
            .where(*filters, TenantReconcileRun.status == "succeeded")
        )
    ).scalar()
    lag_since_last_success_minutes: float | None = None
    if isinstance(last_success, datetime):
        lag_since_last_success_minutes = max(
            0.0,
            float((datetime.now(timezone.utc) - last_success).total_seconds() / 60.0),
        )

    last_error = (
        await db.execute(
            select(TenantReconcileRun.last_error)
            .where(*filters, TenantReconcileRun.last_error.isnot(None), TenantReconcileRun.last_error != "")
            .order_by(TenantReconcileRun.submitted_at.desc())
            .limit(1)
        )
    ).scalar()

    failure_reason_filters = [TenantReconcileRun.tenant_id == tenant_uuid]
    if account_id:
        failure_reason_filters.append(TenantReconcileRun.account_id == account_id)
    failure_reason_rows = (
        await db.execute(
            select(TenantReconcileRunShard.error_code, func.count())
            .join(TenantReconcileRun, TenantReconcileRunShard.run_id == TenantReconcileRun.id)
            .where(
                *failure_reason_filters,
                TenantReconcileRunShard.status == "failed",
                TenantReconcileRunShard.error_code.isnot(None),
            )
            .group_by(TenantReconcileRunShard.error_code)
            .order_by(desc(func.count()))
        )
    ).all()
    failure_reasons = {str(code): int(count or 0) for code, count in failure_reason_rows if code}

    assume_role_failures = sum(
        count for code, count in failure_reasons.items() if str(code).lower().startswith("assumerole:")
    )
    permission_denials = sum(
        count for code, count in failure_reasons.items() if code in _ACCESS_DENIED_CODES
    )
    alert_threshold = max(1, int(settings.TENANT_RECONCILIATION_ALERT_FAILURE_THRESHOLD or 3))
    alerts: list[ReconciliationAlert] = []
    if assume_role_failures >= alert_threshold:
        alerts.append(
            ReconciliationAlert(
                code="repeated_assume_role_failures",
                count=assume_role_failures,
                detail="Repeated AssumeRole failures detected across reconciliation shards.",
            )
        )
    if permission_denials >= alert_threshold:
        alerts.append(
            ReconciliationAlert(
                code="repeated_inventory_permission_denials",
                count=permission_denials,
                detail="Repeated inventory permission denials detected across reconciliation shards.",
            )
        )

    summary = ReconciliationStatusSummary(
        total_runs=total_runs,
        queued_runs=queued_runs,
        running_runs=running_runs,
        succeeded_runs=succeeded_runs,
        partial_failed_runs=partial_failed_runs,
        failed_runs=failed_runs,
        success_rate=success_rate,
        lag_since_last_success_minutes=lag_since_last_success_minutes,
        last_error=(str(last_error) if last_error else None),
        failure_reasons=failure_reasons,
        alerts=alerts,
    )
    return ReconciliationStatusResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        account_id=account_id,
        summary=summary,
        runs=runs,
    )


@router.get(
    "/coverage",
    response_model=ReconciliationCoverageResponse,
    status_code=status.HTTP_200_OK,
)
async def get_reconciliation_coverage(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    account_id: Annotated[str | None, Query(pattern=r"^\d{12}$")] = None,
) -> ReconciliationCoverageResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)
    ensure_tenant_reconciliation_enabled(tenant_uuid)

    if account_id:
        account = await get_account_for_tenant(tenant_uuid, account_id, db)
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AWS account not found for tenant.")

    finding_filters = [
        Finding.tenant_id == tenant_uuid,
        Finding.source == "security_hub",
        Finding.in_scope.is_(True),
    ]
    if account_id:
        finding_filters.append(Finding.account_id == account_id)

    in_scope_total = int((await db.execute(select(func.count()).select_from(Finding).where(*finding_filters))).scalar() or 0)
    in_scope_matched = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Finding)
                .where(
                    *finding_filters,
                    Finding.shadow_fingerprint.isnot(None),
                    Finding.shadow_fingerprint != "",
                )
            )
        ).scalar()
        or 0
    )
    in_scope_unmatched = max(0, in_scope_total - in_scope_matched)
    coverage_rate = float(in_scope_matched / in_scope_total) if in_scope_total > 0 else 0.0

    in_scope_new_total = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Finding)
                .where(*finding_filters, Finding.status.in_(("NEW", "NOTIFIED")))
            )
        ).scalar()
        or 0
    )
    in_scope_new_matched = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Finding)
                .where(
                    *finding_filters,
                    Finding.status.in_(("NEW", "NOTIFIED")),
                    Finding.shadow_fingerprint.isnot(None),
                    Finding.shadow_fingerprint != "",
                )
            )
        ).scalar()
        or 0
    )
    in_scope_new_coverage_rate = float(in_scope_new_matched / in_scope_new_total) if in_scope_new_total > 0 else 0.0

    top_unmatched_rows = (
        await db.execute(
            select(func.coalesce(Finding.canonical_control_id, Finding.control_id), func.count())
            .where(
                *finding_filters,
                or_(Finding.shadow_fingerprint.is_(None), Finding.shadow_fingerprint == ""),
            )
            .group_by(func.coalesce(Finding.canonical_control_id, Finding.control_id))
            .order_by(desc(func.count()))
            .limit(10)
        )
    ).all()
    top_unmatched_controls = [
        CoverageTopControl(control_id=str(control_id or "UNKNOWN"), unmatched_count=int(count or 0))
        for control_id, count in top_unmatched_rows
    ]

    return ReconciliationCoverageResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        account_id=account_id,
        in_scope_total=in_scope_total,
        in_scope_matched=in_scope_matched,
        in_scope_unmatched=in_scope_unmatched,
        coverage_rate=coverage_rate,
        in_scope_new_total=in_scope_new_total,
        in_scope_new_matched=in_scope_new_matched,
        in_scope_new_coverage_rate=in_scope_new_coverage_rate,
        top_unmatched_controls=top_unmatched_controls,
    )


@router.get(
    "/settings/{account_id}",
    response_model=ReconciliationSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_reconciliation_settings(
    account_id: Annotated[str, Path(pattern=r"^\d{12}$")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> ReconciliationSettingsResponse:
    tenant_uuid, _tenant, account = await _resolve_tenant_and_account(
        db=db,
        account_id=account_id,
        current_user=current_user,
        tenant_id=tenant_id,
    )
    ensure_tenant_reconciliation_enabled(tenant_uuid)

    settings_row = (
        await db.execute(
            select(AwsAccountReconcileSettings).where(
                AwsAccountReconcileSettings.tenant_id == tenant_uuid,
                AwsAccountReconcileSettings.account_id == account.account_id,
            )
        )
    ).scalar_one_or_none()
    return _settings_response_from_row(account=account, settings_row=settings_row)


@router.put(
    "/settings/{account_id}",
    response_model=ReconciliationSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def update_reconciliation_settings(
    account_id: Annotated[str, Path(pattern=r"^\d{12}$")],
    body: ReconciliationSettingsUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> ReconciliationSettingsResponse:
    tenant_uuid, _tenant, account = await _resolve_tenant_and_account(
        db=db,
        account_id=account_id,
        current_user=current_user,
        tenant_id=tenant_id,
    )
    ensure_tenant_reconciliation_enabled(tenant_uuid)

    row = (
        await db.execute(
            select(AwsAccountReconcileSettings).where(
                AwsAccountReconcileSettings.tenant_id == tenant_uuid,
                AwsAccountReconcileSettings.account_id == account.account_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = AwsAccountReconcileSettings(
            tenant_id=tenant_uuid,
            account_id=account.account_id,
            enabled=False,
            interval_minutes=max(60, int(settings.TENANT_RECONCILIATION_SCHEDULE_MIN_INTERVAL_MINUTES)),
            services=settings.control_plane_inventory_services_list,
            regions=account.regions or [settings.AWS_REGION],
            max_resources=int(settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD or 500),
            sweep_mode="global",
            cooldown_minutes=30,
        )
        db.add(row)

    if body.enabled is not None:
        row.enabled = bool(body.enabled)
    if body.interval_minutes is not None:
        minimum = max(1, int(settings.TENANT_RECONCILIATION_SCHEDULE_MIN_INTERVAL_MINUTES))
        if body.interval_minutes < minimum:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"interval_minutes must be >= {minimum}.",
            )
        row.interval_minutes = int(body.interval_minutes)
    if body.services is not None:
        row.services = normalize_services(body.services)
    if body.regions is not None:
        row.regions = normalize_regions(body.regions, account.regions)
    if body.max_resources is not None:
        row.max_resources = normalize_max_resources(body.max_resources)
    if body.sweep_mode is not None:
        row.sweep_mode = normalize_sweep_mode(body.sweep_mode)
    if body.cooldown_minutes is not None:
        row.cooldown_minutes = int(body.cooldown_minutes)

    if not row.services:
        row.services = settings.control_plane_inventory_services_list
    if not row.regions:
        row.regions = account.regions or [settings.AWS_REGION]
    if not row.max_resources:
        row.max_resources = int(settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD or 500)

    await db.commit()
    await db.refresh(row)
    return _settings_response_from_row(account=account, settings_row=row)
