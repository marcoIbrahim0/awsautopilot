"""
Baseline report API (Step 13.3).

POST: request a baseline report (enqueue job). GET: status and presigned download URL.
Rate limit: one report per tenant per 24 hours. Optional email when ready (worker).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.config import settings
from backend.database import get_db
from backend.models.baseline_report import BaselineReport
from backend.models.enums import BaselineReportStatus
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.services.baseline_report_builder import build_baseline_report_data
from backend.services.baseline_report_spec import BaselineReportData
from backend.services.s3_presigned import generate_presigned_url
from backend.utils.sqs import (
    build_generate_baseline_report_job_payload,
    parse_queue_region,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/baseline-report", tags=["baseline-report"])

# Rate limit: one report per tenant per 24 hours
BASELINE_REPORT_RATE_LIMIT_HOURS = 24


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CreateBaselineReportRequest(BaseModel):
    """Request body for POST /baseline-report (Step 13.3)."""
    account_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of account IDs to include; if omitted, all accounts for the tenant.",
    )


class BaselineReportCreatedResponse(BaseModel):
    """Response for POST (201 Created)."""
    id: str
    status: str
    requested_at: str
    message: str = "Baseline report job queued. Report will be ready within 48 hours."


class BaselineReportDetailResponse(BaseModel):
    """Response for GET /baseline-report/{id}."""
    id: str
    status: str
    requested_at: str
    completed_at: Optional[str] = None
    file_size_bytes: Optional[int] = None
    download_url: Optional[str] = None
    outcome: Optional[str] = None


class BaselineReportListItem(BaseModel):
    """Single report in list."""
    id: str
    status: str
    requested_at: str
    completed_at: Optional[str] = None


class BaselineReportListResponse(BaseModel):
    """Paginated list of baseline reports."""
    items: List[BaselineReportListItem]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _report_to_detail(report: BaselineReport) -> BaselineReportDetailResponse:
    """Build detail response; add download_url when status is success."""
    download_url = None
    if (
        report.status == BaselineReportStatus.success
        and report.s3_bucket
        and report.s3_key
    ):
        try:
            download_url = generate_presigned_url(
                report.s3_bucket,
                report.s3_key,
            )
        except Exception as e:
            logger.warning(
                "Failed to generate presigned URL for baseline report %s: %s",
                report.id,
                e,
            )
    return BaselineReportDetailResponse(
        id=str(report.id),
        status=report.status.value,
        requested_at=report.requested_at.isoformat() if report.requested_at else "",
        completed_at=report.completed_at.isoformat() if report.completed_at else None,
        file_size_bytes=report.file_size_bytes,
        download_url=download_url,
        outcome=report.outcome,
    )


def _parse_report_uuid(report_id: str) -> uuid.UUID:
    """Parse report_id UUID or raise 404."""
    try:
        return uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Report not found", "detail": "Invalid report ID"},
        ) from None


async def _load_report_for_tenant(
    db: AsyncSession,
    *,
    report_id: uuid.UUID,
    tenant_id: uuid.UUID,
    report_id_raw: str,
) -> BaselineReport:
    """Load tenant-scoped report row or raise 404."""
    result = await db.execute(
        select(BaselineReport).where(
            BaselineReport.id == report_id,
            BaselineReport.tenant_id == tenant_id,
        )
    )
    report = result.scalar_one_or_none()
    if report:
        return report
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "Report not found", "detail": f"No report found with ID {report_id_raw}"},
    )


def _normalize_account_ids(account_ids: object) -> list[str] | None:
    """Normalize stored account_ids JSON value to optional list[str]."""
    if not isinstance(account_ids, list):
        return None
    normalized = [str(account_id) for account_id in account_ids if isinstance(account_id, str)]
    return normalized or None


async def _load_tenant_name(db: AsyncSession, tenant_id: uuid.UUID) -> str | None:
    """Return tenant display name when present."""
    result = await db.execute(select(Tenant.name).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def _build_report_view_data(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_ids_raw: object,
) -> BaselineReportData:
    """Build in-app viewer payload from current tenant findings."""
    tenant_name = await _load_tenant_name(db, tenant_id)
    account_ids = _normalize_account_ids(account_ids_raw)
    return await db.run_sync(
        lambda session: build_baseline_report_data(
            session,
            tenant_id=str(tenant_id),
            account_ids=account_ids,
            tenant_name=tenant_name,
        )
    )


# ---------------------------------------------------------------------------
# POST /baseline-report — Create report and enqueue worker
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=BaselineReportCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request baseline report",
    description="Create a baseline report job. Report will be ready within 48 hours. Rate limit: one report per tenant per 24 hours. Poll GET /baseline-report/{id} for status and download URL.",
    responses={
        401: {"description": "Not authenticated"},
        429: {"description": "Rate limit exceeded (one report per tenant per 24h)"},
        503: {"description": "Baseline report or queue not configured"},
    },
)
async def create_baseline_report(
    request: CreateBaselineReportRequest = CreateBaselineReportRequest(),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> BaselineReportCreatedResponse:
    """
    Create a baseline report row (status=pending) and enqueue generate_baseline_report job.

    **account_ids:** Optional; if provided, report includes only those accounts.
    **Rate limit:** One report per tenant per 24 hours (429 with Retry-After).
    """
    tenant_uuid = current_user.tenant_id

    if not (settings.S3_EXPORT_BUCKET and settings.S3_EXPORT_BUCKET.strip()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Baseline report not configured",
                "detail": "S3 export bucket is not configured. Set S3_EXPORT_BUCKET.",
            },
        )
    if not (settings.SQS_EXPORT_REPORT_QUEUE_URL and settings.SQS_EXPORT_REPORT_QUEUE_URL.strip()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Queue unavailable",
                "detail": "SQS_EXPORT_REPORT_QUEUE_URL is not configured.",
            },
        )

    # Rate limit: one report per tenant per 24h
    since = datetime.now(timezone.utc) - timedelta(hours=BASELINE_REPORT_RATE_LIMIT_HOURS)
    rate_result = await db.execute(
        select(BaselineReport)
        .where(
            BaselineReport.tenant_id == tenant_uuid,
            BaselineReport.created_at >= since,
        )
        .order_by(BaselineReport.created_at.desc())
        .limit(1)
    )
    recent = rate_result.scalar_one_or_none()
    if recent:
        created = recent.created_at
        if getattr(created, "tzinfo", None) is None:
            created = created.replace(tzinfo=timezone.utc)
        next_allowed = created + timedelta(hours=BASELINE_REPORT_RATE_LIMIT_HOURS)
        retry_after = int((next_allowed - datetime.now(timezone.utc)).total_seconds())
        retry_after = max(1, min(retry_after, 86400))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "detail": "One baseline report per tenant per 24 hours. Try again later.",
            },
            headers={"Retry-After": str(retry_after)},
        )

    # Validate account_ids if provided
    account_ids = request.account_ids
    if account_ids is not None:
        if not isinstance(account_ids, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid request", "detail": "account_ids must be a list of strings."},
            )
        for a in account_ids:
            if not isinstance(a, str) or len(a) != 12 or not a.isdigit():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Invalid request", "detail": "Each account_id must be a 12-digit string."},
                )

    now = datetime.now(timezone.utc)
    report = BaselineReport(
        tenant_id=tenant_uuid,
        status=BaselineReportStatus.pending,
        requested_by_user_id=current_user.id,
        requested_at=now,
        account_ids=account_ids,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    now_iso = now.isoformat()
    payload = build_generate_baseline_report_job_payload(
        report_id=report.id,
        tenant_id=tenant_uuid,
        created_at=now_iso,
        account_ids=account_ids,
    )
    queue_url = settings.SQS_EXPORT_REPORT_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    try:
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    except ClientError as e:
        logger.exception("SQS send_message failed for generate_baseline_report: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Queue unavailable",
                "detail": "Could not enqueue report job. Please try again later.",
            },
        ) from e

    logger.info(
        "Created baseline report %s for tenant %s by user %s",
        report.id,
        tenant_uuid,
        current_user.id,
    )
    return BaselineReportCreatedResponse(
        id=str(report.id),
        status=report.status.value,
        requested_at=report.requested_at.isoformat() if report.requested_at else now_iso,
        message="Baseline report job queued. Report will be ready within 48 hours.",
    )


# ---------------------------------------------------------------------------
# GET /baseline-report — List reports for tenant
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=BaselineReportListResponse,
    summary="List baseline reports",
    description="List baseline reports for the authenticated tenant (most recent first).",
)
async def list_baseline_reports(
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size")] = 20,
    offset: Annotated[int, Query(ge=0, description="Offset")] = 0,
) -> BaselineReportListResponse:
    """List baseline reports for the tenant."""
    tenant_uuid = current_user.tenant_id
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count()).select_from(BaselineReport).where(BaselineReport.tenant_id == tenant_uuid)
    )
    total = count_result.scalar() or 0
    query = (
        select(BaselineReport)
        .where(BaselineReport.tenant_id == tenant_uuid)
        .order_by(BaselineReport.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    reports = list(result.scalars().all())
    items = [
        BaselineReportListItem(
            id=str(r.id),
            status=r.status.value,
            requested_at=r.requested_at.isoformat() if r.requested_at else "",
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )
        for r in reports
    ]
    return BaselineReportListResponse(items=items, total=total)


# ---------------------------------------------------------------------------
# GET /baseline-report/{id} — Get report by id (with presigned URL when success)
# ---------------------------------------------------------------------------


@router.get(
    "/{report_id}",
    response_model=BaselineReportDetailResponse,
    summary="Get baseline report by ID",
    description="Get report status and details. When status is success, download_url is a presigned URL (expires in 1 hour) to download the report. Cache-Control: no-store for time-limited URL.",
    responses={404: {"description": "Report not found"}},
)
async def get_baseline_report(
    report_id: Annotated[str, Path(description="Report ID (UUID)")],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
):
    """Get a single baseline report by id. Returns download_url when status is success. Cache-Control: no-store."""
    tenant_uuid = current_user.tenant_id
    report_uuid = _parse_report_uuid(report_id)
    report = await _load_report_for_tenant(
        db,
        report_id=report_uuid,
        tenant_id=tenant_uuid,
        report_id_raw=report_id,
    )

    body = _report_to_detail(report)
    return JSONResponse(
        content=body.model_dump(),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


# ---------------------------------------------------------------------------
# GET /baseline-report/{id}/data — In-app report viewer payload
# ---------------------------------------------------------------------------


@router.get(
    "/{report_id}/data",
    response_model=BaselineReportData,
    summary="Get baseline report data by ID",
    description="Return structured report payload for in-app viewer. Report must exist in tenant scope and be in success status.",
    responses={
        404: {"description": "Report not found"},
        409: {"description": "Report is not ready yet"},
    },
)
async def get_baseline_report_data(
    report_id: Annotated[str, Path(description="Report ID (UUID)")],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
):
    """Return structured baseline report payload for the in-app viewer."""
    tenant_uuid = current_user.tenant_id
    report_uuid = _parse_report_uuid(report_id)
    report = await _load_report_for_tenant(
        db,
        report_id=report_uuid,
        tenant_id=tenant_uuid,
        report_id_raw=report_id,
    )
    if report.status != BaselineReportStatus.success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Report not ready",
                "detail": "Baseline report is not yet available for viewer data.",
                "status": report.status.value,
            },
        )

    view_data = await _build_report_view_data(
        db,
        tenant_id=tenant_uuid,
        account_ids_raw=report.account_ids,
    )
    return JSONResponse(
        content=view_data.model_dump(mode="json"),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )
