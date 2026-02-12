"""
Evidence export API (Step 10.4).

Lets the frontend request an evidence pack export (enqueue job), poll status,
and get a download URL when ready.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user, get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.enums import EvidenceExportStatus
from backend.models.evidence_export import EvidenceExport
from backend.models.user import User
from backend.routers.aws_accounts import get_tenant, resolve_tenant_id
from backend.utils.sqs import build_generate_export_job_payload, parse_queue_region
from backend.services.evidence_export_s3 import PRESIGNED_URL_EXPIRES_IN

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exports", tags=["exports"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

PACK_TYPE_EVIDENCE = "evidence"
PACK_TYPE_COMPLIANCE = "compliance"


class CreateExportRequest(BaseModel):
    """Request body for POST /exports (Step 12.2)."""
    pack_type: Literal["evidence", "compliance"] = Field(
        default="evidence",
        description="evidence = Step 10 only; compliance = Step 10 + exception_attestations + control_mapping + auditor_summary",
    )


class ExportCreatedResponse(BaseModel):
    """Response for POST (202 Accepted)."""

    id: str
    status: str
    created_at: str
    message: str = "Export job queued"


class ExportDetailResponse(BaseModel):
    """Response for GET /exports/{id}."""

    id: str
    status: str
    pack_type: str = "evidence"
    created_at: str
    started_at: str | None
    completed_at: str | None
    error_message: str | None
    download_url: str | None = None
    file_size_bytes: int | None = None


class ExportListItem(BaseModel):
    """Single export in list response."""

    id: str
    status: str
    pack_type: str = "evidence"
    created_at: str
    completed_at: str | None


class ExportsListResponse(BaseModel):
    """Paginated list of exports."""

    items: list[ExportListItem]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_presigned_url(bucket: str, key: str) -> str:
    """Generate a presigned GET URL for the S3 object (Step 10.5; expiry from evidence_export_s3).
    Uses AWS Signature Version 4 (required by S3 in all regions). Client region must match bucket region.
    Path-style addressing is used to avoid SignatureDoesNotMatch in some regions/proxies.
    """
    region = (settings.S3_EXPORT_BUCKET_REGION or "").strip() or settings.AWS_REGION
    s3_config = Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
    )
    s3 = boto3.client("s3", region_name=region, config=s3_config)
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=PRESIGNED_URL_EXPIRES_IN,
    )


def _export_to_detail(export: EvidenceExport) -> ExportDetailResponse:
    """Build detail response; add download_url when status is success."""
    download_url = None
    if export.status == EvidenceExportStatus.success and export.s3_bucket and export.s3_key:
        try:
            download_url = _generate_presigned_url(export.s3_bucket, export.s3_key)
        except Exception as e:
            logger.warning("Failed to generate presigned URL for export %s: %s", export.id, e)

    pack_type = getattr(export, "pack_type", None) or "evidence"
    return ExportDetailResponse(
        id=str(export.id),
        status=export.status.value,
        pack_type=pack_type,
        created_at=export.created_at.isoformat() if export.created_at else "",
        started_at=export.started_at.isoformat() if export.started_at else None,
        completed_at=export.completed_at.isoformat() if export.completed_at else None,
        error_message=export.error_message,
        download_url=download_url,
        file_size_bytes=export.file_size_bytes,
    )


# ---------------------------------------------------------------------------
# POST /exports — Create export and enqueue worker (requires auth)
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ExportCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request evidence or compliance pack export",
    description="Create an export job and enqueue the worker. pack_type: evidence (Step 10 only) or compliance (Step 10 + attestations + control_mapping + auditor_summary). Requires authentication. Poll GET /exports/{id} until status is success or failed.",
    responses={
        401: {"description": "Not authenticated"},
        503: {"description": "Export not configured or queue unavailable"},
    },
)
async def create_export(
    request: CreateExportRequest = CreateExportRequest(),
    db: Annotated[AsyncSession, Depends(get_db)] = None,  # noqa: injected by FastAPI
    current_user: Annotated[User, Depends(get_current_user)] = None,  # noqa: injected by FastAPI
) -> ExportCreatedResponse:
    """
    Create an export row (status=pending) and enqueue generate_export job.

    **pack_type:** "evidence" (default) or "compliance". **Config:** S3_EXPORT_BUCKET and SQS_EXPORT_REPORT_QUEUE_URL must be set.
    """
    tenant_uuid = current_user.tenant_id
    pack_type = (request.pack_type or "evidence").strip().lower() or "evidence"
    if pack_type not in ("evidence", "compliance"):
        pack_type = "evidence"

    if not (settings.S3_EXPORT_BUCKET and settings.S3_EXPORT_BUCKET.strip()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Evidence export not configured",
                "detail": "S3 export bucket is not configured. Set S3_EXPORT_BUCKET to enable evidence pack exports.",
            },
        )

    if not (settings.SQS_EXPORT_REPORT_QUEUE_URL and settings.SQS_EXPORT_REPORT_QUEUE_URL.strip()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Export queue unavailable",
                "detail": "Queue URL not configured. Set SQS_EXPORT_REPORT_QUEUE_URL.",
            },
        )

    export = EvidenceExport(
        tenant_id=tenant_uuid,
        status=EvidenceExportStatus.pending,
        pack_type=pack_type,
        requested_by_user_id=current_user.id,
    )
    db.add(export)
    await db.commit()
    await db.refresh(export)

    now = datetime.now(timezone.utc).isoformat()
    payload = build_generate_export_job_payload(export.id, tenant_uuid, now, pack_type=pack_type)
    queue_url = settings.SQS_EXPORT_REPORT_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)

    try:
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    except ClientError as e:
        logger.exception("SQS send_message failed for generate_export: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Export queue unavailable",
                "detail": "Could not enqueue export job. Please try again later.",
            },
        ) from e

    logger.info(
        "Created evidence export %s for tenant %s by user %s",
        export.id,
        tenant_uuid,
        current_user.id,
    )

    return ExportCreatedResponse(
        id=str(export.id),
        status=export.status.value,
        created_at=export.created_at.isoformat() if export.created_at else now,
        message="Export job queued",
    )


# ---------------------------------------------------------------------------
# GET /exports — List exports for tenant (optional auth, tenant_id query)
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ExportsListResponse,
    summary="List evidence exports",
    description="List evidence exports for the tenant (most recent first). Supports pagination and optional status filter.",
    responses={404: {"description": "Tenant not found"}},
)
async def list_exports(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)] = None,
    tenant_id: Annotated[Optional[str], Query(description="Tenant ID (required if not authenticated)")] = None,
    status_filter: Annotated[
        Optional[str],
        Query(alias="status", description="Filter by status: pending, running, success, failed"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size")] = 20,
    offset: Annotated[int, Query(ge=0, description="Offset for pagination")] = 0,
) -> ExportsListResponse:
    """List exports for the tenant with optional status filter and pagination."""
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    base_filter = select(EvidenceExport).where(EvidenceExport.tenant_id == tenant_uuid)
    if status_filter:
        try:
            status_enum = EvidenceExportStatus(status_filter)
            base_filter = base_filter.where(EvidenceExport.status == status_enum)
        except ValueError:
            pass  # ignore invalid status filter

    count_query = select(func.count()).select_from(base_filter.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = base_filter.order_by(EvidenceExport.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    exports = list(result.scalars().all())

    items = [
        ExportListItem(
            id=str(e.id),
            status=e.status.value,
            pack_type=getattr(e, "pack_type", None) or "evidence",
            created_at=e.created_at.isoformat() if e.created_at else "",
            completed_at=e.completed_at.isoformat() if e.completed_at else None,
        )
        for e in exports
    ]

    return ExportsListResponse(items=items, total=total)


# ---------------------------------------------------------------------------
# GET /exports/{export_id} — Get export by id (with presigned URL when success)
# ---------------------------------------------------------------------------


@router.get(
    "/{export_id}",
    response_model=ExportDetailResponse,
    summary="Get export by ID",
    description="Get export status and details. When status is success, download_url is a presigned URL (expires in 1 hour) to download the evidence pack zip.",
    responses={404: {"description": "Export not found"}},
)
async def get_export(
    db: Annotated[AsyncSession, Depends(get_db)],
    export_id: Annotated[str, Path(description="Export ID (UUID)")],
    current_user: Annotated[Optional[User], Depends(get_optional_user)] = None,
    tenant_id: Annotated[Optional[str], Query(description="Tenant ID (required if not authenticated)")] = None,
) -> ExportDetailResponse:
    """Get a single export by id. Returns download_url when status is success."""
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    try:
        export_uuid = uuid.UUID(export_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Export not found", "detail": "Invalid export ID"},
        ) from None

    result = await db.execute(
        select(EvidenceExport).where(
            EvidenceExport.id == export_uuid,
            EvidenceExport.tenant_id == tenant_uuid,
        )
    )
    export = result.scalar_one_or_none()
    if not export:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Export not found", "detail": f"No export found with ID {export_id}"},
        )

    return _export_to_detail(export)
