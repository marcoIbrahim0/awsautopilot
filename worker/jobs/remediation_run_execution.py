"""Worker job handler for SaaS-managed PR bundle execution (plan/apply)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from backend.config import settings
from backend.models.action import Action
from backend.models.aws_account import AwsAccount
from backend.models.enums import (
    RemediationRunExecutionPhase,
    RemediationRunExecutionStatus,
    RemediationRunMode,
    RemediationRunStatus,
)
from backend.models.remediation_run import RemediationRun
from backend.models.remediation_run_execution import RemediationRunExecution
from worker.database import session_scope
from worker.services.aws import assume_role

logger = logging.getLogger("worker.jobs.remediation_run_execution")

RUN_TIMEOUT_SECONDS = 300


def _resolve_fail_fast(execution: RemediationRunExecution) -> bool:
    manifest = execution.workspace_manifest if isinstance(execution.workspace_manifest, dict) else {}
    configured = manifest.get("fail_fast")
    if isinstance(configured, bool):
        return configured
    return settings.SAAS_BUNDLE_EXECUTOR_FAIL_FAST


def _bundle_files(run: RemediationRun) -> list[dict[str, str]]:
    if not isinstance(run.artifacts, dict):
        return []
    pr_bundle = run.artifacts.get("pr_bundle")
    if not isinstance(pr_bundle, dict):
        return []
    raw_files = pr_bundle.get("files")
    if not isinstance(raw_files, list):
        return []
    result: list[dict[str, str]] = []
    for item in raw_files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        content = item.get("content")
        if content is None:
            content = ""
        elif not isinstance(content, str):
            content = str(content)
        result.append({"path": path, "content": content})
    return result


def _bundle_hash(files: list[dict[str, str]]) -> str:
    h = hashlib.sha256()
    for item in sorted(files, key=lambda f: f["path"]):
        h.update(item["path"].encode("utf-8"))
        h.update(b"\x00")
        h.update(item["content"].encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _safe_write(base_dir: Path, rel_path: str, content: str) -> None:
    rel = Path(rel_path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe bundle path: {rel_path}")
    full = base_dir / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _execution_folders(workspace: Path) -> list[Path]:
    actions_dir = workspace / "actions"
    if actions_dir.exists() and actions_dir.is_dir():
        dirs = sorted([p for p in actions_dir.iterdir() if p.is_dir()], key=lambda p: p.name)
        if dirs:
            return dirs
    return [workspace]


def _run_cmd(
    args: list[str],
    cwd: Path,
    env: dict[str, str],
) -> dict[str, object]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_SECONDS,
        check=False,
    )
    return {
        "command": " ".join(args),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _ensure_group_invariants(session: Session, run: RemediationRun) -> tuple[str, str | None]:
    account_id = run.action.account_id if run.action else None
    region = run.action.region if run.action else None
    if not isinstance(run.artifacts, dict):
        if not account_id:
            raise ValueError("Action/account context missing for execution.")
        return account_id, region
    group_bundle = run.artifacts.get("group_bundle")
    if not isinstance(group_bundle, dict):
        if not account_id:
            raise ValueError("Action/account context missing for execution.")
        return account_id, region
    raw_ids = group_bundle.get("action_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise ValueError("Group bundle has no action_ids.")
    action_ids: list[uuid.UUID] = []
    for raw_id in raw_ids:
        if not isinstance(raw_id, str):
            continue
        try:
            action_ids.append(uuid.UUID(raw_id))
        except ValueError:
            continue
    if not action_ids:
        raise ValueError("Group bundle action_ids are invalid.")
    result = session.execute(
        select(Action).where(Action.tenant_id == run.tenant_id, Action.id.in_(action_ids))
    )
    actions = result.scalars().all()
    if not actions:
        raise ValueError("Group bundle actions not found.")
    account_ids = {action.account_id for action in actions}
    regions = {action.region for action in actions}
    if len(account_ids) != 1 or len(regions) != 1:
        raise ValueError("Group bundle execution requires same account_id and region for all actions.")
    resolved_account = next(iter(account_ids))
    resolved_region = next(iter(regions))
    return resolved_account, resolved_region


def _assume_write_role(
    session: Session,
    run: RemediationRun,
    account_id: str,
) -> dict[str, str]:
    account_result = session.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == run.tenant_id,
            AwsAccount.account_id == account_id,
        )
    )
    account = account_result.scalar_one_or_none()
    if not account or not account.role_write_arn:
        raise ValueError("WriteRole not configured for this AWS account.")
    write_session = assume_role(
        role_arn=account.role_write_arn,
        external_id=account.external_id,
    )
    credentials = write_session.get_credentials()
    if credentials is None:
        raise ValueError("Failed to obtain temporary AWS credentials.")
    frozen = credentials.get_frozen_credentials()
    env = os.environ.copy()
    env["AWS_ACCESS_KEY_ID"] = frozen.access_key
    env["AWS_SECRET_ACCESS_KEY"] = frozen.secret_key
    env["AWS_SESSION_TOKEN"] = frozen.token
    return env


def _append_run_log(run: RemediationRun, message: str) -> None:
    existing = (run.logs or "").strip()
    if existing:
        run.logs = f"{existing}\n{message}"
    else:
        run.logs = message


def execute_pr_bundle_execution_job(job: dict) -> None:
    """Process execute_pr_bundle_plan/apply jobs."""
    run_id_raw = job.get("run_id")
    tenant_id_raw = job.get("tenant_id")
    execution_id_raw = job.get("execution_id")
    phase_raw = job.get("phase")

    try:
        run_id = uuid.UUID(str(run_id_raw))
        tenant_id = uuid.UUID(str(tenant_id_raw))
        execution_id = uuid.UUID(str(execution_id_raw))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid execution payload ids: {exc}") from exc

    if phase_raw not in {"plan", "apply"}:
        raise ValueError(f"invalid phase: {phase_raw}")
    phase = RemediationRunExecutionPhase(phase_raw)

    with session_scope() as session:
        result = session.execute(
            select(RemediationRunExecution)
            .where(
                RemediationRunExecution.id == execution_id,
                RemediationRunExecution.tenant_id == tenant_id,
                RemediationRunExecution.run_id == run_id,
            )
            .options(selectinload(RemediationRunExecution.run).selectinload(RemediationRun.action))
        )
        execution = result.scalar_one_or_none()
        if execution is None:
            raise ValueError(f"execution not found: {execution_id}")
        run = execution.run
        if run is None:
            raise ValueError("execution missing remediation run")
        if run.mode != RemediationRunMode.pr_only:
            raise ValueError("bundle execution is only supported for pr_only runs")
        if execution.status in {
            RemediationRunExecutionStatus.success,
            RemediationRunExecutionStatus.failed,
            RemediationRunExecutionStatus.cancelled,
        }:
            logger.info("bundle execution idempotent skip execution_id=%s", execution.id)
            return
        if execution.status == RemediationRunExecutionStatus.running:
            logger.info("bundle execution already running; skip duplicate delivery execution_id=%s", execution.id)
            return
        if execution.status != RemediationRunExecutionStatus.queued:
            logger.info(
                "bundle execution in non-queue state '%s'; skip duplicate delivery execution_id=%s",
                execution.status,
                execution.id,
            )
            return

        now = datetime.now(timezone.utc)
        claim_result = session.execute(
            update(RemediationRunExecution)
            .where(
                RemediationRunExecution.id == execution.id,
                RemediationRunExecution.status == RemediationRunExecutionStatus.queued,
            )
            .values(
                status=RemediationRunExecutionStatus.running,
                started_at=now,
            )
        )
        if int(claim_result.rowcount or 0) == 0:
            logger.info("bundle execution claim lost; another worker claimed execution_id=%s", execution.id)
            return
        execution.status = RemediationRunExecutionStatus.running
        execution.started_at = now
        run.status = RemediationRunStatus.running
        _append_run_log(run, f"SaaS {phase.value} execution started at {now.isoformat()}.")
        session.flush()

        files = _bundle_files(run)
        if not files:
            execution.status = RemediationRunExecutionStatus.failed
            execution.error_summary = "bundle_missing"
            execution.completed_at = datetime.now(timezone.utc)
            run.status = RemediationRunStatus.failed
            run.outcome = "SaaS bundle execution failed: bundle_missing"
            _append_run_log(run, "SaaS execution failed: bundle_missing.")
            session.flush()
            return

        digest = _bundle_hash(files)
        try:
            account_id, _ = _ensure_group_invariants(session, run)
            env = _assume_write_role(session, run, account_id)
            fail_fast = _resolve_fail_fast(execution)
            with tempfile.TemporaryDirectory(prefix="bundle-exec-") as tmp_dir:
                workspace = Path(tmp_dir)
                for item in files:
                    _safe_write(workspace, item["path"], item["content"])

                folders = _execution_folders(workspace)
                folder_results: list[dict[str, object]] = []
                manifest = execution.workspace_manifest if isinstance(execution.workspace_manifest, dict) else {}
                expected_hash = manifest.get("bundle_hash")
                if (
                    phase == RemediationRunExecutionPhase.apply
                    and isinstance(expected_hash, str)
                    and expected_hash != digest
                ):
                    raise RuntimeError("bundle hash mismatch; re-run plan before apply")
                for folder in folders:
                    rel_folder = str(folder.relative_to(workspace)) if folder != workspace else "."
                    item_results: list[dict[str, object]] = []
                    folder_error: str | None = None

                    init_result = _run_cmd(["terraform", "init", "-input=false"], folder, env)
                    item_results.append(init_result)
                    if int(init_result["returncode"]) != 0:
                        folder_error = f"terraform init failed for {rel_folder}"

                    if folder_error is None:
                        plan_result = _run_cmd(["terraform", "plan", "-input=false", "-out=tfplan"], folder, env)
                        item_results.append(plan_result)
                        if int(plan_result["returncode"]) != 0:
                            folder_error = f"terraform plan failed for {rel_folder}"

                    if folder_error is None and phase == RemediationRunExecutionPhase.plan:
                        show_result = _run_cmd(["terraform", "show", "-no-color", "tfplan"], folder, env)
                        item_results.append(show_result)
                        if int(show_result["returncode"]) != 0:
                            folder_error = f"terraform show failed for {rel_folder}"
                    elif folder_error is None:
                        apply_result = _run_cmd(["terraform", "apply", "-auto-approve", "tfplan"], folder, env)
                        item_results.append(apply_result)
                        if int(apply_result["returncode"]) != 0:
                            folder_error = f"terraform apply failed for {rel_folder}"

                    if folder_error is not None:
                        folder_results.append(
                            {
                                "folder": rel_folder,
                                "commands": item_results,
                                "status": "failed",
                                "error": folder_error,
                            }
                        )
                        if fail_fast:
                            raise RuntimeError(folder_error)
                        continue

                    folder_results.append({"folder": rel_folder, "commands": item_results, "status": "success"})

                failed_folders = [item for item in folder_results if item.get("status") == "failed"]
                any_failed = bool(failed_folders)

                execution.results = {
                    "folders": folder_results,
                    "folder_count": len(folder_results),
                    "failed_folder_count": len(failed_folders),
                    "executor": "terraform",
                    "fail_fast": fail_fast,
                }
                execution.workspace_manifest = {
                    "bundle_hash": digest,
                    "folders": [str(folder.relative_to(workspace)) if folder != workspace else "." for folder in folders],
                    "executor": "terraform",
                    "fail_fast": fail_fast,
                }
                execution.logs_ref = json.dumps(execution.results)
                execution.completed_at = datetime.now(timezone.utc)

                if phase == RemediationRunExecutionPhase.plan:
                    if any_failed:
                        execution.status = RemediationRunExecutionStatus.failed
                        execution.error_summary = "one or more folders failed during plan"
                        run.status = RemediationRunStatus.failed
                        run.outcome = "SaaS plan failed."
                        _append_run_log(run, "SaaS plan failed.")
                    else:
                        execution.status = RemediationRunExecutionStatus.awaiting_approval
                        execution.error_summary = None
                        run.status = RemediationRunStatus.awaiting_approval
                        run.outcome = "Plan complete. Awaiting approval for apply."
                        _append_run_log(run, "SaaS plan complete. Awaiting approval for apply.")
                else:
                    if any_failed:
                        execution.status = RemediationRunExecutionStatus.failed
                        execution.error_summary = "one or more folders failed during apply"
                        run.status = RemediationRunStatus.failed
                        run.outcome = "SaaS apply failed."
                        _append_run_log(run, "SaaS apply failed.")
                    else:
                        execution.status = RemediationRunExecutionStatus.success
                        execution.error_summary = None
                        run.status = RemediationRunStatus.success
                        run.outcome = "SaaS apply completed successfully."
                        _append_run_log(run, "SaaS apply completed successfully.")
        except FileNotFoundError as exc:
            execution.status = RemediationRunExecutionStatus.failed
            execution.error_summary = "runtime_missing_dependency"
            execution.completed_at = datetime.now(timezone.utc)
            run.status = RemediationRunStatus.failed
            run.outcome = f"SaaS execution failed: {exc}"
            _append_run_log(run, f"SaaS execution failed: {exc}")
        except Exception as exc:
            logger.exception("bundle execution failed execution_id=%s: %s", execution.id, exc)
            execution.status = RemediationRunExecutionStatus.failed
            execution.error_summary = str(exc)[:500]
            execution.completed_at = datetime.now(timezone.utc)
            run.status = RemediationRunStatus.failed
            run.outcome = f"SaaS execution failed: {exc}"
            _append_run_log(run, f"SaaS execution failed: {exc}")

        session.flush()
