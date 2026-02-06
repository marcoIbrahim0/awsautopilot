"""
Baseline report job handler (Step 13.2).

Picks up generate_baseline_report jobs from SQS, updates report status
(pending → running → success/failed), calls generate_baseline_report to build
HTML and upload to S3, then updates the baseline_reports row.
Idempotent: skips if report is already success or failed.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models.baseline_report import BaselineReport
from backend.models.enums import BaselineReportStatus
from backend.services.baseline_report_service import generate_baseline_report
from backend.services.email import email_service
from backend.services.s3_presigned import generate_presigned_url
from worker.database import session_scope

logger = logging.getLogger("worker.jobs.generate_baseline_report")

GENERATE_BASELINE_REPORT_REQUIRED_FIELDS = {"job_type", "report_id", "tenant_id", "created_at"}


def execute_generate_baseline_report_job(job: dict) -> None:
    """
    Process a generate_baseline_report job: update report row, generate HTML, upload to S3.

    Idempotent: no-op if report is already success or failed.
    On success: sets status=success, s3_bucket, s3_key, file_size_bytes, completed_at.
    On failure: sets status=failed, outcome (truncated), completed_at.

    Args:
        job: Payload with report_id, tenant_id, created_at; optional account_ids (list of str).
    """
    report_id_str = job.get("report_id")
    tenant_id_str = job.get("tenant_id")
    account_ids = job.get("account_ids")

    if not report_id_str or not tenant_id_str:
        raise ValueError("job missing report_id or tenant_id")

    try:
        report_uuid = uuid.UUID(report_id_str)
        tenant_uuid = uuid.UUID(tenant_id_str)
    except (TypeError, ValueError) as e:
        raise ValueError(f"invalid report_id/tenant_id: {e}") from e

    if account_ids is not None and not isinstance(account_ids, list):
        account_ids = None
    if account_ids is not None:
        account_ids = [str(a) for a in account_ids if a is not None]

    final_status = "unknown"
    with session_scope() as session:
        result = session.execute(
            select(BaselineReport)
            .where(
                BaselineReport.id == report_uuid,
                BaselineReport.tenant_id == tenant_uuid,
            )
            .options(
                selectinload(BaselineReport.requested_by),
                selectinload(BaselineReport.tenant),
            )
        )
        report = result.scalar_one_or_none()
        if not report:
            raise ValueError(
                f"baseline report not found: report_id={report_id_str} tenant_id={tenant_id_str}"
            )

        if report.status == BaselineReportStatus.success or report.status == BaselineReportStatus.failed:
            logger.info(
                "generate_baseline_report idempotent skip report_id=%s status=%s",
                report_id_str,
                report.status.value,
            )
            return

        if report.status != BaselineReportStatus.pending:
            logger.warning(
                "generate_baseline_report not pending report_id=%s status=%s; treating as retry",
                report_id_str,
                report.status.value,
            )

        now = datetime.now(timezone.utc)
        report.status = BaselineReportStatus.running
        report.outcome = None
        session.flush()

        try:
            bucket, key, file_size = generate_baseline_report(
                session=session,
                tenant_id=tenant_uuid,
                report_id=report_uuid,
                account_ids=account_ids,
            )
            report.status = BaselineReportStatus.success
            report.completed_at = now
            report.s3_bucket = bucket
            report.s3_key = key
            report.file_size_bytes = file_size
            report.outcome = None
            final_status = BaselineReportStatus.success.value
            logger.info(
                "generate_baseline_report success report_id=%s s3_key=%s size=%s",
                report_id_str,
                key,
                file_size,
            )
            # Optional: send "report ready" email to requested_by (Step 13.3)
            if report.requested_by and getattr(report.requested_by, "email", None):
                try:
                    download_url = generate_presigned_url(bucket, key)
                    tenant_name = (
                        (report.tenant.name or "Your organization").strip()
                        if report.tenant
                        else "Your organization"
                    )
                    if email_service.send_baseline_report_ready(
                        report.requested_by.email,
                        tenant_name,
                        download_url,
                    ):
                        logger.info(
                            "baseline report ready email sent report_id=%s to %s",
                            report_id_str,
                            report.requested_by.email,
                        )
                    else:
                        logger.warning(
                            "baseline report ready email failed report_id=%s",
                            report_id_str,
                        )
                except Exception as email_err:
                    logger.warning(
                        "baseline report ready email error report_id=%s: %s",
                        report_id_str,
                        email_err,
                    )
        except Exception as e:
            logger.exception(
                "generate_baseline_report failed report_id=%s: %s",
                report_id_str,
                e,
            )
            report.status = BaselineReportStatus.failed
            report.completed_at = now
            report.outcome = str(e)[:1000]
            final_status = BaselineReportStatus.failed.value

        session.flush()

    logger.info(
        "BaselineReport completed report_id=%s tenant_id=%s status=%s",
        report_id_str,
        tenant_id_str,
        final_status,
    )
