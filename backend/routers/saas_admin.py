from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile, status
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import require_saas_admin
from backend.config import settings
from backend.database import get_db
from backend.models.action import Action
from backend.models.audit_log import AuditLog
from backend.models.aws_account import AwsAccount
from backend.models.baseline_report import BaselineReport
from backend.models.control_plane_event import ControlPlaneEvent
from backend.models.control_plane_reconcile_job import ControlPlaneReconcileJob
from backend.models.enums import BaselineReportStatus, EvidenceExportStatus, RemediationRunStatus
from backend.models.evidence_export import EvidenceExport
from backend.models.finding import Finding
from backend.models.finding_shadow_state import FindingShadowState
from backend.models.remediation_run import RemediationRun
from backend.models.support_file import SupportFile
from backend.models.support_note import SupportNote
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.services.control_scope import IN_SCOPE_CONTROL_TOKENS
from backend.utils.sqs import (
    build_reconcile_inventory_shard_job_payload,
    build_reconcile_recently_touched_resources_job_payload,
    parse_queue_region,
)

router = APIRouter(prefix="/saas", tags=["saas-admin"])


SAFE_ARTIFACT_KEYS = {"pr_bundle", "summary", "plan", "diff_summary", "files"}
PROMOTION_BLOCK_REASON_CODES = (
    "shadow_mode_enabled",
    "promotion_disabled",
    "control_not_high_confidence",
    "confidence_below_threshold",
    "soft_resolved_not_allowed",
    "tenant_not_in_pilot",
)


class TenantListItem(BaseModel):
    tenant_id: str
    tenant_name: str
    created_at: str
    users_count: int
    aws_accounts_count: int
    open_findings_count: int
    open_actions_count: int
    last_activity_at: str | None
    has_connected_accounts: bool
    ingestion_stale: bool
    digest_enabled: bool
    slack_configured: bool


class TenantListResponse(BaseModel):
    items: list[TenantListItem]
    total: int


class TenantOverviewResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    created_at: str
    users_count: int
    accounts_by_status: dict[str, int]
    actions_by_status: dict[str, int]
    findings_by_severity: dict[str, int]
    findings_trend: dict[str, int]
    digest_enabled: bool
    slack_configured: bool


class UserItemResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    created_at: str
    onboarding_completed_at: str | None


class AccountItemResponse(BaseModel):
    id: str
    account_id: str
    regions: list[str]
    status: str
    last_validated_at: str | None
    created_at: str


class FindingItemResponse(BaseModel):
    id: str
    finding_id: str
    account_id: str
    region: str
    source: str
    severity_label: str
    status: str
    title: str
    description: str | None
    resource_id: str | None
    resource_type: str | None
    control_id: str | None
    standard_name: str | None
    first_observed_at: str | None
    last_observed_at: str | None
    updated_at: str | None
    created_at: str


class FindingsListResponse(BaseModel):
    items: list[FindingItemResponse]
    total: int


class ActionItemResponse(BaseModel):
    id: str
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
    updated_at: str | None
    created_at: str | None


class ActionsListResponse(BaseModel):
    items: list[ActionItemResponse]
    total: int


class RemediationRunItemResponse(BaseModel):
    id: str
    action_id: str
    mode: str
    status: str
    outcome: str | None
    artifacts: dict[str, Any] | None
    approved_by_email: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str


class RemediationRunsListResponse(BaseModel):
    items: list[RemediationRunItemResponse]
    total: int


class ExportItemResponse(BaseModel):
    id: str
    status: str
    pack_type: str
    created_at: str
    started_at: str | None
    completed_at: str | None
    error_message: str | None
    file_size_bytes: int | None


class BaselineReportItemResponse(BaseModel):
    id: str
    status: str
    requested_at: str
    completed_at: str | None
    outcome: str | None
    file_size_bytes: int | None


class SupportNoteCreateRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)


class SupportNoteResponse(BaseModel):
    id: str
    tenant_id: str
    created_by_user_id: str | None
    created_by_email: str | None
    body: str
    created_at: str


class SupportFileItemResponse(BaseModel):
    id: str
    tenant_id: str
    filename: str
    content_type: str | None
    size_bytes: int | None
    status: str
    visible_to_tenant: bool
    message: str | None
    created_at: str
    uploaded_at: str | None


class InitiateSupportFileRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=5000)
    visible_to_tenant: bool = True


class InitiateSupportFileResponse(BaseModel):
    id: str
    upload_url: str
    method: str = "PUT"
    required_headers: dict[str, str]


class FinalizeSupportFileRequest(BaseModel):
    size_bytes: int | None = Field(default=None, ge=0)


class SystemHealthResponse(BaseModel):
    window_hours: int
    queue_configured: bool
    export_bucket_configured: bool
    support_bucket_configured: bool
    failing_remediation_runs_24h: int
    failing_baseline_reports_24h: int
    failing_exports_24h: int
    remediation_failure_rate_24h: float
    baseline_report_failure_rate_24h: float
    export_failure_rate_24h: float
    worker_failure_rate_24h: float
    p95_queue_lag_ms_24h: float | None
    control_plane_drop_rate_24h: float


class ControlPlaneSLOResponse(BaseModel):
    window_hours: int
    tenant_id: str | None
    total_events: int
    success_events: int
    dropped_events: int
    duplicate_hits: int
    p95_end_to_end_lag_ms: float | None
    p99_end_to_end_lag_ms: float | None
    p95_resolution_freshness_ms: float | None
    p95_cloudtrail_delivery_lag_ms: float | None
    p95_queue_lag_ms: float | None
    p95_handler_latency_ms: float | None
    drop_rate: float
    duplicate_rate: float
    in_scope_total: int
    missing_canonical: int
    missing_resource_key: int
    in_scope_matched: int
    in_scope_unmatched: int
    match_coverage_rate: float
    in_scope_new_total: int
    in_scope_new_matched: int
    in_scope_new_match_rate: float
    shadow_freshness_lag_minutes: float | None
    sweep_failures: int


class ControlPlanePromotionBlockedByReason(BaseModel):
    shadow_mode_enabled: int
    promotion_disabled: int
    control_not_high_confidence: int
    confidence_below_threshold: int
    soft_resolved_not_allowed: int
    tenant_not_in_pilot: int


class ControlPlanePromotionMetrics(BaseModel):
    attempts: int
    successes: int
    blocked: int
    success_rate: float
    blocked_rate: float
    blocked_by_reason: ControlPlanePromotionBlockedByReason


class ControlPlaneMismatchMetrics(BaseModel):
    comparable_rows: int
    mismatches: int
    mismatch_rate: float


class ControlPlaneSoftResolvedMetrics(BaseModel):
    promoted_controls_rows: int
    soft_resolved_rows: int
    soft_resolved_rate: float


class ControlPlaneShadowFreshnessMetrics(BaseModel):
    stale_threshold_minutes: int
    total_rows: int
    stale_rows: int
    stale_rate: float
    latest_evaluated_at: str | None
    oldest_evaluated_at: str | None


class ControlPlanePromotionGuardrailConfig(BaseModel):
    shadow_mode_enabled: bool
    promotion_enabled: bool
    high_confidence_controls_count: int
    promotion_min_confidence: int
    allow_soft_resolved: bool
    pilot_tenants_count: int


class ControlPlanePromotionGuardrailHealthResponse(BaseModel):
    generated_at: str
    scope: str
    tenant_id: str | None
    window_hours: int
    guardrails: ControlPlanePromotionGuardrailConfig
    promotion: ControlPlanePromotionMetrics
    mismatch: ControlPlaneMismatchMetrics
    soft_resolved: ControlPlaneSoftResolvedMetrics
    shadow_freshness: ControlPlaneShadowFreshnessMetrics


class ControlPlaneShadowSummaryResponse(BaseModel):
    tenant_id: str
    total_rows: int
    open_count: int
    resolved_count: int
    soft_resolved_count: int
    controls: dict[str, int]


class ControlPlaneCanonicalFindingRef(BaseModel):
    id: str
    source: str
    status_raw: str
    status_normalized: str
    severity_label: str | None = None
    title: str | None = None
    updated_at: str | None = None


class ControlPlaneShadowCompareItem(BaseModel):
    fingerprint: str
    account_id: str
    region: str
    resource_id: str | None = None
    resource_type: str | None = None
    control_id: str | None = None
    shadow_status: str
    shadow_status_normalized: str
    status_reason: str | None = None
    evidence_ref: dict | None = None
    last_observed_event_time: str | None = None
    last_evaluated_at: str | None = None
    canonical: ControlPlaneCanonicalFindingRef | None = None
    is_mismatch: bool


class ControlPlaneShadowCompareResponse(BaseModel):
    tenant_id: str
    total: int
    items: list[ControlPlaneShadowCompareItem]


class ControlPlaneShadowRef(BaseModel):
    fingerprint: str
    status_raw: str
    status_normalized: str
    status_reason: str | None = None
    evidence_ref: dict | None = None
    last_observed_event_time: str | None = None
    last_evaluated_at: str | None = None


class ControlPlaneCompareItem(BaseModel):
    comparison_key: str
    account_id: str
    region: str
    resource_id: str | None = None
    resource_type: str | None = None
    control_id: str | None = None
    shadow: ControlPlaneShadowRef | None = None
    live: ControlPlaneCanonicalFindingRef | None = None
    is_mismatch: bool


class ControlPlaneCompareResponse(BaseModel):
    tenant_id: str
    basis: str
    total: int
    items: list[ControlPlaneCompareItem]


class ControlPlaneUnmatchedReasonItem(BaseModel):
    control_id: str
    reason: str
    count: int


class ControlPlaneUnmatchedReportResponse(BaseModel):
    tenant_id: str
    generated_at: str
    items: list[ControlPlaneUnmatchedReasonItem]


class ReconcileJobsListItemResponse(BaseModel):
    id: str
    tenant_id: str
    job_type: str
    status: str
    payload_summary: dict[str, Any] | None
    submitted_at: str
    submitted_by: str | None
    error_message: str | None


class ReconcileJobsListResponse(BaseModel):
    items: list[ReconcileJobsListItemResponse]
    total: int


class ReconcileRecentlyTouchedRequest(BaseModel):
    tenant_id: str
    lookback_minutes: int | None = Field(default=None, ge=1, le=1440)
    services: list[str] | None = None
    max_resources: int | None = Field(default=None, ge=1, le=5000)


