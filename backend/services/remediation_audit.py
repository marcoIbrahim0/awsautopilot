"""
Remediation run audit semantics (Step 7.5).

The remediation_runs table is the primary audit record for every remediation run:
who (approved_by_user_id), when (started_at, completed_at), what (action_id, mode),
and outcome (status, outcome, logs, artifacts). Once a run reaches status success
or failed, outcome, logs, and artifacts are immutable—no updates or overwrites.
This satisfies the remediation safety rule: "Full audit log for every run."
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Union

from sqlalchemy.orm import Session

from backend.models.remediation_run import RemediationRun
from backend.models.enums import RemediationRunStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Immutability guards
# ---------------------------------------------------------------------------

COMPLETED_STATUSES = (RemediationRunStatus.success, RemediationRunStatus.failed)


def is_run_completed(status: Union[str, RemediationRunStatus]) -> bool:
    """
    Return True if the run is in a terminal state (success or failed).

    Completed runs are immutable for outcome, logs, and artifacts.
    """
    if isinstance(status, RemediationRunStatus):
        return status in COMPLETED_STATUSES
    return str(status).strip().lower() in ("success", "failed")


def allow_update_outcome(run: RemediationRun) -> bool:
    """
    Return True if outcome, logs, or artifacts may be updated for this run.

    Only pending or running runs may be updated. Used by the worker before
    writing outcome/logs/artifacts and by any future PATCH API to reject
    updates to completed runs.
    """
    return not is_run_completed(run.status)


# ---------------------------------------------------------------------------
# Optional: one-line audit_log table entry for compliance dashboards
# ---------------------------------------------------------------------------

AUDIT_EVENT_REMEDIATION_RUN_COMPLETED = "remediation_run_completed"
AUDIT_EVENT_REMEDIATION_MUTATION_BLOCKED = "remediation_mutation_blocked"
AUDIT_ENTITY_REMEDIATION_RUN = "remediation_run"


def write_remediation_run_audit(session: Session, run: RemediationRun) -> None:
    """
    Write a one-line summary to the audit_log table when a remediation run completes.

    Used for compliance dashboards and search. The remediation_runs row remains
    the source of truth; this is an optional denormalized summary.

    Call only after run.status is set to success or failed and run.completed_at is set.
    """
    if not is_run_completed(run.status):
        logger.warning("write_remediation_run_audit called for non-completed run %s", run.id)
        return

    summary = (
        f"run_id={run.id} action_id={run.action_id} mode={run.mode.value} "
        f"status={run.status.value} outcome={run.outcome or ''}"
    )
    _write_audit_entry(
        session,
        tenant_id=run.tenant_id,
        event_type=AUDIT_EVENT_REMEDIATION_RUN_COMPLETED,
        entity_id=run.id,
        user_id=run.approved_by_user_id,
        timestamp=run.completed_at or run.updated_at,
        summary=summary,
    )
    logger.debug("Audit log entry created for remediation run %s", run.id)


def write_blocked_mutation_audit(
    session: Session,
    run: RemediationRun,
    *,
    reason: str,
    detail: str,
    requested_mode: str,
    approval_path: str | None,
) -> None:
    """Record an explicit audit event when an unapproved mutation attempt is blocked."""
    summary = (
        f"run_id={run.id} action_id={run.action_id} requested_mode={requested_mode} "
        f"reason={reason} approval_path={approval_path or 'missing'} detail={detail}"
    )
    _write_audit_entry(
        session,
        tenant_id=run.tenant_id,
        event_type=AUDIT_EVENT_REMEDIATION_MUTATION_BLOCKED,
        entity_id=run.id,
        user_id=run.approved_by_user_id,
        timestamp=datetime.now(timezone.utc),
        summary=summary,
    )
    logger.info("Blocked remediation mutation audit recorded for run %s reason=%s", run.id, reason)


def _write_audit_entry(
    session: Session,
    *,
    tenant_id: object,
    event_type: str,
    entity_id: object,
    user_id: object,
    timestamp: object,
    summary: str,
) -> None:
    from backend.models.audit_log import AuditLog

    entry = AuditLog(
        tenant_id=tenant_id,
        event_type=event_type,
        entity_type=AUDIT_ENTITY_REMEDIATION_RUN,
        entity_id=entity_id,
        user_id=user_id,
        timestamp=timestamp,
        summary=_truncate_summary(summary),
    )
    session.add(entry)


def _truncate_summary(summary: str) -> str:
    if len(summary) <= 500:
        return summary
    return summary[:497] + "..."


__all__ = [
    "is_run_completed",
    "allow_update_outcome",
    "write_remediation_run_audit",
    "write_blocked_mutation_audit",
    "COMPLETED_STATUSES",
    "AUDIT_EVENT_REMEDIATION_RUN_COMPLETED",
    "AUDIT_EVENT_REMEDIATION_MUTATION_BLOCKED",
    "AUDIT_ENTITY_REMEDIATION_RUN",
]
