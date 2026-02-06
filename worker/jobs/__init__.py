"""
Job handlers registry. Routes by job_type to the appropriate handler function.
"""
from __future__ import annotations

from typing import Callable

from backend.utils.sqs import (
    COMPUTE_ACTIONS_JOB_TYPE,
    GENERATE_BASELINE_REPORT_JOB_TYPE,
    GENERATE_EXPORT_JOB_TYPE,
    INGEST_ACCESS_ANALYZER_JOB_TYPE,
    INGEST_INSPECTOR_JOB_TYPE,
    INGEST_JOB_TYPE,
    REMEDIATION_RUN_JOB_TYPE,
    WEEKLY_DIGEST_JOB_TYPE,
)
from worker.jobs.compute_actions import execute_compute_actions_job
from worker.jobs.evidence_export import execute_evidence_export_job
from worker.jobs.generate_baseline_report import execute_generate_baseline_report_job
from worker.jobs.ingest_access_analyzer import execute_ingest_access_analyzer_job
from worker.jobs.ingest_findings import execute_ingest_job
from worker.jobs.ingest_inspector import execute_ingest_inspector_job
from worker.jobs.remediation_run import execute_remediation_run_job
from worker.jobs.weekly_digest import execute_weekly_digest_job

# Registry: job_type → handler(job: dict) -> None
_HANDLERS: dict[str, Callable[[dict], None]] = {
    INGEST_JOB_TYPE: execute_ingest_job,
    INGEST_ACCESS_ANALYZER_JOB_TYPE: execute_ingest_access_analyzer_job,
    INGEST_INSPECTOR_JOB_TYPE: execute_ingest_inspector_job,
    COMPUTE_ACTIONS_JOB_TYPE: execute_compute_actions_job,
    REMEDIATION_RUN_JOB_TYPE: execute_remediation_run_job,
    GENERATE_EXPORT_JOB_TYPE: execute_evidence_export_job,
    GENERATE_BASELINE_REPORT_JOB_TYPE: execute_generate_baseline_report_job,
    WEEKLY_DIGEST_JOB_TYPE: execute_weekly_digest_job,
}


def get_job_handler(job_type: str) -> Callable[[dict], None] | None:
    """
    Get the handler function for the given job_type.

    Returns None if job_type is unknown.
    """
    return _HANDLERS.get(job_type)


__all__ = ["get_job_handler"]
