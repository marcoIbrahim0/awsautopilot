"""
Evidence export job handler (Step 10.3).

Picks up generate_export jobs from SQS, updates export status (pending → running → success/failed),
calls generate_evidence_pack to build zip and upload to S3, then updates the export row.
Idempotent: skips if export is already success or failed.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models.enums import EvidenceExportStatus
from backend.models.evidence_export import EvidenceExport
from backend.services.evidence_export import generate_evidence_pack
from worker.database import session_scope

logger = logging.getLogger("worker.jobs.evidence_export")

# ---------------------------------------------------------------------------
# Contract: job dict must have job_type, export_id, tenant_id, created_at
# ---------------------------------------------------------------------------

GENERATE_EXPORT_REQUIRED_FIELDS = {"job_type", "export_id", "tenant_id", "created_at"}


def execute_evidence_export_job(job: dict) -> None:
    """
    Process a generate_export job: update export row, generate pack, zip, upload to S3.

    Idempotent: no-op if export is already success or failed.
    On success: sets status=success, s3_bucket, s3_key, file_size_bytes, completed_at.
    On failure: sets status=failed, error_message (truncated), completed_at.

    Args:
        job: Payload with export_id, tenant_id, created_at; optional pack_type ("evidence" | "compliance").
    """
    export_id_str = job.get("export_id")
    tenant_id_str = job.get("tenant_id")

    if not export_id_str or not tenant_id_str:
        raise ValueError("job missing export_id or tenant_id")

    try:
        export_uuid = uuid.UUID(export_id_str)
        tenant_uuid = uuid.UUID(tenant_id_str)
    except (TypeError, ValueError) as e:
        raise ValueError(f"invalid export_id/tenant_id: {e}") from e

    final_status = "unknown"
    with session_scope() as session:
        result = session.execute(
            select(EvidenceExport)
            .where(
                EvidenceExport.id == export_uuid,
                EvidenceExport.tenant_id == tenant_uuid,
            )
            .options(selectinload(EvidenceExport.requested_by))
        )
        export = result.scalar_one_or_none()
        if not export:
            raise ValueError(
                f"evidence export not found: export_id={export_id_str} tenant_id={tenant_id_str}"
            )

        # Idempotency: do not overwrite completed exports
        if export.status == EvidenceExportStatus.success or export.status == EvidenceExportStatus.failed:
            logger.info(
                "evidence_export idempotent skip export_id=%s status=%s",
                export_id_str,
                export.status.value,
            )
            return

        if export.status != EvidenceExportStatus.pending:
            logger.warning(
                "evidence_export not pending export_id=%s status=%s; treating as retry, setting running",
                export_id_str,
                export.status.value,
            )

        now = datetime.now(timezone.utc)
        export.status = EvidenceExportStatus.running
        export.started_at = now
        export.error_message = None
        session.flush()

        requested_by_email = "unknown"
        if export.requested_by:
            requested_by_email = export.requested_by.email or str(export.requested_by_user_id)
        elif export.requested_by_user_id:
            requested_by_email = str(export.requested_by_user_id)

        export_created_at = export.created_at.isoformat() if export.created_at else now.isoformat()

        pack_type = (job.get("pack_type") or "evidence").strip().lower() or "evidence"
        if pack_type not in ("evidence", "compliance"):
            pack_type = "evidence"

        try:
            bucket, key, file_size = generate_evidence_pack(
                session=session,
                tenant_id=tenant_uuid,
                export_id=export_uuid,
                requested_by_email=requested_by_email,
                export_created_at=export_created_at,
                pack_type=pack_type,
            )
            export.status = EvidenceExportStatus.success
            export.completed_at = datetime.now(timezone.utc)
            export.s3_bucket = bucket
            export.s3_key = key
            export.file_size_bytes = file_size
            export.error_message = None
            final_status = EvidenceExportStatus.success.value
            logger.info(
                "evidence_export success export_id=%s s3_key=%s size=%s",
                export_id_str,
                key,
                file_size,
            )
        except Exception as e:
            logger.exception("evidence_export failed export_id=%s: %s", export_id_str, e)
            export.status = EvidenceExportStatus.failed
            export.completed_at = datetime.now(timezone.utc)
            export.error_message = str(e)[:1000]
            final_status = EvidenceExportStatus.failed.value

        session.flush()

    logger.info(
        "EvidenceExport completed export_id=%s tenant_id=%s status=%s",
        export_id_str,
        tenant_id_str,
        final_status,
    )