class ReconcileGlobalRequest(BaseModel):
    tenant_id: str
    account_ids: list[str] | None = None
    regions: list[str] | None = None
    services: list[str] | None = None
    max_resources: int | None = Field(default=None, ge=1, le=5000)


class ReconcileShardItem(BaseModel):
    tenant_id: str
    account_id: str = Field(..., pattern=r"^\d{12}$")
    region: str = Field(..., min_length=1, max_length=32)
    service: str = Field(..., min_length=1, max_length=32)
    resource_ids: list[str] | None = None
    sweep_mode: str | None = Field(default=None, pattern=r"^(targeted|global)$")
    max_resources: int | None = Field(default=None, ge=1, le=5000)


class ReconcileShardRequest(BaseModel):
    shards: list[ReconcileShardItem] = Field(default_factory=list, min_length=1)


class ReconcileEnqueueResponse(BaseModel):
    enqueued: int
    job_ids: list[str]
    status: str


def _parse_tenant_id(tenant_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="tenant_id must be a valid UUID") from exc


def _normalize_canonical_finding_status(status_raw: str | None) -> str:
    s = (status_raw or "").strip().upper()
    if not s:
        return "UNKNOWN"
    if s in {"ACTIVE", "NEW", "OPEN"}:
        return "OPEN"
    if s in {"RESOLVED", "CLOSED", "SUPPRESSED"}:
        return "RESOLVED"
    return "UNKNOWN"


def _normalize_shadow_status(status_raw: str | None) -> str:
    s = (status_raw or "").strip().upper()
    if s == "OPEN":
        return "OPEN"
    if s in {"RESOLVED", "SOFT_RESOLVED"}:
        return "RESOLVED"
    return "UNKNOWN"


def _rate(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator > 0 else 0.0


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _empty_promotion_block_reason_counts() -> dict[str, int]:
    return {reason: 0 for reason in PROMOTION_BLOCK_REASON_CODES}


def _promotion_guardrail_block_reasons(
    *,
    tenant_id: uuid.UUID,
    canonical_control_id: str,
    raw_status: str | None,
    state_confidence: int,
    shadow_mode_enabled: bool,
    promotion_enabled: bool,
    high_confidence_controls: set[str],
    min_confidence: int,
    allow_soft_resolved: bool,
    pilot_tenants: set[str],
) -> list[str]:
    reasons: list[str] = []
    if shadow_mode_enabled:
        reasons.append("shadow_mode_enabled")
    if not promotion_enabled:
        reasons.append("promotion_disabled")
    if canonical_control_id.upper() not in high_confidence_controls:
        reasons.append("control_not_high_confidence")
    if state_confidence < min_confidence:
        reasons.append("confidence_below_threshold")
    if (raw_status or "").strip().upper() == "SOFT_RESOLVED" and not allow_soft_resolved:
        reasons.append("soft_resolved_not_allowed")
    if pilot_tenants and str(tenant_id).lower() not in pilot_tenants:
        reasons.append("tenant_not_in_pilot")
    return reasons


def _build_promotion_blocked_by_reason(counts: dict[str, int]) -> ControlPlanePromotionBlockedByReason:
    return ControlPlanePromotionBlockedByReason(
        shadow_mode_enabled=int(counts.get("shadow_mode_enabled") or 0),
        promotion_disabled=int(counts.get("promotion_disabled") or 0),
        control_not_high_confidence=int(counts.get("control_not_high_confidence") or 0),
        confidence_below_threshold=int(counts.get("confidence_below_threshold") or 0),
        soft_resolved_not_allowed=int(counts.get("soft_resolved_not_allowed") or 0),
        tenant_not_in_pilot=int(counts.get("tenant_not_in_pilot") or 0),
    )


def _inventory_queue_or_503() -> str:
    queue_url = (settings.SQS_INVENTORY_RECONCILE_QUEUE_URL or "").strip()
    if not queue_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inventory reconcile queue URL not configured. Set SQS_INVENTORY_RECONCILE_QUEUE_URL.",
        )
    return queue_url


def _inventory_queue_client() -> tuple[Any, str]:
    queue_url = _inventory_queue_or_503()
    queue_region = parse_queue_region(queue_url)
    return boto3.client("sqs", region_name=queue_region), queue_url


def _normalize_services(services: list[str] | None) -> list[str]:
    allowed = settings.control_plane_inventory_services_list
    allowed_set = set(allowed)
    if not services:
        return allowed
    out: list[str] = []
    seen: set[str] = set()
    for item in services:
        token = str(item).strip().lower()
        if not token or token in seen or token not in allowed_set:
            continue
        seen.add(token)
        out.append(token)
    return out or allowed


async def _get_tenant_or_404(db: AsyncSession, tenant_uuid: uuid.UUID) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _sanitize_artifacts(artifacts: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(artifacts, dict):
        return None
    return {k: artifacts[k] for k in SAFE_ARTIFACT_KEYS if k in artifacts}


def _support_s3_client():
    region = (settings.S3_SUPPORT_BUCKET_REGION or "").strip() or settings.AWS_REGION
    return boto3.client("s3", region_name=region, config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))


@router.get("/system-health", response_model=SystemHealthResponse)
async def get_system_health(
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SystemHealthResponse:
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    def _rate(failed: int, total: int) -> float:
        return float(failed / total) if total > 0 else 0.0

    remediation_failed = await db.execute(
        select(func.count()).select_from(RemediationRun).where(
            RemediationRun.status == RemediationRunStatus.failed,
            RemediationRun.created_at >= since,
        )
    )
    remediation_total = await db.execute(
        select(func.count()).select_from(RemediationRun).where(RemediationRun.created_at >= since)
    )
    baseline_failed = await db.execute(
        select(func.count()).select_from(BaselineReport).where(
            BaselineReport.status == BaselineReportStatus.failed,
            BaselineReport.created_at >= since,
        )
    )
    baseline_total = await db.execute(
        select(func.count()).select_from(BaselineReport).where(BaselineReport.created_at >= since)
    )
    exports_failed = await db.execute(
        select(func.count()).select_from(EvidenceExport).where(
            EvidenceExport.status == EvidenceExportStatus.failed,
            EvidenceExport.created_at >= since,
        )
    )
    exports_total = await db.execute(
        select(func.count()).select_from(EvidenceExport).where(EvidenceExport.created_at >= since)
    )
    control_plane_total = await db.execute(
        select(func.count()).select_from(ControlPlaneEvent).where(ControlPlaneEvent.event_time >= since)
    )
    control_plane_dropped = await db.execute(
        select(func.count())
        .select_from(ControlPlaneEvent)
        .where(
            ControlPlaneEvent.event_time >= since,
            ControlPlaneEvent.processing_status == "dropped",
        )
    )
    queue_lag_p95 = await db.execute(
        select(func.percentile_cont(0.95).within_group(ControlPlaneEvent.queue_lag_ms)).where(
            ControlPlaneEvent.event_time >= since,
            ControlPlaneEvent.queue_lag_ms.isnot(None),
        )
    )

    remediation_failed_count = int(remediation_failed.scalar() or 0)
    remediation_total_count = int(remediation_total.scalar() or 0)
    baseline_failed_count = int(baseline_failed.scalar() or 0)
    baseline_total_count = int(baseline_total.scalar() or 0)
    exports_failed_count = int(exports_failed.scalar() or 0)
    exports_total_count = int(exports_total.scalar() or 0)
    control_plane_total_count = int(control_plane_total.scalar() or 0)
    control_plane_dropped_count = int(control_plane_dropped.scalar() or 0)
    queue_lag_p95_raw = queue_lag_p95.scalar()

    worker_failed_total = remediation_failed_count + baseline_failed_count + exports_failed_count
    worker_runs_total = remediation_total_count + baseline_total_count + exports_total_count

    queue_lag_p95_ms: float | None = None
    if queue_lag_p95_raw is not None:
        try:
            queue_lag_p95_ms = float(queue_lag_p95_raw)
        except (TypeError, ValueError):
            queue_lag_p95_ms = None

    return SystemHealthResponse(
        window_hours=24,
        queue_configured=bool(settings.SQS_INGEST_QUEUE_URL.strip()),
        export_bucket_configured=bool(settings.S3_EXPORT_BUCKET.strip()),
        support_bucket_configured=bool(settings.S3_SUPPORT_BUCKET.strip()),
        failing_remediation_runs_24h=remediation_failed_count,
        failing_baseline_reports_24h=baseline_failed_count,
        failing_exports_24h=exports_failed_count,
        remediation_failure_rate_24h=_rate(remediation_failed_count, remediation_total_count),
        baseline_report_failure_rate_24h=_rate(baseline_failed_count, baseline_total_count),
        export_failure_rate_24h=_rate(exports_failed_count, exports_total_count),
        worker_failure_rate_24h=_rate(worker_failed_total, worker_runs_total),
        p95_queue_lag_ms_24h=queue_lag_p95_ms,
        control_plane_drop_rate_24h=_rate(control_plane_dropped_count, control_plane_total_count),
    )


@router.get("/control-plane/slo", response_model=ControlPlaneSLOResponse)
async def get_control_plane_slo(
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[str | None, Query()] = None,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> ControlPlaneSLOResponse:
    tenant_uuid: uuid.UUID | None = None
    if tenant_id:
        tenant_uuid = _parse_tenant_id(tenant_id)
        await _get_tenant_or_404(db, tenant_uuid)

    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(hours=hours)
    filters = [ControlPlaneEvent.event_time >= since]
    if tenant_uuid is not None:
        filters.append(ControlPlaneEvent.tenant_id == tenant_uuid)

    total = int(
        (
            await db.execute(
                select(func.count()).select_from(ControlPlaneEvent).where(*filters)
            )
        ).scalar()
        or 0
    )
    success_events = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ControlPlaneEvent)
                .where(*filters, ControlPlaneEvent.processing_status == "success")
            )
        ).scalar()
        or 0
    )
    dropped_events = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ControlPlaneEvent)
                .where(*filters, ControlPlaneEvent.processing_status == "dropped")
            )
        ).scalar()
        or 0
    )
    duplicate_hits = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(ControlPlaneEvent.duplicate_count), 0)).where(*filters)
            )
        ).scalar()
        or 0
    )

    async def _percentile(metric_col, percentile: float) -> float | None:
        value = (
            await db.execute(
                select(func.percentile_cont(percentile).within_group(metric_col))
                .where(*filters, metric_col.isnot(None))
            )
        ).scalar()
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):  # pragma: no cover - defensive conversion
            return None

    p95_end_to_end_lag_ms = await _percentile(ControlPlaneEvent.end_to_end_lag_ms, 0.95)
    p99_end_to_end_lag_ms = await _percentile(ControlPlaneEvent.end_to_end_lag_ms, 0.99)
    p95_resolution_freshness_ms = await _percentile(ControlPlaneEvent.resolution_freshness_ms, 0.95)
    p95_cloudtrail_delivery_lag_ms = await _percentile(ControlPlaneEvent.cloudtrail_delivery_lag_ms, 0.95)
    p95_queue_lag_ms = await _percentile(ControlPlaneEvent.queue_lag_ms, 0.95)
    p95_handler_latency_ms = await _percentile(ControlPlaneEvent.handler_latency_ms, 0.95)

    total_attempts = total + duplicate_hits
    drop_rate = float(dropped_events / total) if total > 0 else 0.0
    duplicate_rate = float(duplicate_hits / total_attempts) if total_attempts > 0 else 0.0
    finding_filters: list[Any] = [
        Finding.source == "security_hub",
        Finding.in_scope.is_(True),
    ]
    shadow_filters: list[Any] = []
    reconcile_job_filters: list[Any] = [ControlPlaneReconcileJob.submitted_at >= since]
    if tenant_uuid is not None:
        finding_filters.append(Finding.tenant_id == tenant_uuid)
        shadow_filters.append(FindingShadowState.tenant_id == tenant_uuid)
        reconcile_job_filters.append(ControlPlaneReconcileJob.tenant_id == tenant_uuid)

    in_scope_total = int(
        (
            await db.execute(
                select(func.count()).select_from(Finding).where(*finding_filters)
            )
        ).scalar()
        or 0
    )
    missing_canonical = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Finding)
                .where(*finding_filters, Finding.canonical_control_id.is_(None))
            )
        ).scalar()
        or 0
    )
    missing_resource_key = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Finding)
                .where(*finding_filters, Finding.resource_key.is_(None))
            )
        ).scalar()
        or 0
    )
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
    match_coverage_rate = float(in_scope_matched / in_scope_total) if in_scope_total > 0 else 0.0

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
    in_scope_new_match_rate = (
        float(in_scope_new_matched / in_scope_new_total) if in_scope_new_total > 0 else 0.0
    )

    latest_shadow = (
        await db.execute(
            select(func.max(FindingShadowState.updated_at)).where(*shadow_filters)
        )
    ).scalar()
    if latest_shadow is not None:
        shadow_freshness_lag_minutes = max(
            0.0, float((now_utc - latest_shadow).total_seconds() / 60.0)
        )
    else:
        shadow_freshness_lag_minutes = None

    sweep_failures = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ControlPlaneReconcileJob)
                .where(*reconcile_job_filters, ControlPlaneReconcileJob.status == "error")
            )
        ).scalar()
        or 0
    )

    return ControlPlaneSLOResponse(
        window_hours=hours,
        tenant_id=str(tenant_uuid) if tenant_uuid is not None else None,
        total_events=total,
        success_events=success_events,
        dropped_events=dropped_events,
        duplicate_hits=duplicate_hits,
        p95_end_to_end_lag_ms=p95_end_to_end_lag_ms,
        p99_end_to_end_lag_ms=p99_end_to_end_lag_ms,
        p95_resolution_freshness_ms=p95_resolution_freshness_ms,
        p95_cloudtrail_delivery_lag_ms=p95_cloudtrail_delivery_lag_ms,
        p95_queue_lag_ms=p95_queue_lag_ms,
        p95_handler_latency_ms=p95_handler_latency_ms,
        drop_rate=drop_rate,
        duplicate_rate=duplicate_rate,
        in_scope_total=in_scope_total,
        missing_canonical=missing_canonical,
        missing_resource_key=missing_resource_key,
        in_scope_matched=in_scope_matched,
        in_scope_unmatched=in_scope_unmatched,
        match_coverage_rate=match_coverage_rate,
        in_scope_new_total=in_scope_new_total,
        in_scope_new_matched=in_scope_new_matched,
        in_scope_new_match_rate=in_scope_new_match_rate,
        shadow_freshness_lag_minutes=shadow_freshness_lag_minutes,
        sweep_failures=sweep_failures,
    )


