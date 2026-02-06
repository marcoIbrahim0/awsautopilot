"""
Shared SQS / ingest-job helpers. Used by API (enqueue) and worker (parse region, job contract).
"""
from __future__ import annotations

import uuid

from backend.config import settings

INGEST_JOB_TYPE = "ingest_findings"
INGEST_ACCESS_ANALYZER_JOB_TYPE = "ingest_access_analyzer"
INGEST_INSPECTOR_JOB_TYPE = "ingest_inspector"
COMPUTE_ACTIONS_JOB_TYPE = "compute_actions"
REMEDIATION_RUN_JOB_TYPE = "remediation_run"
GENERATE_EXPORT_JOB_TYPE = "generate_export"
WEEKLY_DIGEST_JOB_TYPE = "weekly_digest"
GENERATE_BASELINE_REPORT_JOB_TYPE = "generate_baseline_report"


def parse_queue_region(queue_url: str) -> str:
    """Extract region from SQS queue URL (e.g. https://sqs.eu-north-1.amazonaws.com/...)."""
    try:
        parts = (queue_url or "").strip().split(".")
        if len(parts) >= 3 and (parts[0] or "").endswith("//sqs"):
            return parts[1] or settings.AWS_REGION
    except Exception:
        pass
    return settings.AWS_REGION


def build_ingest_job_payload(
    tenant_id: uuid.UUID,
    account_id: str,
    region: str,
    created_at: str,
) -> dict:
    """Build ingest job dict for SQS. Matches worker contract (REQUIRED_JOB_FIELDS + created_at)."""
    return {
        "tenant_id": str(tenant_id),
        "account_id": account_id,
        "region": region,
        "job_type": INGEST_JOB_TYPE,
        "created_at": created_at,
    }


def build_ingest_access_analyzer_job_payload(
    tenant_id: uuid.UUID,
    account_id: str,
    region: str,
    created_at: str,
) -> dict:
    """Build ingest_access_analyzer job dict for SQS (Step 2B.1). Same shape as ingest_findings."""
    return {
        "tenant_id": str(tenant_id),
        "account_id": account_id,
        "region": region,
        "job_type": INGEST_ACCESS_ANALYZER_JOB_TYPE,
        "created_at": created_at,
    }


def build_ingest_inspector_job_payload(
    tenant_id: uuid.UUID,
    account_id: str,
    region: str,
    created_at: str,
) -> dict:
    """Build ingest_inspector job dict for SQS (Step 2B.2). Same shape as ingest_findings."""
    return {
        "tenant_id": str(tenant_id),
        "account_id": account_id,
        "region": region,
        "job_type": INGEST_INSPECTOR_JOB_TYPE,
        "created_at": created_at,
    }


def build_compute_actions_job_payload(
    tenant_id: uuid.UUID,
    created_at: str,
    account_id: str | None = None,
    region: str | None = None,
) -> dict:
    """
    Build compute_actions job dict for SQS.
    Omit account_id/region for tenant-wide computation.
    """
    payload: dict = {
        "tenant_id": str(tenant_id),
        "job_type": COMPUTE_ACTIONS_JOB_TYPE,
        "created_at": created_at,
    }
    if account_id is not None:
        payload["account_id"] = account_id
    if region is not None:
        payload["region"] = region
    return payload


def build_remediation_run_job_payload(
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    mode: str,
    created_at: str,
) -> dict:
    """
    Build remediation_run job dict for SQS.
    Worker consumes this to update run status, call PR bundle scaffold, etc.
    """
    return {
        "job_type": REMEDIATION_RUN_JOB_TYPE,
        "run_id": str(run_id),
        "tenant_id": str(tenant_id),
        "action_id": str(action_id),
        "mode": mode,
        "created_at": created_at,
    }


def build_generate_export_job_payload(
    export_id: uuid.UUID,
    tenant_id: uuid.UUID,
    created_at: str,
    pack_type: str = "evidence",
) -> dict:
    """
    Build generate_export job dict for SQS (Step 10.3, 12.2).
    Worker consumes this to generate evidence or compliance pack, zip, upload to S3.
    pack_type: "evidence" (Step 10 only) or "compliance" (Step 10 + attestations + control_mapping + auditor_summary).
    """
    return {
        "job_type": GENERATE_EXPORT_JOB_TYPE,
        "export_id": str(export_id),
        "tenant_id": str(tenant_id),
        "created_at": created_at,
        "pack_type": (pack_type or "evidence").strip().lower() or "evidence",
    }


def build_weekly_digest_job_payload(tenant_id: uuid.UUID, created_at: str) -> dict:
    """
    Build weekly_digest job dict for SQS (Step 11.1).
    One job per tenant; worker builds digest payload and updates last_digest_sent_at.
    """
    return {
        "job_type": WEEKLY_DIGEST_JOB_TYPE,
        "tenant_id": str(tenant_id),
        "created_at": created_at,
    }


def build_generate_baseline_report_job_payload(
    report_id: uuid.UUID,
    tenant_id: uuid.UUID,
    created_at: str,
    account_ids: list[str] | None = None,
) -> dict:
    """
    Build generate_baseline_report job dict for SQS (Step 13.2).
    Worker consumes this to build report data, render HTML, upload to S3.
    account_ids: optional list of account IDs to include; if omitted, all accounts.
    """
    payload: dict = {
        "job_type": GENERATE_BASELINE_REPORT_JOB_TYPE,
        "report_id": str(report_id),
        "tenant_id": str(tenant_id),
        "created_at": created_at,
    }
    if account_ids is not None:
        payload["account_ids"] = account_ids
    return payload
