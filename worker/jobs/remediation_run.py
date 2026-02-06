"""
Remediation run job handler (Step 7.3 + 8.3).

Picks up remediation_run jobs from SQS, updates run status (pending → running → success/failed),
calls PR bundle scaffold for pr_only, or direct fix executor for direct_fix. Idempotent: skips
if run already success or failed.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.aws_account import AwsAccount
from backend.models.enums import RemediationRunMode, RemediationRunStatus
from backend.models.remediation_run import RemediationRun
from backend.services.pr_bundle import generate_pr_bundle
from backend.services.remediation_audit import allow_update_outcome, write_remediation_run_audit
from worker.database import session_scope
from worker.services.aws import assume_role
from worker.services.direct_fix import run_direct_fix

logger = logging.getLogger("worker.jobs.remediation_run")

# ---------------------------------------------------------------------------
# Contract: job dict must have job_type, run_id, tenant_id, action_id, mode, created_at
# ---------------------------------------------------------------------------

REMEDIATION_RUN_REQUIRED_FIELDS = {"job_type", "run_id", "tenant_id", "action_id", "mode", "created_at"}


def _execute_direct_fix(session: Session, run: RemediationRun, log_lines: list[str]) -> None:
    """
    Execute direct fix: load action and account, assume WriteRole, call run_direct_fix.
    Updates run.outcome, run.logs, run.status, run.completed_at, run.artifacts.
    """
    action = run.action
    if not action:
        run.outcome = "Action not found (may have been deleted)"
        run.status = RemediationRunStatus.failed
        log_lines.append(run.outcome)
        return

    # Load AWS account (tenant + account_id)
    acc_result = session.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == run.tenant_id,
            AwsAccount.account_id == action.account_id,
        )
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        run.outcome = "AWS account not found for this action"
        run.status = RemediationRunStatus.failed
        log_lines.append(run.outcome)
        return

    if not account.role_write_arn:
        run.outcome = (
            "WriteRole not configured for this account. "
            "Use PR-only or add WriteRole ARN in account settings."
        )
        run.status = RemediationRunStatus.failed
        log_lines.append(run.outcome)
        return

    # Assume WriteRole
    log_lines.append("Assuming WriteRole.")
    try:
        wr_session = assume_role(
            role_arn=account.role_write_arn,
            external_id=account.external_id,
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        run.outcome = f"Failed to assume WriteRole: {code}"
        run.status = RemediationRunStatus.failed
        log_lines.append(f"AssumeRole failed: {code} - {msg}")
        return
    except Exception as e:
        logger.exception("Assume WriteRole failed for run_id=%s: %s", run.id, e)
        run.outcome = f"Failed to assume WriteRole: {e}"
        run.status = RemediationRunStatus.failed
        log_lines.append(str(e))
        return

    # Run direct fix executor
    log_lines.append(f"Running direct fix: action_type={action.action_type}.")
    try:
        result = run_direct_fix(
            wr_session,
            action_type=action.action_type,
            account_id=action.account_id,
            region=action.region,
            run_id=run.id,
            action_id=action.id,
        )
    except Exception as e:
        logger.exception("Direct fix executor failed for run_id=%s: %s", run.id, e)
        run.outcome = f"Direct fix failed: {e}"
        run.status = RemediationRunStatus.failed
        log_lines.append(str(e))
        return

    # Update run from executor result
    run.outcome = result.outcome
    run.status = RemediationRunStatus.success if result.success else RemediationRunStatus.failed
    log_lines.extend(result.logs)
    if result.success and result.outcome != "Already compliant; no change needed":
        run.artifacts = run.artifacts or {}
        run.artifacts["direct_fix"] = {"outcome": result.outcome}


def execute_remediation_run_job(job: dict) -> None:
    """
    Process a remediation_run job: update run row, call PR bundle scaffold for pr_only,
    write outcome, logs, and artifacts. Idempotent: no-op if run is already success/failed.

    Args:
        job: Payload with run_id, tenant_id, action_id, mode (pr_only | direct_fix), created_at.
    """
    run_id_str = job.get("run_id")
    tenant_id_str = job.get("tenant_id")
    action_id_str = job.get("action_id")
    mode_str = job.get("mode")

    if not run_id_str or not tenant_id_str or not action_id_str or not mode_str:
        raise ValueError("job missing run_id, tenant_id, action_id, or mode")

    try:
        run_uuid = uuid.UUID(run_id_str)
        tenant_uuid = uuid.UUID(tenant_id_str)
        action_uuid = uuid.UUID(action_id_str)
    except (TypeError, ValueError) as e:
        raise ValueError(f"invalid run_id/tenant_id/action_id: {e}") from e

    if mode_str not in ("pr_only", "direct_fix"):
        raise ValueError(f"invalid mode: {mode_str}")

    final_status = "unknown"
    with session_scope() as session:
        result = session.execute(
            select(RemediationRun)
            .where(
                RemediationRun.id == run_uuid,
                RemediationRun.tenant_id == tenant_uuid,
            )
            .options(selectinload(RemediationRun.action))
        )
        run = result.scalar_one_or_none()
        if not run:
            raise ValueError(f"remediation run not found: run_id={run_id_str} tenant_id={tenant_id_str}")

        # Idempotency: do not overwrite completed runs
        if run.status == RemediationRunStatus.success or run.status == RemediationRunStatus.failed:
            logger.info(
                "remediation_run idempotent skip run_id=%s status=%s",
                run_id_str,
                run.status.value,
            )
            return

        if run.status != RemediationRunStatus.pending:
            logger.warning(
                "remediation_run run not pending run_id=%s status=%s; treating as retry, setting running",
                run_id_str,
                run.status.value,
            )

        # Audit: only update outcome/logs/artifacts when run is not completed (immutability)
        if not allow_update_outcome(run):
            logger.warning("remediation_run run already completed run_id=%s", run_id_str)
            return

        now = datetime.now(timezone.utc)
        run.status = RemediationRunStatus.running
        run.started_at = now
        session.flush()

        log_lines = [f"Run started at {now.isoformat()}."]

        if mode_str == "pr_only":
            try:
                action = run.action
                if not action:
                    run.outcome = "Action not found (may have been deleted)"
                    run.status = RemediationRunStatus.failed
                    log_lines.append(run.outcome)
                else:
                    pr_bundle = generate_pr_bundle(action, format="terraform")
                    run.artifacts = {"pr_bundle": pr_bundle}
                    run.outcome = "PR bundle generated"
                    run.status = RemediationRunStatus.success
                    log_lines.append(
                        f"PR bundle generated for action_type={action.action_type}."
                    )
            except Exception as e:
                logger.exception("PR bundle generation failed for run_id=%s: %s", run_id_str, e)
                run.outcome = f"PR bundle generation failed: {e}"
                run.status = RemediationRunStatus.failed
        else:
            # direct_fix (Step 8.3): load action, account, assume WriteRole, run executor
            _execute_direct_fix(session, run, log_lines)

        run.completed_at = datetime.now(timezone.utc)
        log_lines.append(f"Run completed at {run.completed_at.isoformat()}.")
        run.logs = "\n".join(log_lines)

        # Optional: one-line audit_log entry for compliance dashboards
        write_remediation_run_audit(session, run)

        final_status = run.status.value
        session.flush()

    # Operational visibility: structured log for CloudWatch/metrics
    logger.info(
        "RemediationRun completed run_id=%s action_id=%s status=%s",
        run_id_str,
        action_id_str,
        final_status,
    )