@router.get(
    "/control-plane/promotion-guardrail-health",
    response_model=ControlPlanePromotionGuardrailHealthResponse,
)
async def get_control_plane_promotion_guardrail_health(
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[str | None, Query()] = None,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> ControlPlanePromotionGuardrailHealthResponse:
    tenant_uuid: uuid.UUID | None = None
    if tenant_id:
        tenant_uuid = _parse_tenant_id(tenant_id)
        await _get_tenant_or_404(db, tenant_uuid)

    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(hours=hours)

    high_confidence_controls = settings.control_plane_high_confidence_controls_set
    promotion_min_confidence = settings.control_plane_promotion_min_confidence
    pilot_tenants = settings.control_plane_promotion_pilot_tenants_set
    allow_soft_resolved = bool(settings.CONTROL_PLANE_PROMOTION_ALLOW_SOFT_RESOLVED)
    shadow_mode_enabled = bool(settings.CONTROL_PLANE_SHADOW_MODE)
    promotion_enabled = bool(settings.CONTROL_PLANE_AUTHORITATIVE_PROMOTION_ENABLED)
    scope = "tenant" if tenant_uuid is not None else "global"

    shadow_alias = sa.orm.aliased(FindingShadowState)
    shadow_eval_col = func.coalesce(shadow_alias.last_evaluated_at, shadow_alias.updated_at)
    candidate_filters: list[Any] = [
        shadow_alias.source == settings.CONTROL_PLANE_SOURCE,
        shadow_alias.canonical_control_id.isnot(None),
        shadow_alias.resource_key.isnot(None),
        shadow_alias.status.in_(("OPEN", "RESOLVED", "SOFT_RESOLVED")),
        shadow_eval_col >= since,
    ]
    if tenant_uuid is not None:
        candidate_filters.append(shadow_alias.tenant_id == tenant_uuid)

    canonical_subq = (
        select(Finding.status)
        .where(
            Finding.tenant_id == shadow_alias.tenant_id,
            Finding.account_id == shadow_alias.account_id,
            Finding.region == shadow_alias.region,
            Finding.source == "security_hub",
            Finding.canonical_control_id == shadow_alias.canonical_control_id,
            Finding.resource_key == shadow_alias.resource_key,
        )
        .order_by(Finding.updated_at.desc())
        .limit(1)
        .lateral()
        .alias("canonical_finding")
    )

    candidate_stmt = (
        select(
            shadow_alias.tenant_id,
            shadow_alias.canonical_control_id,
            shadow_alias.status,
            shadow_alias.state_confidence,
            shadow_eval_col.label("shadow_evaluated_at"),
            canonical_subq.c.status.label("canonical_status"),
        )
        .select_from(shadow_alias)
        .outerjoin(canonical_subq, sa.true())
        .where(*candidate_filters)
    )
    candidate_rows = (await db.execute(candidate_stmt)).all()

    attempts = 0
    successes = 0
    blocked = 0
    blocked_by_reason_counts = _empty_promotion_block_reason_counts()
    comparable_rows = 0
    mismatches = 0
    promoted_controls_rows = 0
    soft_resolved_rows = 0

    for row in candidate_rows:
        (
            row_tenant_id,
            row_control_id,
            raw_shadow_status,
            row_state_confidence,
            _shadow_evaluated_at,
            raw_canonical_status,
        ) = row
        shadow_norm = _normalize_shadow_status(raw_shadow_status)
        if shadow_norm not in {"OPEN", "RESOLVED"}:
            continue

        attempts += 1
        control_id = str(row_control_id or "").strip().upper()
        state_confidence = _coerce_int(row_state_confidence)
        row_tenant_uuid = row_tenant_id if isinstance(row_tenant_id, uuid.UUID) else uuid.UUID(str(row_tenant_id))

        block_reasons = _promotion_guardrail_block_reasons(
            tenant_id=row_tenant_uuid,
            canonical_control_id=control_id,
            raw_status=raw_shadow_status,
            state_confidence=state_confidence,
            shadow_mode_enabled=shadow_mode_enabled,
            promotion_enabled=promotion_enabled,
            high_confidence_controls=high_confidence_controls,
            min_confidence=promotion_min_confidence,
            allow_soft_resolved=allow_soft_resolved,
            pilot_tenants=pilot_tenants,
        )

        if block_reasons:
            blocked += 1
            for reason in block_reasons:
                if reason in blocked_by_reason_counts:
                    blocked_by_reason_counts[reason] += 1
        else:
            canonical_norm = _normalize_canonical_finding_status(raw_canonical_status)
            if canonical_norm == shadow_norm:
                successes += 1

        if control_id in high_confidence_controls:
            promoted_controls_rows += 1
            if str(raw_shadow_status or "").strip().upper() == "SOFT_RESOLVED":
                soft_resolved_rows += 1
            canonical_norm = _normalize_canonical_finding_status(raw_canonical_status)
            if canonical_norm in {"OPEN", "RESOLVED"}:
                comparable_rows += 1
                if canonical_norm != shadow_norm:
                    mismatches += 1

    freshness_filters: list[Any] = [FindingShadowState.source == settings.CONTROL_PLANE_SOURCE]
    if tenant_uuid is not None:
        freshness_filters.append(FindingShadowState.tenant_id == tenant_uuid)

    freshness_eval_col = func.coalesce(FindingShadowState.last_evaluated_at, FindingShadowState.updated_at)
    stale_threshold_minutes = max(1, _coerce_int(settings.CONTROL_PLANE_PREREQ_MAX_STALENESS_MINUTES, 30))
    stale_before = now_utc - timedelta(minutes=stale_threshold_minutes)

    total_shadow_rows = int(
        (
            await db.execute(
                select(func.count()).select_from(FindingShadowState).where(*freshness_filters)
            )
        ).scalar()
        or 0
    )
    stale_rows = int(
        (
            await db.execute(
                select(func.count())
                .select_from(FindingShadowState)
                .where(*freshness_filters, freshness_eval_col < stale_before)
            )
        ).scalar()
        or 0
    )
    latest_shadow_eval = (
        await db.execute(select(func.max(freshness_eval_col)).where(*freshness_filters))
    ).scalar()
    oldest_shadow_eval = (
        await db.execute(select(func.min(freshness_eval_col)).where(*freshness_filters))
    ).scalar()

    return ControlPlanePromotionGuardrailHealthResponse(
        generated_at=now_utc.isoformat(),
        scope=scope,
        tenant_id=str(tenant_uuid) if tenant_uuid is not None else None,
        window_hours=hours,
        guardrails=ControlPlanePromotionGuardrailConfig(
            shadow_mode_enabled=shadow_mode_enabled,
            promotion_enabled=promotion_enabled,
            high_confidence_controls_count=len(high_confidence_controls),
            promotion_min_confidence=promotion_min_confidence,
            allow_soft_resolved=allow_soft_resolved,
            pilot_tenants_count=len(pilot_tenants),
        ),
        promotion=ControlPlanePromotionMetrics(
            attempts=attempts,
            successes=successes,
            blocked=blocked,
            success_rate=_rate(successes, attempts),
            blocked_rate=_rate(blocked, attempts),
            blocked_by_reason=_build_promotion_blocked_by_reason(blocked_by_reason_counts),
        ),
        mismatch=ControlPlaneMismatchMetrics(
            comparable_rows=comparable_rows,
            mismatches=mismatches,
            mismatch_rate=_rate(mismatches, comparable_rows),
        ),
        soft_resolved=ControlPlaneSoftResolvedMetrics(
            promoted_controls_rows=promoted_controls_rows,
            soft_resolved_rows=soft_resolved_rows,
            soft_resolved_rate=_rate(soft_resolved_rows, promoted_controls_rows),
        ),
        shadow_freshness=ControlPlaneShadowFreshnessMetrics(
            stale_threshold_minutes=stale_threshold_minutes,
            total_rows=total_shadow_rows,
            stale_rows=stale_rows,
            stale_rate=_rate(stale_rows, total_shadow_rows),
            latest_evaluated_at=latest_shadow_eval.isoformat() if latest_shadow_eval else None,
            oldest_evaluated_at=oldest_shadow_eval.isoformat() if oldest_shadow_eval else None,
        ),
    )


@router.get("/control-plane/shadow-summary", response_model=ControlPlaneShadowSummaryResponse)
async def get_control_plane_shadow_summary(
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[str, Query()],
) -> ControlPlaneShadowSummaryResponse:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)

    shadow_filters: list[Any] = [FindingShadowState.tenant_id == tenant_uuid]
    if settings.ONLY_IN_SCOPE_CONTROLS:
        control_token = func.upper(func.substring(FindingShadowState.control_id, r"([A-Za-z][A-Za-z0-9]*\.\d+)$"))
        in_scope_token = func.coalesce(FindingShadowState.canonical_control_id, control_token)
        shadow_filters.append(in_scope_token.in_(sorted(IN_SCOPE_CONTROL_TOKENS)))

    total_rows = int(
        (
            await db.execute(
                select(func.count()).select_from(FindingShadowState).where(*shadow_filters)
            )
        ).scalar()
        or 0
    )
    open_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(FindingShadowState)
                .where(*shadow_filters, FindingShadowState.status == "OPEN")
            )
        ).scalar()
        or 0
    )
    resolved_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(FindingShadowState)
                .where(*shadow_filters, FindingShadowState.status == "RESOLVED")
            )
        ).scalar()
        or 0
    )
    soft_resolved_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(FindingShadowState)
                .where(*shadow_filters, FindingShadowState.status == "SOFT_RESOLVED")
            )
        ).scalar()
        or 0
    )
    controls_group_key = func.coalesce(FindingShadowState.canonical_control_id, FindingShadowState.control_id)
    controls_rows = await db.execute(
        select(controls_group_key, func.count())
        .where(*shadow_filters)
        .group_by(controls_group_key)
    )
    controls = {str(control): int(count) for control, count in controls_rows.all()}

    return ControlPlaneShadowSummaryResponse(
        tenant_id=str(tenant_uuid),
        total_rows=total_rows,
        open_count=open_count,
        resolved_count=resolved_count,
        soft_resolved_count=soft_resolved_count,
        controls=controls,
    )


