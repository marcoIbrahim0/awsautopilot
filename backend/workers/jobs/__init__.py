"""
Job handlers registry. Routes by job_type to the appropriate handler function.
"""
from __future__ import annotations

from typing import Callable

from backend.utils.sqs import (
    BACKFILL_ACTION_GROUPS_JOB_TYPE,
    BACKFILL_FINDING_KEYS_JOB_TYPE,
    COMPUTE_ACTIONS_JOB_TYPE,
    EXECUTE_PR_BUNDLE_APPLY_JOB_TYPE,
    EXECUTE_PR_BUNDLE_PLAN_JOB_TYPE,
    GENERATE_BASELINE_REPORT_JOB_TYPE,
    GENERATE_EXPORT_JOB_TYPE,
    INGEST_CONTROL_PLANE_EVENTS_JOB_TYPE,
    INGEST_ACCESS_ANALYZER_JOB_TYPE,
    INGEST_INSPECTOR_JOB_TYPE,
    INGEST_JOB_TYPE,
    RECONCILE_INVENTORY_GLOBAL_ORCHESTRATION_JOB_TYPE,
    RECONCILE_INVENTORY_SHARD_JOB_TYPE,
    RECONCILE_RECENTLY_TOUCHED_RESOURCES_JOB_TYPE,
    REMEDIATION_RUN_JOB_TYPE,
    WEEKLY_DIGEST_JOB_TYPE,
)
from backend.workers.jobs.backfill_action_groups import execute_backfill_action_groups_job
from backend.workers.jobs.backfill_finding_keys import execute_backfill_finding_keys_job
from backend.workers.jobs.compute_actions import execute_compute_actions_job
from backend.workers.jobs.evidence_export import execute_evidence_export_job
from backend.workers.jobs.generate_baseline_report import execute_generate_baseline_report_job
from backend.workers.jobs.ingest_control_plane_events import execute_ingest_control_plane_events_job
from backend.workers.jobs.ingest_access_analyzer import execute_ingest_access_analyzer_job
from backend.workers.jobs.ingest_findings import execute_ingest_job
from backend.workers.jobs.ingest_inspector import execute_ingest_inspector_job
from backend.workers.jobs.reconcile_inventory_shard import execute_reconcile_inventory_shard_job
from backend.workers.jobs.reconcile_inventory_global_orchestration import (
    execute_reconcile_inventory_global_orchestration_job,
)
from backend.workers.jobs.reconcile_recently_touched_resources import (
    execute_reconcile_recently_touched_resources_job,
)
from backend.workers.jobs.remediation_run import execute_remediation_run_job
from backend.workers.jobs.remediation_run_execution import execute_pr_bundle_execution_job
from backend.workers.jobs.weekly_digest import execute_weekly_digest_job

# Registry: job_type → handler(job: dict) -> None
_HANDLERS: dict[str, Callable[[dict], None]] = {
    BACKFILL_ACTION_GROUPS_JOB_TYPE: execute_backfill_action_groups_job,
    BACKFILL_FINDING_KEYS_JOB_TYPE: execute_backfill_finding_keys_job,
    INGEST_JOB_TYPE: execute_ingest_job,
    INGEST_ACCESS_ANALYZER_JOB_TYPE: execute_ingest_access_analyzer_job,
    INGEST_INSPECTOR_JOB_TYPE: execute_ingest_inspector_job,
    INGEST_CONTROL_PLANE_EVENTS_JOB_TYPE: execute_ingest_control_plane_events_job,
    COMPUTE_ACTIONS_JOB_TYPE: execute_compute_actions_job,
    RECONCILE_INVENTORY_GLOBAL_ORCHESTRATION_JOB_TYPE: execute_reconcile_inventory_global_orchestration_job,
    RECONCILE_INVENTORY_SHARD_JOB_TYPE: execute_reconcile_inventory_shard_job,
    RECONCILE_RECENTLY_TOUCHED_RESOURCES_JOB_TYPE: execute_reconcile_recently_touched_resources_job,
    REMEDIATION_RUN_JOB_TYPE: execute_remediation_run_job,
    EXECUTE_PR_BUNDLE_PLAN_JOB_TYPE: execute_pr_bundle_execution_job,
    EXECUTE_PR_BUNDLE_APPLY_JOB_TYPE: execute_pr_bundle_execution_job,
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