@router.get("/control-plane/shadow-compare", response_model=ControlPlaneShadowCompareResponse)
async def get_control_plane_shadow_compare(
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[str, Query()],
    control_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> ControlPlaneShadowCompareResponse:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)

    shadow_filters: list[Any] = [FindingShadowState.tenant_id == tenant_uuid]
    control_filter = (control_id or "").strip().upper()
    if control_filter:
        shadow_filters.append(
            func.upper(func.coalesce(FindingShadowState.canonical_control_id, FindingShadowState.control_id))
            == control_filter
        )
    if settings.ONLY_IN_SCOPE_CONTROLS:
        control_token = func.upper(func.substring(FindingShadowState.control_id, r"([A-Za-z][A-Za-z0-9]*\.\d+)$"))
        in_scope_token = func.coalesce(FindingShadowState.canonical_control_id, control_token)
        shadow_filters.append(in_scope_token.in_(sorted(IN_SCOPE_CONTROL_TOKENS)))

    total = int(
        (
            await db.execute(
                select(func.count()).select_from(FindingShadowState).where(*shadow_filters)
            )
        ).scalar()
        or 0
    )

    shadow_alias = sa.orm.aliased(FindingShadowState)
    shadow_alias_filters: list[Any] = [shadow_alias.tenant_id == tenant_uuid]
    if control_filter:
        shadow_alias_filters.append(
            func.upper(func.coalesce(shadow_alias.canonical_control_id, shadow_alias.control_id)) == control_filter
        )
    if settings.ONLY_IN_SCOPE_CONTROLS:
        control_token_alias = func.upper(func.substring(shadow_alias.control_id, r"([A-Za-z][A-Za-z0-9]*\.\d+)$"))
        in_scope_token_alias = func.coalesce(shadow_alias.canonical_control_id, control_token_alias)
        shadow_alias_filters.append(in_scope_token_alias.in_(sorted(IN_SCOPE_CONTROL_TOKENS)))

    # LATERAL subquery: pick the latest canonical finding that matches this shadow row.
    # We map it back to a Finding ORM entity via aliased(Finding, subquery).
    canonical_subq = (
        select(Finding)
        .where(
            Finding.tenant_id == shadow_alias.tenant_id,
            Finding.account_id == shadow_alias.account_id,
            Finding.region == shadow_alias.region,
            sa.or_(
                # Preferred: canonical join key (stable across control aliases and resource ARN formats).
                sa.and_(
                    shadow_alias.canonical_control_id.isnot(None),
                    shadow_alias.resource_key.isnot(None),
                    Finding.canonical_control_id == shadow_alias.canonical_control_id,
                    Finding.resource_key == shadow_alias.resource_key,
                ),
                # Back-compat fallback: match on raw control/resource identifiers.
                sa.and_(
                    Finding.control_id == shadow_alias.control_id,
                    sa.or_(
                        Finding.resource_id == shadow_alias.resource_id,
                        Finding.resource_id.contains(shadow_alias.resource_id),
                    ),
                ),
            ),
        )
        .order_by(Finding.updated_at.desc())
        .limit(1)
        .lateral()
        .alias("canonical_finding")
    )
    canonical_alias = sa.orm.aliased(Finding, canonical_subq)

    stmt = (
        select(shadow_alias, canonical_alias)
        .select_from(shadow_alias)
        .outerjoin(canonical_subq, sa.true())
        .where(*shadow_alias_filters)
        .order_by(sa.desc(shadow_alias.last_observed_event_time).nullslast(), sa.desc(shadow_alias.updated_at))
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()

    items: list[ControlPlaneShadowCompareItem] = []
    for shadow_row, canonical_row in rows:
        shadow_norm = _normalize_shadow_status(getattr(shadow_row, "status", None))
        canonical_ref: ControlPlaneCanonicalFindingRef | None = None
        canonical_norm = "UNKNOWN"
        if canonical_row is not None:
            canonical_norm = _normalize_canonical_finding_status(getattr(canonical_row, "status", None))
            canonical_ref = ControlPlaneCanonicalFindingRef(
                id=str(canonical_row.id),
                source=str(canonical_row.source or ""),
                status_raw=str(canonical_row.status or ""),
                status_normalized=canonical_norm,
                severity_label=str(canonical_row.severity_label) if canonical_row.severity_label else None,
                title=str(canonical_row.title) if canonical_row.title else None,
                updated_at=canonical_row.updated_at.isoformat() if canonical_row.updated_at else None,
            )

        is_mismatch = bool(shadow_norm != "UNKNOWN" and canonical_norm != "UNKNOWN" and shadow_norm != canonical_norm)
        items.append(
            ControlPlaneShadowCompareItem(
                fingerprint=str(shadow_row.fingerprint),
                account_id=str(shadow_row.account_id),
                region=str(shadow_row.region),
                resource_id=str(shadow_row.resource_id) if shadow_row.resource_id else None,
                resource_type=str(shadow_row.resource_type) if shadow_row.resource_type else None,
                control_id=str(shadow_row.control_id) if shadow_row.control_id else None,
                shadow_status=str(shadow_row.status),
                shadow_status_normalized=shadow_norm,
                status_reason=str(shadow_row.status_reason) if shadow_row.status_reason else None,
                evidence_ref=shadow_row.evidence_ref if isinstance(shadow_row.evidence_ref, dict) else None,
                last_observed_event_time=shadow_row.last_observed_event_time.isoformat()
                if shadow_row.last_observed_event_time
                else None,
                last_evaluated_at=shadow_row.last_evaluated_at.isoformat() if shadow_row.last_evaluated_at else None,
                canonical=canonical_ref,
                is_mismatch=is_mismatch,
            )
        )

    return ControlPlaneShadowCompareResponse(tenant_id=str(tenant_uuid), total=total, items=items)


@router.get("/control-plane/compare", response_model=ControlPlaneCompareResponse)
async def get_control_plane_compare(
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[str, Query()],
    basis: Annotated[str, Query(pattern=r"^(live|shadow)$")] = "live",
    only_with_shadow: Annotated[bool, Query()] = False,
    only_mismatches: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> ControlPlaneCompareResponse:
    """
    Returns a side-by-side comparison between:
    - "live": canonical findings (Security Hub / legacy ingest outputs)
    - "shadow": near-real-time overlay state (event + enrichment, plus inventory reconciliation)

    Rationale: a shadow-first view is great to debug the control-plane pipeline, but it hides the
    majority of "live" findings for controls not yet covered by shadow. This endpoint provides
    a live-first basis so admins can see coverage gaps and mismatches at a glance.
    """
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)

    if basis == "shadow":
        # Keep a thin compatibility layer: return the existing shadow-first list
        # as compare items (live may be None).
        shadow_resp = await get_control_plane_shadow_compare(
            _admin=_admin,
            db=db,
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
        )
        items = [
            ControlPlaneCompareItem(
                comparison_key=f"f:{row.fingerprint}",
                account_id=row.account_id,
                region=row.region,
                resource_id=row.resource_id,
                resource_type=row.resource_type,
                control_id=row.control_id,
                shadow=ControlPlaneShadowRef(
                    fingerprint=row.fingerprint,
                    status_raw=row.shadow_status,
                    status_normalized=row.shadow_status_normalized,
                    status_reason=row.status_reason,
                    evidence_ref=row.evidence_ref,
                    last_observed_event_time=row.last_observed_event_time,
                    last_evaluated_at=row.last_evaluated_at,
                ),
                live=row.canonical,
                is_mismatch=row.is_mismatch,
            )
            for row in shadow_resp.items
        ]
        return ControlPlaneCompareResponse(
            tenant_id=str(tenant_uuid),
            basis="shadow",
            total=shadow_resp.total,
            items=items,
        )

    finding_alias = sa.orm.aliased(Finding)

    # Best-effort derived join keys for legacy rows that have not been backfilled yet.
    # These mirror backend.services.canonicalization behavior, but are intentionally
    # limited to a few high-signal resource types that we care about in Phase 1/2.
    derived_control_token = sa.func.upper(
        sa.func.substring(
            finding_alias.control_id,
            r"([A-Za-z][A-Za-z0-9]*\.\d+)$",
        )
    )
    join_control_id = sa.func.coalesce(
        finding_alias.canonical_control_id,
        derived_control_token,
        sa.func.upper(finding_alias.control_id),
    )

    derived_sg_id = sa.func.coalesce(
        sa.case(
            (finding_alias.resource_id.ilike("sg-%"), finding_alias.resource_id),
            else_=None,
        ),
        sa.func.substring(finding_alias.resource_id, r"(sg-[0-9a-f]{8,17})"),
    )
    derived_sg_key = sa.case(
        (derived_sg_id.isnot(None), sa.literal("sg:") + derived_sg_id),
        else_=None,
    )

    derived_s3_bucket = sa.case(
        (finding_alias.resource_id.ilike("arn:aws:s3:::%"), sa.func.replace(finding_alias.resource_id, "arn:aws:s3:::", "")),
        else_=finding_alias.resource_id,
    )
    derived_s3_key = sa.case(
        (derived_s3_bucket.isnot(None), sa.literal("s3:") + derived_s3_bucket),
        else_=None,
    )

    derived_account_key = sa.literal("account:") + finding_alias.account_id
    derived_account_region_key = (
        sa.literal("account:") + finding_alias.account_id + sa.literal(":region:") + finding_alias.region
    )

    derived_resource_key = sa.case(
        (finding_alias.resource_type == "AwsEc2SecurityGroup", derived_sg_key),
        (finding_alias.resource_type == "AwsS3Bucket", derived_s3_key),
        (finding_alias.resource_type == "AwsAccount", derived_account_key),
        (finding_alias.resource_type == "AwsAccountRegion", derived_account_region_key),
        else_=None,
    )
    join_resource_key = sa.func.coalesce(finding_alias.resource_key, derived_resource_key)

    scope_filter = sa.true()
    if settings.ONLY_IN_SCOPE_CONTROLS:
        scope_filter = join_control_id.in_(sorted(IN_SCOPE_CONTROL_TOKENS))

    # LATERAL subquery: pick the latest shadow state that matches this canonical finding.
    shadow_subq = (
        select(FindingShadowState)
        .where(
            FindingShadowState.tenant_id == finding_alias.tenant_id,
            FindingShadowState.account_id == finding_alias.account_id,
            FindingShadowState.region == finding_alias.region,
            sa.or_(
                # Preferred: canonical join key (stable across control aliases and resource ARN formats).
                sa.and_(
                    join_control_id.isnot(None),
                    join_resource_key.isnot(None),
                    FindingShadowState.canonical_control_id == join_control_id,
                    FindingShadowState.resource_key == join_resource_key,
                ),
                # Back-compat fallback: match on raw control/resource identifiers.
                sa.and_(
                    FindingShadowState.control_id == finding_alias.control_id,
                    finding_alias.resource_id.isnot(None),
                    FindingShadowState.resource_id.isnot(None),
                    sa.or_(
                        FindingShadowState.resource_id == finding_alias.resource_id,
                        finding_alias.resource_id.contains(FindingShadowState.resource_id),
                        FindingShadowState.resource_id.contains(finding_alias.resource_id),
                    ),
                ),
            ),
        )
        .order_by(
            sa.desc(FindingShadowState.last_observed_event_time).nullslast(),
            sa.desc(FindingShadowState.updated_at),
        )
        .limit(1)
        .lateral()
        .alias("shadow_state")
    )
    shadow_alias = sa.orm.aliased(FindingShadowState, shadow_subq)

    # Filter flags: apply on the server so pagination/total stays consistent.
    require_shadow_filter = sa.true()
    if only_with_shadow or only_mismatches:
        require_shadow_filter = shadow_alias.id.isnot(None)

    mismatch_filter = sa.true()
    if only_mismatches:
        live_upper = func.upper(func.coalesce(cast(finding_alias.status, String), ""))
        live_norm = sa.case(
            (live_upper.in_(("ACTIVE", "NEW", "OPEN")), "OPEN"),
            (live_upper.in_(("RESOLVED", "CLOSED", "SUPPRESSED")), "RESOLVED"),
            else_="UNKNOWN",
        )
        shadow_upper = func.upper(func.coalesce(cast(shadow_alias.status, String), ""))
        shadow_norm = sa.case(
            (shadow_upper == "OPEN", "OPEN"),
            (shadow_upper.in_(("RESOLVED", "SOFT_RESOLVED")), "RESOLVED"),
            else_="UNKNOWN",
        )
        mismatch_filter = sa.and_(shadow_norm != "UNKNOWN", live_norm != "UNKNOWN", shadow_norm != live_norm)

    count_stmt = (
        select(func.count())
        .select_from(finding_alias)
        .outerjoin(shadow_subq, sa.true())
        .where(
            finding_alias.tenant_id == tenant_uuid,
            scope_filter,
            require_shadow_filter,
            mismatch_filter,
        )
    )
    total = int((await db.execute(count_stmt)).scalar() or 0)

    stmt = (
        select(finding_alias, shadow_alias)
        .select_from(finding_alias)
        .outerjoin(shadow_subq, sa.true())
        .where(
            finding_alias.tenant_id == tenant_uuid,
            scope_filter,
            require_shadow_filter,
            mismatch_filter,
        )
        .order_by(sa.desc(finding_alias.updated_at))
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()

    items: list[ControlPlaneCompareItem] = []
    for finding_row, shadow_row in rows:
        live_norm = _normalize_canonical_finding_status(getattr(finding_row, "status", None))
        live_ref = ControlPlaneCanonicalFindingRef(
            id=str(finding_row.id),
            source=str(finding_row.source or ""),
            status_raw=str(finding_row.status or ""),
            status_normalized=live_norm,
            severity_label=str(finding_row.severity_label) if finding_row.severity_label else None,
            title=str(finding_row.title) if finding_row.title else None,
            updated_at=finding_row.updated_at.isoformat() if finding_row.updated_at else None,
        )

        shadow_ref: ControlPlaneShadowRef | None = None
        shadow_norm = "UNKNOWN"
        if shadow_row is not None:
            shadow_norm = _normalize_shadow_status(getattr(shadow_row, "status", None))
            shadow_ref = ControlPlaneShadowRef(
                fingerprint=str(shadow_row.fingerprint),
                status_raw=str(shadow_row.status or ""),
                status_normalized=shadow_norm,
                status_reason=str(shadow_row.status_reason) if shadow_row.status_reason else None,
                evidence_ref=shadow_row.evidence_ref if isinstance(shadow_row.evidence_ref, dict) else None,
                last_observed_event_time=shadow_row.last_observed_event_time.isoformat()
                if shadow_row.last_observed_event_time
                else None,
                last_evaluated_at=shadow_row.last_evaluated_at.isoformat() if shadow_row.last_evaluated_at else None,
            )

        is_mismatch = bool(
            shadow_norm != "UNKNOWN"
            and live_norm != "UNKNOWN"
            and shadow_norm != live_norm
        )

        comparison_key = f"c:{finding_row.id}"
        if shadow_ref is not None:
            comparison_key = f"c:{finding_row.id}:f:{shadow_ref.fingerprint}"

        items.append(
            ControlPlaneCompareItem(
                comparison_key=comparison_key,
                account_id=str(finding_row.account_id),
                region=str(finding_row.region),
                resource_id=str(finding_row.resource_id) if finding_row.resource_id else None,
                resource_type=str(finding_row.resource_type) if finding_row.resource_type else None,
                control_id=str(finding_row.control_id) if finding_row.control_id else None,
                shadow=shadow_ref,
                live=live_ref,
                is_mismatch=is_mismatch,
            )
        )

    return ControlPlaneCompareResponse(
        tenant_id=str(tenant_uuid),
        basis="live",
        total=total,
        items=items,
    )


@router.get("/control-plane/unmatched-report", response_model=ControlPlaneUnmatchedReportResponse)
async def get_control_plane_unmatched_report(
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[str, Query()],
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> ControlPlaneUnmatchedReportResponse:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    finding_alias = sa.orm.aliased(Finding)
    derived_control_token = sa.func.upper(
        sa.func.substring(
            finding_alias.control_id,
            r"([A-Za-z][A-Za-z0-9]*\.\d+)$",
        )
    )
    control_group = sa.func.coalesce(
        finding_alias.canonical_control_id,
        derived_control_token,
        sa.func.upper(finding_alias.control_id),
        sa.literal("UNKNOWN"),
    )

    derived_sg_id = sa.func.coalesce(
        sa.case(
            (finding_alias.resource_id.ilike("sg-%"), finding_alias.resource_id),
            else_=None,
        ),
        sa.func.substring(finding_alias.resource_id, r"(sg-[0-9a-f]{8,17})"),
    )
    derived_sg_key = sa.case(
        (derived_sg_id.isnot(None), sa.literal("sg:") + derived_sg_id),
        else_=None,
    )
    derived_s3_bucket = sa.case(
        (
            finding_alias.resource_id.ilike("arn:aws:s3:::%"),
            sa.func.replace(finding_alias.resource_id, "arn:aws:s3:::", ""),
        ),
        else_=finding_alias.resource_id,
    )
    derived_s3_key = sa.case(
        (derived_s3_bucket.isnot(None), sa.literal("s3:") + derived_s3_bucket),
        else_=None,
    )
    derived_account_key = sa.literal("account:") + finding_alias.account_id
    derived_account_region_key = (
        sa.literal("account:")
        + finding_alias.account_id
        + sa.literal(":region:")
        + finding_alias.region
    )
    derived_resource_key = sa.case(
        (finding_alias.resource_type == "AwsEc2SecurityGroup", derived_sg_key),
        (finding_alias.resource_type == "AwsS3Bucket", derived_s3_key),
        (finding_alias.resource_type == "AwsAccount", derived_account_key),
        (finding_alias.resource_type == "AwsAccountRegion", derived_account_region_key),
        else_=None,
    )
    join_resource_key = sa.func.coalesce(finding_alias.resource_key, derived_resource_key)

    shadow_exists = sa.exists(
        select(FindingShadowState.id).where(
            FindingShadowState.tenant_id == finding_alias.tenant_id,
            FindingShadowState.account_id == finding_alias.account_id,
            FindingShadowState.region == finding_alias.region,
            FindingShadowState.canonical_control_id == control_group,
            FindingShadowState.resource_key == join_resource_key,
        )
    )
    reason_expr = sa.case(
        (finding_alias.status == "RESOLVED", sa.literal("expected_historical_resolved")),
        (
            shadow_exists,
            sa.literal("shadow_exists_but_not_attached"),
        ),
        else_=sa.literal("no_shadow_row"),
    )

    rows = (
        await db.execute(
            select(
                control_group.label("control_id"),
                reason_expr.label("reason"),
                func.count().label("count"),
            )
            .select_from(finding_alias)
            .where(
                finding_alias.tenant_id == tenant_uuid,
                finding_alias.source == "security_hub",
                finding_alias.in_scope.is_(True),
                finding_alias.updated_at >= since,
                sa.or_(
                    finding_alias.shadow_fingerprint.is_(None),
                    finding_alias.shadow_fingerprint == "",
                ),
            )
            .group_by(control_group, reason_expr)
            .order_by(sa.desc(func.count()))
        )
    ).all()

    items = [
        ControlPlaneUnmatchedReasonItem(
            control_id=str(control_id or "UNKNOWN"),
            reason=str(reason or "unknown"),
            count=int(count or 0),
        )
        for control_id, reason, count in rows
    ]
    return ControlPlaneUnmatchedReportResponse(
        tenant_id=str(tenant_uuid),
        generated_at=datetime.now(timezone.utc).isoformat(),
        items=items,
    )


@router.get("/control-plane/reconcile-jobs", response_model=ReconcileJobsListResponse)
async def list_control_plane_reconcile_jobs(
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[str, Query()],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ReconcileJobsListResponse:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)

    total = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ControlPlaneReconcileJob)
                .where(ControlPlaneReconcileJob.tenant_id == tenant_uuid)
            )
        ).scalar()
        or 0
    )
    rows = (
        await db.execute(
            select(ControlPlaneReconcileJob)
            .where(ControlPlaneReconcileJob.tenant_id == tenant_uuid)
            .order_by(ControlPlaneReconcileJob.submitted_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    items = [
        ReconcileJobsListItemResponse(
            id=str(row.id),
            tenant_id=str(row.tenant_id),
            job_type=row.job_type,
            status=row.status,
            payload_summary=row.payload_summary if isinstance(row.payload_summary, dict) else None,
            submitted_at=row.submitted_at.isoformat() if row.submitted_at else "",
            submitted_by=row.submitted_by_email,
            error_message=row.error_message,
        )
        for row in rows
    ]
    return ReconcileJobsListResponse(items=items, total=total)


@router.post("/control-plane/reconcile/recently-touched", response_model=ReconcileEnqueueResponse)
async def enqueue_control_plane_reconcile_recently_touched(
    body: ReconcileRecentlyTouchedRequest,
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReconcileEnqueueResponse:
    tenant_uuid = _parse_tenant_id(body.tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    sqs, queue_url = _inventory_queue_client()
    now = datetime.now(timezone.utc)
    services = _normalize_services(body.services)
    payload = build_reconcile_recently_touched_resources_job_payload(
        tenant_id=tenant_uuid,
        created_at=now.isoformat(),
        lookback_minutes=body.lookback_minutes,
        services=services,
        max_resources=body.max_resources,
    )

    record = ControlPlaneReconcileJob(
        tenant_id=tenant_uuid,
        submitted_by_user_id=admin.id,
        submitted_by_email=admin.email,
        job_type="reconcile_recently_touched_resources",
        status="queued",
        payload_summary={
            "lookback_minutes": body.lookback_minutes or settings.CONTROL_PLANE_RECENT_TOUCH_LOOKBACK_MINUTES,
            "services": services,
            "max_resources": body.max_resources or settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD,
        },
        submitted_at=now,
    )
    db.add(record)
    try:
        response = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
        record.queue_message_id = str(response.get("MessageId") or "")
        record.status = "enqueued"
        await db.commit()
        await db.refresh(record)
    except Exception as exc:
        record.status = "error"
        record.error_message = str(exc)[:4000]
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Failed to enqueue reconcile job: {exc}") from exc

    return ReconcileEnqueueResponse(enqueued=1, job_ids=[str(record.id)], status="ok")


@router.post("/control-plane/reconcile/global", response_model=ReconcileEnqueueResponse)
async def enqueue_control_plane_reconcile_global(
    body: ReconcileGlobalRequest,
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReconcileEnqueueResponse:
    tenant_uuid = _parse_tenant_id(body.tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    sqs, queue_url = _inventory_queue_client()
    now = datetime.now(timezone.utc)
    services = _normalize_services(body.services)

    account_ids_filter = {str(v).strip() for v in (body.account_ids or []) if str(v).strip()}
    stmt = select(AwsAccount).where(AwsAccount.tenant_id == tenant_uuid)
    if account_ids_filter:
        stmt = stmt.where(AwsAccount.account_id.in_(sorted(account_ids_filter)))
    accounts = list((await db.execute(stmt)).scalars().all())

    record = ControlPlaneReconcileJob(
        tenant_id=tenant_uuid,
        submitted_by_user_id=admin.id,
        submitted_by_email=admin.email,
        job_type="reconcile_inventory_global",
        status="queued",
        payload_summary={
            "account_ids": sorted(account_ids_filter) if account_ids_filter else None,
            "regions": body.regions,
            "services": services,
            "max_resources": body.max_resources or settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD,
        },
        submitted_at=now,
    )
    db.add(record)
    enqueued = 0
    try:
        for account in accounts:
            status_value = getattr(account.status, "value", str(account.status)).lower()
            if status_value == "disabled":
                continue
            account_regions = body.regions if body.regions else (account.regions or [settings.AWS_REGION])
            regions: list[str] = []
            seen_regions: set[str] = set()
            for raw_region in account_regions:
                region = str(raw_region).strip()
                if not region or region in seen_regions:
                    continue
                seen_regions.add(region)
                regions.append(region)
            for region in regions:
                for service in services:
                    payload = build_reconcile_inventory_shard_job_payload(
                        tenant_id=tenant_uuid,
                        account_id=account.account_id,
                        region=region,
                        service=service,
                        resource_ids=None,
                        created_at=now.isoformat(),
                        sweep_mode="global",
                        max_resources=body.max_resources,
                    )
                    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
                    enqueued += 1
        record.status = "enqueued"
        record.payload_summary = {
            **(record.payload_summary if isinstance(record.payload_summary, dict) else {}),
            "enqueued": enqueued,
        }
        await db.commit()
        await db.refresh(record)
    except Exception as exc:
        record.status = "error"
        record.error_message = str(exc)[:4000]
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Failed to enqueue global reconcile jobs: {exc}") from exc
    return ReconcileEnqueueResponse(enqueued=enqueued, job_ids=[str(record.id)], status="ok")


@router.post("/control-plane/reconcile/shard", response_model=ReconcileEnqueueResponse)
async def enqueue_control_plane_reconcile_shard(
    body: ReconcileShardRequest,
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReconcileEnqueueResponse:
    sqs, queue_url = _inventory_queue_client()
    now = datetime.now(timezone.utc)
    enqueued = 0
    tenant_uuid_for_record: uuid.UUID | None = None
    services_used: set[str] = set()
    for shard in body.shards:
        tenant_uuid = _parse_tenant_id(shard.tenant_id)
        await _get_tenant_or_404(db, tenant_uuid)
        if tenant_uuid_for_record is None:
            tenant_uuid_for_record = tenant_uuid
        elif tenant_uuid_for_record != tenant_uuid:
            raise HTTPException(status_code=400, detail="All shards must belong to the same tenant_id")

    if tenant_uuid_for_record is None:
        raise HTTPException(status_code=400, detail="At least one shard is required")

    record = ControlPlaneReconcileJob(
        tenant_id=tenant_uuid_for_record,
        submitted_by_user_id=admin.id,
        submitted_by_email=admin.email,
        job_type="reconcile_inventory_shard",
        status="queued",
        payload_summary={
            "shards": len(body.shards),
            "services": sorted(services_used),
        },
        submitted_at=now,
    )
    db.add(record)
    try:
        for shard in body.shards:
            payload = build_reconcile_inventory_shard_job_payload(
                tenant_id=_parse_tenant_id(shard.tenant_id),
                account_id=shard.account_id,
                region=shard.region,
                service=shard.service,
                resource_ids=shard.resource_ids,
                created_at=now.isoformat(),
                sweep_mode=shard.sweep_mode,
                max_resources=shard.max_resources,
            )
            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
            services_used.add(str(shard.service).strip().lower())
            enqueued += 1
        record.status = "enqueued"
        record.payload_summary = {
            **(record.payload_summary if isinstance(record.payload_summary, dict) else {}),
            "services": sorted(services_used),
            "enqueued": enqueued,
        }
        await db.commit()
        await db.refresh(record)
    except Exception as exc:
        record.status = "error"
        record.error_message = str(exc)[:4000]
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Failed to enqueue shard reconcile jobs: {exc}") from exc
    return ReconcileEnqueueResponse(enqueued=enqueued, job_ids=[str(record.id)], status="ok")


@router.get("/tenants", response_model=TenantListResponse)
async def list_tenants(
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    query: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TenantListResponse:
    base = select(Tenant)
    if query:
        base = base.where(
            Tenant.name.ilike(f"%{query.strip()}%")
            | cast(Tenant.id, String).ilike(f"%{query.strip()}%")
        )
    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = int(total_result.scalar() or 0)
    result = await db.execute(base.order_by(Tenant.created_at.desc()).limit(limit).offset(offset))
    tenants = list(result.scalars().all())
    items: list[TenantListItem] = []
    stale_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
    for tenant in tenants:
        tenant_id = tenant.id
        users_count = int((await db.execute(select(func.count()).select_from(User).where(User.tenant_id == tenant_id))).scalar() or 0)
        aws_accounts_count = int((await db.execute(select(func.count()).select_from(AwsAccount).where(AwsAccount.tenant_id == tenant_id))).scalar() or 0)
        open_findings_count = int((await db.execute(select(func.count()).select_from(Finding).where(Finding.tenant_id == tenant_id, Finding.status.in_(["NEW", "NOTIFIED"])))).scalar() or 0)
        open_actions_count = int((await db.execute(select(func.count()).select_from(Action).where(Action.tenant_id == tenant_id, Action.status.in_(["open", "in_progress"])))).scalar() or 0)
        latest_finding = (await db.execute(select(func.max(Finding.sh_updated_at)).where(Finding.tenant_id == tenant_id))).scalar()
        latest_remediation = (await db.execute(select(func.max(RemediationRun.created_at)).where(RemediationRun.tenant_id == tenant_id))).scalar()
        latest_export = (await db.execute(select(func.max(EvidenceExport.created_at)).where(EvidenceExport.tenant_id == tenant_id))).scalar()
        latest_baseline = (await db.execute(select(func.max(BaselineReport.created_at)).where(BaselineReport.tenant_id == tenant_id))).scalar()
        activity_candidates = [latest_finding, latest_remediation, latest_export, latest_baseline]
        last_activity = max((d for d in activity_candidates if d is not None), default=None)
        items.append(
            TenantListItem(
                tenant_id=str(tenant.id),
                tenant_name=tenant.name,
                created_at=tenant.created_at.isoformat() if tenant.created_at else "",
                users_count=users_count,
                aws_accounts_count=aws_accounts_count,
                open_findings_count=open_findings_count,
                open_actions_count=open_actions_count,
                last_activity_at=last_activity.isoformat() if last_activity else None,
                has_connected_accounts=aws_accounts_count > 0,
                ingestion_stale=bool(latest_finding is None or latest_finding < stale_threshold),
                digest_enabled=bool(tenant.digest_enabled),
                slack_configured=bool((tenant.slack_webhook_url or "").strip()),
            )
        )
    return TenantListResponse(items=items, total=total)


@router.get("/tenants/{tenant_id}", response_model=TenantOverviewResponse)
async def get_tenant_overview(
    tenant_id: Annotated[str, Path()],
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantOverviewResponse:
    tenant_uuid = _parse_tenant_id(tenant_id)
    tenant = await _get_tenant_or_404(db, tenant_uuid)
    users_count = int((await db.execute(select(func.count()).select_from(User).where(User.tenant_id == tenant_uuid))).scalar() or 0)
    account_rows = await db.execute(select(AwsAccount.status, func.count()).where(AwsAccount.tenant_id == tenant_uuid).group_by(AwsAccount.status))
    action_rows = await db.execute(select(Action.status, func.count()).where(Action.tenant_id == tenant_uuid).group_by(Action.status))
    severity_rows = await db.execute(select(Finding.severity_label, func.count()).where(Finding.tenant_id == tenant_uuid).group_by(Finding.severity_label))
    now = datetime.now(timezone.utc)
    trend_24h = int((await db.execute(select(func.count()).select_from(Finding).where(Finding.tenant_id == tenant_uuid, Finding.sh_updated_at >= now - timedelta(hours=24)))).scalar() or 0)
    trend_7d = int((await db.execute(select(func.count()).select_from(Finding).where(Finding.tenant_id == tenant_uuid, Finding.sh_updated_at >= now - timedelta(days=7)))).scalar() or 0)
    trend_30d = int((await db.execute(select(func.count()).select_from(Finding).where(Finding.tenant_id == tenant_uuid, Finding.sh_updated_at >= now - timedelta(days=30)))).scalar() or 0)
    return TenantOverviewResponse(
        tenant_id=str(tenant.id),
        tenant_name=tenant.name,
        created_at=tenant.created_at.isoformat() if tenant.created_at else "",
        users_count=users_count,
        accounts_by_status={str(status): int(count) for status, count in account_rows.all()},
        actions_by_status={str(status): int(count) for status, count in action_rows.all()},
        findings_by_severity={str(sev): int(count) for sev, count in severity_rows.all()},
        findings_trend={"24h": trend_24h, "7d": trend_7d, "30d": trend_30d},
        digest_enabled=bool(tenant.digest_enabled),
        slack_configured=bool((tenant.slack_webhook_url or "").strip()),
    )


@router.get("/tenants/{tenant_id}/users", response_model=list[UserItemResponse])
async def list_tenant_users(
    tenant_id: Annotated[str, Path()],
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserItemResponse]:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    result = await db.execute(select(User).where(User.tenant_id == tenant_uuid).order_by(User.created_at.desc()))
    users = list(result.scalars().all())
    return [
        UserItemResponse(
            id=str(user.id),
            name=user.name,
            email=user.email,
            role=getattr(user.role, "value", user.role),
            created_at=user.created_at.isoformat() if user.created_at else "",
            onboarding_completed_at=user.onboarding_completed_at.isoformat() if user.onboarding_completed_at else None,
        )
        for user in users
    ]


@router.get("/tenants/{tenant_id}/aws-accounts", response_model=list[AccountItemResponse])
async def list_tenant_accounts(
    tenant_id: Annotated[str, Path()],
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AccountItemResponse]:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    result = await db.execute(select(AwsAccount).where(AwsAccount.tenant_id == tenant_uuid).order_by(AwsAccount.created_at.desc()))
    accounts = list(result.scalars().all())
    return [
        AccountItemResponse(
            id=str(account.id),
            account_id=account.account_id,
            regions=account.regions or [],
            status=getattr(account.status, "value", account.status),
            last_validated_at=account.last_validated_at.isoformat() if account.last_validated_at else None,
            created_at=account.created_at.isoformat() if account.created_at else "",
        )
        for account in accounts
    ]


@router.get("/tenants/{tenant_id}/findings", response_model=FindingsListResponse)
async def list_tenant_findings(
    tenant_id: Annotated[str, Path()],
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    account_id: Annotated[str | None, Query()] = None,
    region: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    source: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FindingsListResponse:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    query = select(Finding).where(Finding.tenant_id == tenant_uuid)
    if account_id:
        query = query.where(Finding.account_id == account_id)
    if region:
        query = query.where(Finding.region == region)
    if severity:
        query = query.where(Finding.severity_label.in_([s.strip().upper() for s in severity.split(",")]))
    if status_filter:
        query = query.where(Finding.status.in_([s.strip().upper() for s in status_filter.split(",")]))
    if source:
        query = query.where(Finding.source.in_([s.strip().lower() for s in source.split(",")]))
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0)
    result = await db.execute(query.order_by(Finding.severity_normalized.desc(), Finding.updated_at.desc()).limit(limit).offset(offset))
    findings = list(result.scalars().all())
    return FindingsListResponse(
        items=[
            FindingItemResponse(
                id=str(f.id),
                finding_id=f.finding_id,
                account_id=f.account_id,
                region=f.region,
                source=f.source,
                severity_label=f.severity_label,
                status=f.status,
                title=f.title,
                description=f.description,
                resource_id=f.resource_id,
                resource_type=f.resource_type,
                control_id=f.control_id,
                standard_name=f.standard_name,
                first_observed_at=f.first_observed_at.isoformat() if f.first_observed_at else None,
                last_observed_at=f.last_observed_at.isoformat() if f.last_observed_at else None,
                updated_at=f.sh_updated_at.isoformat() if f.sh_updated_at else None,
                created_at=f.created_at.isoformat() if f.created_at else "",
            )
            for f in findings
        ],
        total=total,
    )


@router.get("/tenants/{tenant_id}/actions", response_model=ActionsListResponse)
async def list_tenant_actions(
    tenant_id: Annotated[str, Path()],
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    account_id: Annotated[str | None, Query()] = None,
    region: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ActionsListResponse:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    query = select(Action).where(Action.tenant_id == tenant_uuid)
    if account_id:
        query = query.where(Action.account_id == account_id)
    if region:
        query = query.where(Action.region == region)
    if status_filter:
        query = query.where(Action.status == status_filter.strip().lower())
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0)
    result = await db.execute(query.order_by(Action.priority.desc(), Action.updated_at.desc()).limit(limit).offset(offset))
    actions = list(result.scalars().all())
    return ActionsListResponse(
        items=[
            ActionItemResponse(
                id=str(a.id),
                action_type=a.action_type,
                target_id=a.target_id,
                account_id=a.account_id,
                region=a.region,
                priority=a.priority,
                status=a.status,
                title=a.title,
                description=a.description,
                control_id=a.control_id,
                resource_id=a.resource_id,
                updated_at=a.updated_at.isoformat() if a.updated_at else None,
                created_at=a.created_at.isoformat() if a.created_at else None,
            )
            for a in actions
        ],
        total=total,
    )


@router.get("/tenants/{tenant_id}/remediation-runs", response_model=RemediationRunsListResponse)
async def list_tenant_remediation_runs(
    tenant_id: Annotated[str, Path()],
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RemediationRunsListResponse:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    query = select(RemediationRun).options(selectinload(RemediationRun.approved_by)).where(RemediationRun.tenant_id == tenant_uuid)
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0)
    result = await db.execute(query.order_by(RemediationRun.created_at.desc()).limit(limit).offset(offset))
    runs = list(result.scalars().all())
    return RemediationRunsListResponse(
        items=[
            RemediationRunItemResponse(
                id=str(run.id),
                action_id=str(run.action_id),
                mode=getattr(run.mode, "value", run.mode),
                status=getattr(run.status, "value", run.status),
                outcome=run.outcome,
                artifacts=_sanitize_artifacts(run.artifacts),
                approved_by_email=run.approved_by.email if run.approved_by else None,
                started_at=run.started_at.isoformat() if run.started_at else None,
                completed_at=run.completed_at.isoformat() if run.completed_at else None,
                created_at=run.created_at.isoformat() if run.created_at else "",
            )
            for run in runs
        ],
        total=total,
    )


@router.get("/tenants/{tenant_id}/exports", response_model=list[ExportItemResponse])
async def list_tenant_exports(
    tenant_id: Annotated[str, Path()],
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ExportItemResponse]:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    result = await db.execute(select(EvidenceExport).where(EvidenceExport.tenant_id == tenant_uuid).order_by(EvidenceExport.created_at.desc()).limit(100))
    exports = list(result.scalars().all())
    return [
        ExportItemResponse(
            id=str(export.id),
            status=getattr(export.status, "value", export.status),
            pack_type=getattr(export, "pack_type", "evidence") or "evidence",
            created_at=export.created_at.isoformat() if export.created_at else "",
            started_at=export.started_at.isoformat() if export.started_at else None,
            completed_at=export.completed_at.isoformat() if export.completed_at else None,
            error_message=export.error_message,
            file_size_bytes=export.file_size_bytes,
        )
        for export in exports
    ]


@router.get("/tenants/{tenant_id}/baseline-reports", response_model=list[BaselineReportItemResponse])
async def list_tenant_baseline_reports(
    tenant_id: Annotated[str, Path()],
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[BaselineReportItemResponse]:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    result = await db.execute(select(BaselineReport).where(BaselineReport.tenant_id == tenant_uuid).order_by(BaselineReport.created_at.desc()).limit(100))
    reports = list(result.scalars().all())
    return [
        BaselineReportItemResponse(
            id=str(report.id),
            status=getattr(report.status, "value", report.status),
            requested_at=report.requested_at.isoformat() if report.requested_at else "",
            completed_at=report.completed_at.isoformat() if report.completed_at else None,
            outcome=report.outcome,
            file_size_bytes=report.file_size_bytes,
        )
        for report in reports
    ]


@router.get("/tenants/{tenant_id}/notes", response_model=list[SupportNoteResponse])
async def list_support_notes(
    tenant_id: Annotated[str, Path()],
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SupportNoteResponse]:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    result = await db.execute(
        select(SupportNote)
        .options(selectinload(SupportNote.created_by))
        .where(SupportNote.tenant_id == tenant_uuid)
        .order_by(SupportNote.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    notes = list(result.scalars().all())
    return [
        SupportNoteResponse(
            id=str(note.id),
            tenant_id=str(note.tenant_id),
            created_by_user_id=str(note.created_by_user_id) if note.created_by_user_id else None,
            created_by_email=note.created_by.email if note.created_by else None,
            body=note.body,
            created_at=note.created_at.isoformat() if note.created_at else "",
        )
        for note in notes
    ]


@router.post("/tenants/{tenant_id}/notes", response_model=SupportNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_support_note(
    tenant_id: Annotated[str, Path()],
    body: SupportNoteCreateRequest,
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SupportNoteResponse:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    note_id = uuid.uuid4()
    note = SupportNote(
        id=note_id,
        tenant_id=tenant_uuid,
        created_by_user_id=admin.id,
        body=body.body.strip(),
    )
    db.add(note)
    db.add(
        AuditLog(
            tenant_id=tenant_uuid,
            event_type="support_note_created",
            entity_type="support_note",
            entity_id=note_id,
            user_id=admin.id,
            timestamp=datetime.now(timezone.utc),
            summary="Support note created by SaaS admin",
        )
    )
    await db.commit()
    await db.refresh(note)
    return SupportNoteResponse(
        id=str(note.id),
        tenant_id=str(note.tenant_id),
        created_by_user_id=str(note.created_by_user_id) if note.created_by_user_id else None,
        created_by_email=admin.email,
        body=note.body,
        created_at=note.created_at.isoformat() if note.created_at else "",
    )


@router.get("/tenants/{tenant_id}/files", response_model=list[SupportFileItemResponse])
async def list_support_files(
    tenant_id: Annotated[str, Path()],
    _admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SupportFileItemResponse]:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    result = await db.execute(
        select(SupportFile)
        .where(SupportFile.tenant_id == tenant_uuid)
        .order_by(SupportFile.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    files = list(result.scalars().all())
    return [
        SupportFileItemResponse(
            id=str(item.id),
            tenant_id=str(item.tenant_id),
            filename=item.filename,
            content_type=item.content_type,
            size_bytes=item.size_bytes,
            status=item.status,
            visible_to_tenant=item.visible_to_tenant,
            message=item.message,
            created_at=item.created_at.isoformat() if item.created_at else "",
            uploaded_at=item.uploaded_at.isoformat() if item.uploaded_at else None,
        )
        for item in files
    ]


@router.post("/tenants/{tenant_id}/files/initiate", response_model=InitiateSupportFileResponse, status_code=status.HTTP_201_CREATED)
async def initiate_support_file_upload(
    tenant_id: Annotated[str, Path()],
    body: InitiateSupportFileRequest,
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InitiateSupportFileResponse:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    bucket = (settings.S3_SUPPORT_BUCKET or "").strip()
    if not bucket:
        raise HTTPException(status_code=503, detail="S3_SUPPORT_BUCKET is not configured")
    key = f"support/{tenant_uuid}/{uuid.uuid4()}/{body.filename}"
    support_file = SupportFile(
        tenant_id=tenant_uuid,
        uploaded_by_user_id=admin.id,
        filename=body.filename,
        content_type=body.content_type,
        s3_bucket=bucket,
        s3_key=key,
        status="pending_upload",
        visible_to_tenant=body.visible_to_tenant,
        message=body.message,
    )
    db.add(support_file)
    await db.commit()
    await db.refresh(support_file)

    client = _support_s3_client()
    params: dict[str, Any] = {"Bucket": bucket, "Key": key}
    required_headers: dict[str, str] = {}
    if body.content_type:
        params["ContentType"] = body.content_type
        required_headers["Content-Type"] = body.content_type
    upload_url = client.generate_presigned_url("put_object", Params=params, ExpiresIn=3600)

    return InitiateSupportFileResponse(
        id=str(support_file.id),
        upload_url=upload_url,
        required_headers=required_headers,
    )


@router.post("/tenants/{tenant_id}/files/{file_id}/finalize", response_model=SupportFileItemResponse)
async def finalize_support_file_upload(
    tenant_id: Annotated[str, Path()],
    file_id: Annotated[str, Path()],
    body: FinalizeSupportFileRequest,
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SupportFileItemResponse:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="file_id must be a valid UUID") from exc
    result = await db.execute(select(SupportFile).where(SupportFile.id == file_uuid, SupportFile.tenant_id == tenant_uuid))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Support file not found")
    client = _support_s3_client()
    size = body.size_bytes
    try:
        head = client.head_object(Bucket=item.s3_bucket, Key=item.s3_key)
        size = size if size is not None else int(head.get("ContentLength") or 0)
    except ClientError as exc:
        raise HTTPException(status_code=409, detail="File is not uploaded yet") from exc
    item.status = "available"
    item.size_bytes = size
    item.uploaded_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            tenant_id=tenant_uuid,
            event_type="support_file_shared",
            entity_type="support_file",
            entity_id=item.id,
            user_id=admin.id,
            timestamp=datetime.now(timezone.utc),
            summary=f"Support file shared: {item.filename}",
        )
    )
    await db.commit()
    await db.refresh(item)
    return SupportFileItemResponse(
        id=str(item.id),
        tenant_id=str(item.tenant_id),
        filename=item.filename,
        content_type=item.content_type,
        size_bytes=item.size_bytes,
        status=item.status,
        visible_to_tenant=item.visible_to_tenant,
        message=item.message,
        created_at=item.created_at.isoformat() if item.created_at else "",
        uploaded_at=item.uploaded_at.isoformat() if item.uploaded_at else None,
    )


@router.post("/tenants/{tenant_id}/files/upload", response_model=SupportFileItemResponse, status_code=status.HTTP_201_CREATED)
async def upload_support_file_direct(
    tenant_id: Annotated[str, Path()],
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    message: str | None = Form(default=None),
    visible_to_tenant: bool = Form(default=True),
) -> SupportFileItemResponse:
    tenant_uuid = _parse_tenant_id(tenant_id)
    await _get_tenant_or_404(db, tenant_uuid)
    bucket = (settings.S3_SUPPORT_BUCKET or "").strip()
    if not bucket:
        raise HTTPException(status_code=503, detail="S3_SUPPORT_BUCKET is not configured")

    key = f"support/{tenant_uuid}/{uuid.uuid4()}/{file.filename}"
    client = _support_s3_client()

    # Determine size if possible
    size_bytes = None
    try:
        file.file.seek(0, 2)
        size_bytes = file.file.tell()
        file.file.seek(0)
    except Exception:
        size_bytes = None

    try:
        extra = {"ContentType": file.content_type} if file.content_type else {}
        client.upload_fileobj(file.file, bucket, key, ExtraArgs=extra)
    except ClientError as exc:
        raise HTTPException(status_code=502, detail="S3 upload failed") from exc

    support_file_id = uuid.uuid4()
    support_file = SupportFile(
        id=support_file_id,
        tenant_id=tenant_uuid,
        uploaded_by_user_id=admin.id,
        filename=file.filename,
        content_type=file.content_type,
        s3_bucket=bucket,
        s3_key=key,
        status="available",
        visible_to_tenant=visible_to_tenant,
        message=message,
        size_bytes=size_bytes,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(support_file)
    db.add(
        AuditLog(
            tenant_id=tenant_uuid,
            event_type="support_file_shared",
            entity_type="support_file",
            entity_id=support_file_id,
            user_id=admin.id,
            timestamp=datetime.now(timezone.utc),
            summary=f"Support file shared: {file.filename}",
        )
    )
    await db.commit()
    await db.refresh(support_file)

    return SupportFileItemResponse(
        id=str(support_file.id),
        tenant_id=str(support_file.tenant_id),
        filename=support_file.filename,
        content_type=support_file.content_type,
        size_bytes=support_file.size_bytes,
        status=support_file.status,
        visible_to_tenant=support_file.visible_to_tenant,
        message=support_file.message,
        created_at=support_file.created_at.isoformat() if support_file.created_at else "",
        uploaded_at=support_file.uploaded_at.isoformat() if support_file.uploaded_at else None,
    )
