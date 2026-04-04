"""Worker job handler for SaaS-managed PR bundle execution (plan/apply)."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from backend.config import settings
from backend.models.action import Action
from backend.models.action_group_membership import ActionGroupMembership
from backend.models.action_group_run import ActionGroupRun
from backend.models.action_group_run_result import ActionGroupRunResult
from backend.models.aws_account import AwsAccount
from backend.models.enums import (
    ActionGroupExecutionStatus,
    ActionGroupRunStatus,
    RemediationRunExecutionPhase,
    RemediationRunExecutionStatus,
    RemediationRunMode,
    RemediationRunStatus,
)
from backend.models.remediation_run import RemediationRun
from backend.models.remediation_run_execution import RemediationRunExecution
from backend.services.account_trust import account_assume_role_external_id, canonical_tenant_external_id
from backend.services.action_run_confirmation import (
    evaluate_confirmation_for_action,
    record_execution_result,
    schedule_confirmation_refresh,
)
from backend.services.root_credentials_workflow import (
    MANUAL_HIGH_RISK_MARKER,
    ROOT_CREDENTIALS_REQUIRED_MESSAGE,
    ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
    build_manual_high_risk_marker,
    is_root_credentials_required_action,
)
from backend.workers.database import session_scope
from backend.workers.services.aws import assume_role
from backend.workers.services.post_apply_reconcile import enqueue_post_apply_reconcile

logger = logging.getLogger("worker.jobs.remediation_run_execution")

RUN_TIMEOUT_SECONDS = 300
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_NON_EXECUTABLE_REASON_BY_TIER = {
    "review_required_bundle": "review_required_metadata_only",
    "manual_guidance_only": "manual_guidance_metadata_only",
}


@dataclass
class _BundleExecutionTarget:
    target_kind: str
    detected_by: str
    layout_version: str | None
    execution_root: str | None
    folders: list[str]
    folder_action_ids: dict[str, str]
    non_executable_actions: list[dict[str, object]]


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


def _load_bundle_manifest(workspace: Path) -> dict[str, Any] | None:
    manifest_path = workspace / "bundle_manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _workspace_subdir(workspace: Path, rel_path: str) -> Path:
    rel = Path(rel_path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe execution root: {rel_path}")
    return workspace / rel


def _dirs_under_root(workspace: Path, root: str, *, require_terraform: bool) -> list[str]:
    root_path = _workspace_subdir(workspace, root)
    if not root_path.exists() or not root_path.is_dir():
        return []
    dirs: list[str] = []
    for path in sorted(root_path.iterdir(), key=lambda item: item.name):
        if not path.is_dir():
            continue
        if require_terraform and not any(child.is_file() and child.suffix == ".tf" for child in path.iterdir()):
            continue
        dirs.append(str(path.relative_to(workspace)))
    return dirs


def _group_bundle_action_records(manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(manifest, dict):
        return []
    raw_records = manifest.get("actions")
    if not isinstance(raw_records, list):
        return []
    return [record for record in raw_records if isinstance(record, dict)]


def _non_executable_reason(*, support_tier: str, outcome: str | None = None) -> str:
    if isinstance(outcome, str) and outcome.strip():
        return outcome.strip()
    return _NON_EXECUTABLE_REASON_BY_TIER.get(support_tier, "non_executable_grouped_action")


def _manifest_non_executable_action(record: dict[str, Any]) -> dict[str, object]:
    support_tier = str(record.get("support_tier") or "").strip()
    outcome = str(record.get("outcome") or "").strip()
    return {
        "action_id": str(record.get("action_id") or ""),
        "folder": str(record.get("folder") or ""),
        "support_tier": support_tier,
        "profile_id": str(record.get("profile_id") or ""),
        "strategy_id": str(record.get("strategy_id") or ""),
        "reason": _non_executable_reason(support_tier=support_tier, outcome=outcome),
        "blocked_reasons": list(record.get("blocked_reasons") or []),
        "tier": str(record.get("tier") or ""),
        "outcome": outcome,
    }


def _manifest_target(workspace: Path, manifest: dict[str, Any]) -> _BundleExecutionTarget | None:
    layout_version = manifest.get("layout_version")
    execution_root = manifest.get("execution_root")
    if not isinstance(layout_version, str) or not layout_version.strip():
        return None
    if not isinstance(execution_root, str) or not execution_root.strip():
        return None
    folder_action_ids: dict[str, str] = {}
    non_executable_actions: list[dict[str, object]] = []
    for record in _group_bundle_action_records(manifest):
        folder = record.get("folder")
        action_id = record.get("action_id")
        if isinstance(folder, str) and folder and isinstance(action_id, str) and action_id:
            folder_action_ids[folder] = action_id
        if record.get("has_runnable_terraform") is True:
            continue
        non_executable_actions.append(_manifest_non_executable_action(record))
    return _BundleExecutionTarget(
        target_kind="mixed_tier_grouped",
        detected_by="bundle_manifest",
        layout_version=layout_version.strip(),
        execution_root=execution_root.strip(),
        folders=_dirs_under_root(workspace, execution_root.strip(), require_terraform=True),
        folder_action_ids=folder_action_ids,
        non_executable_actions=non_executable_actions,
    )


def _resolution_non_executable_actions(run: RemediationRun) -> list[dict[str, object]]:
    payload = _group_bundle_payload(run)
    if not isinstance(payload, dict):
        return []
    raw_entries = payload.get("action_resolutions")
    if not isinstance(raw_entries, list):
        return []
    actions: list[dict[str, object]] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        resolution = entry.get("resolution")
        if not isinstance(resolution, dict):
            continue
        support_tier = str(resolution.get("support_tier") or "").strip()
        if support_tier == "deterministic_bundle":
            continue
        reason = _non_executable_reason(support_tier=support_tier)
        actions.append(
            {
                "action_id": str(entry.get("action_id") or ""),
                "folder": "",
                "support_tier": support_tier,
                "profile_id": str(resolution.get("profile_id") or ""),
                "strategy_id": str(resolution.get("strategy_id") or ""),
                "reason": reason,
                "blocked_reasons": list(resolution.get("blocked_reasons") or []),
                "tier": "",
                "outcome": reason,
            }
        )
    return actions


def _legacy_group_folder_action_ids(run: RemediationRun, folders: list[str]) -> dict[str, str]:
    action_ids = [str(action_id) for action_id in _group_action_ids_from_payload(_group_bundle_payload(run))]
    return {
        folder: action_ids[index]
        for index, folder in enumerate(folders)
        if index < len(action_ids)
    }


def _single_run_folder_action_ids(run: RemediationRun) -> dict[str, str]:
    if run.action and isinstance(run.action.id, uuid.UUID):
        return {".": str(run.action.id)}
    return {}


def _resolve_execution_target(workspace: Path, run: RemediationRun) -> _BundleExecutionTarget:
    manifest = _load_bundle_manifest(workspace)
    if manifest_target := _manifest_target(workspace, manifest or {}):
        return manifest_target
    executable_root = "executable/actions"
    if _workspace_subdir(workspace, executable_root).is_dir():
        return _BundleExecutionTarget(
            target_kind="mixed_tier_grouped",
            detected_by="executable_actions_heuristic",
            layout_version=None,
            execution_root=executable_root,
            folders=_dirs_under_root(workspace, executable_root, require_terraform=True),
            folder_action_ids={},
            non_executable_actions=_resolution_non_executable_actions(run),
        )
    legacy_root = "actions"
    if _workspace_subdir(workspace, legacy_root).is_dir():
        folders = _dirs_under_root(workspace, legacy_root, require_terraform=False)
        return _BundleExecutionTarget(
            target_kind="legacy_grouped",
            detected_by="actions_heuristic",
            layout_version=None,
            execution_root=legacy_root,
            folders=folders,
            folder_action_ids=_legacy_group_folder_action_ids(run, folders),
            non_executable_actions=[],
        )
    return _BundleExecutionTarget(
        target_kind="single_run_root",
        detected_by="workspace_root",
        layout_version=None,
        execution_root=None,
        folders=["."],
        folder_action_ids=_single_run_folder_action_ids(run),
        non_executable_actions=[],
    )


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


def _prepare_terraform_env(base_env: dict[str, str], workspace: Path) -> dict[str, str]:
    """
    Prepare deterministic writable Terraform paths for Lambda runtime.

    Lambda container roots are read-only except `/tmp`, so force HOME/cache/data
    under the execution workspace to prevent init failures on state/cache writes.
    """
    env = dict(base_env)
    tf_home = workspace / ".terraform-home"
    tf_home.mkdir(parents=True, exist_ok=True)
    tf_data_dir = workspace / ".terraform-data"
    tf_data_dir.mkdir(parents=True, exist_ok=True)

    env["HOME"] = str(tf_home)
    env["TF_DATA_DIR"] = str(tf_data_dir)
    env["CHECKPOINT_DISABLE"] = "1"
    env["TF_IN_AUTOMATION"] = "1"
    return env


def _command_failure_detail(result: dict[str, object]) -> str:
    stderr = ANSI_ESCAPE_RE.sub("", str(result.get("stderr") or "")).strip()
    stdout = ANSI_ESCAPE_RE.sub("", str(result.get("stdout") or "")).strip()
    detail = stderr or stdout
    if not detail:
        return ""
    lines = [line.strip() for line in detail.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1][:300]


def _is_tolerable_sg_duplicate_apply_failure(
    *,
    action: Action | None,
    result: dict[str, object],
) -> bool:
    """
    Detect SG-restrict apply failures that are safe idempotent duplicates.

    When restricted SSH/RDP rules already exist (for example from prior manual apply),
    Terraform create can return InvalidPermission.Duplicate. Treat this as success for
    sg_restrict_public_ports to keep SaaS apply idempotent.
    """
    if action is None or action.action_type != "sg_restrict_public_ports":
        return False
    stderr = ANSI_ESCAPE_RE.sub("", str(result.get("stderr") or ""))
    if "InvalidPermission.Duplicate" not in stderr:
        return False
    blocked_markers = [
        "UnauthorizedOperation",
        "AccessDenied",
        "InvalidGroup.NotFound",
        "AuthFailure",
    ]
    return not any(marker in stderr for marker in blocked_markers)


def _execution_results_payload(
    folder_results: list[dict[str, object]],
    *,
    fail_fast: bool,
    target: _BundleExecutionTarget,
) -> dict[str, object]:
    failed_folders = [item for item in folder_results if item.get("status") == "failed"]
    action_results = [
        {
            "action_id": str(item.get("action_id") or ""),
            "folder": str(item.get("folder") or ""),
            "status": str(item.get("status") or "unknown"),
            "error": item.get("error"),
        }
        for item in folder_results
    ]
    non_executable_results = [dict(item) for item in target.non_executable_actions]
    return {
        "folders": folder_results,
        "folder_count": len(folder_results),
        "failed_folder_count": len(failed_folders),
        "executor": "terraform",
        "fail_fast": fail_fast,
        "target_kind": target.target_kind,
        "detected_by": target.detected_by,
        "layout_version": target.layout_version,
        "execution_root": target.execution_root,
        "executed_folders": [
            {
                "folder": str(item.get("folder") or ""),
                "action_id": str(item.get("action_id") or ""),
            }
            for item in folder_results
        ],
        "non_executable_actions": non_executable_results,
        "non_executable_results": non_executable_results,
        "non_executable_action_count": len(non_executable_results),
        "action_results": action_results,
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
    try:
        tenant_external_id_value = canonical_tenant_external_id(session, run.tenant_id)
    except Exception:
        tenant_external_id_value = None
    tenant_external_id = account_assume_role_external_id(
        account,
        tenant_external_id=tenant_external_id_value,
    ) or ""
    write_session = assume_role(
        role_arn=account.role_write_arn,
        external_id=tenant_external_id,
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


def _change_value_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_change_value_text(item) for item in value]
        cleaned = [item for item in parts if item]
        return ", ".join(cleaned)
    if isinstance(value, dict):
        try:
            return json.dumps(value, sort_keys=True)
        except Exception:
            return str(value).strip()
    return str(value).strip()


def _change_entries_for_run(run: RemediationRun) -> list[dict[str, str]]:
    artifacts = run.artifacts if isinstance(run.artifacts, dict) else {}
    raw_inputs = artifacts.get("strategy_inputs")
    changes: list[dict[str, str]] = []
    if isinstance(raw_inputs, dict):
        for key, value in raw_inputs.items():
            value_text = _change_value_text(value)
            if not value_text:
                continue
            changes.append(
                {
                    "field": key.replace("_", " ").strip(),
                    "before": "unspecified",
                    "after": value_text,
                }
            )
    if changes:
        return changes[:6]
    field_name = run.action.control_id if run.action and run.action.control_id else "remediation"
    outcome = str(run.outcome or "Applied remediation").strip() or "Applied remediation"
    return [{"field": field_name, "before": "failing", "after": outcome}]


def _resolve_applied_by(run: RemediationRun) -> str:
    approved_by = getattr(run, "approved_by", None)
    email = getattr(approved_by, "email", None)
    if isinstance(email, str) and email.strip():
        return email.strip()
    approved_by_user_id = getattr(run, "approved_by_user_id", None)
    if isinstance(approved_by_user_id, uuid.UUID):
        return str(approved_by_user_id)
    return "system"


def _write_change_summary_artifact(run: RemediationRun, *, applied_at: datetime | None = None) -> None:
    artifacts: dict[str, object] = {}
    if isinstance(run.artifacts, dict):
        artifacts.update(run.artifacts)
    applied_at_iso = (applied_at or datetime.now(timezone.utc)).isoformat()
    artifacts["change_summary"] = {
        "applied_at": applied_at_iso,
        "applied_by": _resolve_applied_by(run),
        "changes": _change_entries_for_run(run),
        "run_id": str(run.id),
    }
    run.artifacts = artifacts


def _mark_manual_high_risk(run: RemediationRun) -> None:
    """Persist root-credential manual/high-risk marker on run artifacts."""
    artifacts: dict[str, object] = {}
    if isinstance(run.artifacts, dict):
        artifacts.update(run.artifacts)
    approved_by_user_id = run.approved_by_user_id if isinstance(run.approved_by_user_id, uuid.UUID) else None
    artifacts["manual_high_risk"] = build_manual_high_risk_marker(
        approved_by_user_id=approved_by_user_id,
        strategy_id=str(artifacts.get("selected_strategy") or ""),
        action_type=run.action.action_type if run.action else None,
    )
    run.artifacts = artifacts


def _group_bundle_payload(run: RemediationRun) -> dict | None:
    if not isinstance(run.artifacts, dict):
        return None
    raw_group = run.artifacts.get("group_bundle")
    if not isinstance(raw_group, dict):
        return None
    return raw_group


def _group_action_ids_from_payload(payload: dict | None) -> list[uuid.UUID]:
    if not isinstance(payload, dict):
        return []
    raw_ids = payload.get("resolved_action_ids")
    if not isinstance(raw_ids, list):
        raw_ids = payload.get("action_ids")
    if not isinstance(raw_ids, list):
        return []
    parsed: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for raw_id in raw_ids:
        if not isinstance(raw_id, str):
            continue
        try:
            action_id = uuid.UUID(raw_id)
        except ValueError:
            continue
        if action_id in seen:
            continue
        seen.add(action_id)
        parsed.append(action_id)
    return parsed


def _resolve_group_run_for_execution(
    session: Session,
    run: RemediationRun,
    phase: RemediationRunExecutionPhase,
    started_at: datetime | None,
) -> tuple[ActionGroupRun | None, list[uuid.UUID]]:
    payload = _group_bundle_payload(run)
    action_ids = _group_action_ids_from_payload(payload)
    if not action_ids:
        return None, []

    declared_group_run_id: uuid.UUID | None = None
    if isinstance(payload, dict):
        raw_group_run_id = payload.get("group_run_id")
        if isinstance(raw_group_run_id, str):
            try:
                declared_group_run_id = uuid.UUID(raw_group_run_id)
            except ValueError:
                declared_group_run_id = None

    memberships = (
        session.query(ActionGroupMembership)
        .filter(
            ActionGroupMembership.tenant_id == run.tenant_id,
            ActionGroupMembership.action_id.in_(action_ids),
        )
        .all()
    )
    if not memberships:
        return None, action_ids

    group_ids = {membership.group_id for membership in memberships}
    if len(group_ids) != 1:
        return None, action_ids
    group_id = next(iter(group_ids))

    group_run: ActionGroupRun | None = None
    if declared_group_run_id is not None:
        group_run = (
            session.query(ActionGroupRun)
            .filter(
                ActionGroupRun.id == declared_group_run_id,
                ActionGroupRun.tenant_id == run.tenant_id,
            )
            .one_or_none()
        )
    if group_run is None:
        group_run = (
            session.query(ActionGroupRun)
            .filter(
                ActionGroupRun.tenant_id == run.tenant_id,
                ActionGroupRun.group_id == group_id,
                ActionGroupRun.remediation_run_id == run.id,
            )
            .one_or_none()
        )

    if group_run is None:
        mode_value = "saas_plan" if phase == RemediationRunExecutionPhase.plan else "saas_plan_apply"
        group_run = ActionGroupRun(
            id=declared_group_run_id or uuid.uuid4(),
            tenant_id=run.tenant_id,
            group_id=group_id,
            remediation_run_id=run.id,
            initiated_by_user_id=run.approved_by_user_id,
            mode=mode_value,
            status=ActionGroupRunStatus.started,
            started_at=started_at,
            reporting_source="saas_executor",
        )
        session.add(group_run)
        session.flush()

    if group_run.started_at is None and started_at is not None:
        group_run.started_at = started_at
    group_run.reporting_source = "saas_executor"
    return group_run, action_ids


def _to_group_execution_status(status: str | None) -> ActionGroupExecutionStatus:
    value = (status or "").strip().lower()
    if value == "success":
        return ActionGroupExecutionStatus.success
    if value == "failed":
        return ActionGroupExecutionStatus.failed
    if value == "cancelled":
        return ActionGroupExecutionStatus.cancelled
    return ActionGroupExecutionStatus.unknown


def _group_result_map(raw_items: object) -> dict[str, dict[str, object]]:
    if not isinstance(raw_items, list):
        return {}
    result: dict[str, dict[str, object]] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        action_id = str(item.get("action_id") or "").strip()
        if action_id:
            result[action_id] = item
    return result


def _sync_group_run_results(
    session: Session,
    *,
    run: RemediationRun,
    execution: RemediationRunExecution,
    folder_results: list[dict[str, object]] | None,
) -> None:
    group_run, action_ids = _resolve_group_run_for_execution(
        session,
        run,
        phase=execution.phase,
        started_at=execution.started_at,
    )
    if group_run is None or not action_ids:
        return

    execution_results = execution.results if isinstance(execution.results, dict) else {}
    action_result_map = _group_result_map(execution_results.get("action_results"))
    non_executable_result_map = _group_result_map(execution_results.get("non_executable_results"))
    if not non_executable_result_map:
        non_executable_result_map = _group_result_map(execution_results.get("non_executable_actions"))

    ordered_results = folder_results or []
    has_failed = False
    has_cancelled = False
    for index, action_id in enumerate(action_ids):
        action_key = str(action_id)
        action_result = action_result_map.get(action_key)
        non_executable_result = non_executable_result_map.get(action_key)
        folder_result = ordered_results[index] if index < len(ordered_results) else None
        if isinstance(action_result, dict):
            exec_status = _to_group_execution_status(
                str(action_result.get("status") or action_result.get("execution_status") or "unknown")
            )
            raw_result = action_result
        elif isinstance(non_executable_result, dict):
            exec_status = _to_group_execution_status(
                str(non_executable_result.get("status") or non_executable_result.get("execution_status") or "unknown")
            )
            raw_result = non_executable_result
        elif folder_result is None:
            exec_status = ActionGroupExecutionStatus.unknown
            raw_result = {"error": "missing_folder_result"}
        else:
            exec_status = _to_group_execution_status(str(folder_result.get("status") or "unknown"))
            raw_result = folder_result

        if exec_status == ActionGroupExecutionStatus.failed:
            has_failed = True
        if exec_status == ActionGroupExecutionStatus.cancelled:
            has_cancelled = True

        row = (
            session.query(ActionGroupRunResult)
            .filter(
                ActionGroupRunResult.tenant_id == run.tenant_id,
                ActionGroupRunResult.group_run_id == group_run.id,
                ActionGroupRunResult.action_id == action_id,
            )
            .one_or_none()
        )
        if row is None:
            row = ActionGroupRunResult(
                tenant_id=run.tenant_id,
                group_run_id=group_run.id,
                action_id=action_id,
            )
            session.add(row)

        row.execution_status = exec_status
        row.execution_started_at = execution.started_at
        row.execution_finished_at = execution.completed_at
        row.raw_result = raw_result if isinstance(raw_result, dict) else None
        if exec_status == ActionGroupExecutionStatus.failed:
            row.execution_error_code = "saas_executor_failed"
            row.execution_error_message = str(
                (raw_result or {}).get("error") if isinstance(raw_result, dict) else "execution_failed"
            )[:1000]
        else:
            row.execution_error_code = None
            row.execution_error_message = None

        record_execution_result(
            session,
            action_id=action_id,
            latest_run_id=group_run.id,
            execution_status=exec_status,
            attempted_at=execution.started_at,
            finished_at=execution.completed_at,
        )
        evaluate_confirmation_for_action(
            session,
            action_id=action_id,
            since_run_started=execution.started_at,
        )
        if execution.phase == RemediationRunExecutionPhase.apply and exec_status == ActionGroupExecutionStatus.success:
            schedule_confirmation_refresh(
                session,
                action_id=action_id,
                finished_at=execution.completed_at,
            )

    if execution.phase == RemediationRunExecutionPhase.plan:
        if execution.status == RemediationRunExecutionStatus.failed:
            group_run.status = ActionGroupRunStatus.failed
            group_run.finished_at = execution.completed_at
        else:
            group_run.status = ActionGroupRunStatus.started
    else:
        if has_failed:
            group_run.status = ActionGroupRunStatus.failed
        elif has_cancelled:
            group_run.status = ActionGroupRunStatus.cancelled
        else:
            group_run.status = ActionGroupRunStatus.finished
        group_run.finished_at = execution.completed_at


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
        if is_root_credentials_required_action(run.action.action_type if run.action else None):
            now = datetime.now(timezone.utc)
            execution.status = RemediationRunExecutionStatus.failed
            execution.error_summary = "root_credentials_required"
            execution.completed_at = now
            run.status = RemediationRunStatus.failed
            run.outcome = (
                "Root credentials required. This remediation cannot run in SaaS executor mode. "
                f"Follow runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}."
            )
            _mark_manual_high_risk(run)
            _append_run_log(
                run,
                f"{MANUAL_HIGH_RISK_MARKER}: {ROOT_CREDENTIALS_REQUIRED_MESSAGE} "
                f"Runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}.",
            )
            session.flush()
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
        folder_results: list[dict[str, object]] = []
        try:
            account_id, _ = _ensure_group_invariants(session, run)
            base_env = _assume_write_role(session, run, account_id)
            fail_fast = _resolve_fail_fast(execution)
            with tempfile.TemporaryDirectory(prefix="bundle-exec-") as tmp_dir:
                workspace = Path(tmp_dir)
                env = _prepare_terraform_env(base_env, workspace)
                for item in files:
                    _safe_write(workspace, item["path"], item["content"])

                target = _resolve_execution_target(workspace, run)
                manifest = execution.workspace_manifest if isinstance(execution.workspace_manifest, dict) else {}
                expected_hash = manifest.get("bundle_hash")
                if (
                    phase == RemediationRunExecutionPhase.apply
                    and isinstance(expected_hash, str)
                    and expected_hash != digest
                ):
                    raise RuntimeError("bundle hash mismatch; re-run plan before apply")
                if target.target_kind == "mixed_tier_grouped" and not target.folders:
                    execution.results = _execution_results_payload(
                        folder_results=[],
                        fail_fast=fail_fast,
                        target=target,
                    )
                    execution.workspace_manifest = {
                        "bundle_hash": digest,
                        "folders": [],
                        "executor": "terraform",
                        "fail_fast": fail_fast,
                        "target_kind": target.target_kind,
                        "detected_by": target.detected_by,
                        "layout_version": target.layout_version,
                        "execution_root": target.execution_root,
                        "executed_folders": [],
                        "non_executable_actions": target.non_executable_actions,
                        "non_executable_action_count": len(target.non_executable_actions),
                    }
                    execution.logs_ref = json.dumps(execution.results)
                    raise RuntimeError("mixed-tier bundle has no executable folders")

                for rel_folder in target.folders:
                    folder = workspace if rel_folder == "." else workspace / rel_folder
                    item_results: list[dict[str, object]] = []
                    folder_error: str | None = None
                    action_id = target.folder_action_ids.get(rel_folder)

                    init_result = _run_cmd(["terraform", "init", "-input=false"], folder, env)
                    item_results.append(init_result)
                    if int(init_result["returncode"]) != 0:
                        detail = _command_failure_detail(init_result)
                        folder_error = f"terraform init failed for {rel_folder}"
                        if detail:
                            folder_error = f"{folder_error}: {detail}"

                    if folder_error is None:
                        plan_result = _run_cmd(["terraform", "plan", "-input=false", "-out=tfplan"], folder, env)
                        item_results.append(plan_result)
                        if int(plan_result["returncode"]) != 0:
                            detail = _command_failure_detail(plan_result)
                            folder_error = f"terraform plan failed for {rel_folder}"
                            if detail:
                                folder_error = f"{folder_error}: {detail}"

                    if folder_error is None and phase == RemediationRunExecutionPhase.plan:
                        show_result = _run_cmd(["terraform", "show", "-no-color", "tfplan"], folder, env)
                        item_results.append(show_result)
                        if int(show_result["returncode"]) != 0:
                            detail = _command_failure_detail(show_result)
                            folder_error = f"terraform show failed for {rel_folder}"
                            if detail:
                                folder_error = f"{folder_error}: {detail}"
                    elif folder_error is None:
                        apply_result = _run_cmd(["terraform", "apply", "-auto-approve", "tfplan"], folder, env)
                        item_results.append(apply_result)
                        if int(apply_result["returncode"]) != 0:
                            if _is_tolerable_sg_duplicate_apply_failure(
                                action=run.action,
                                result=apply_result,
                            ):
                                logger.info(
                                    "treating duplicate SG ingress apply as success "
                                    "run_id=%s execution_id=%s folder=%s",
                                    run.id,
                                    execution.id,
                                    rel_folder,
                                )
                            else:
                                detail = _command_failure_detail(apply_result)
                                folder_error = f"terraform apply failed for {rel_folder}"
                                if detail:
                                    folder_error = f"{folder_error}: {detail}"

                    if folder_error is not None:
                        folder_results.append(
                            {
                                "folder": rel_folder,
                                "action_id": action_id,
                                "commands": item_results,
                                "status": "failed",
                                "error": folder_error,
                            }
                        )
                        if fail_fast:
                            execution.results = _execution_results_payload(
                                folder_results,
                                fail_fast=fail_fast,
                                target=target,
                            )
                            execution.logs_ref = json.dumps(execution.results)
                            raise RuntimeError(folder_error)
                        continue

                    folder_results.append(
                        {
                            "folder": rel_folder,
                            "action_id": action_id,
                            "commands": item_results,
                            "status": "success",
                        }
                    )

                failed_folders = [item for item in folder_results if item.get("status") == "failed"]
                any_failed = bool(failed_folders)

                execution.results = _execution_results_payload(
                    folder_results,
                    fail_fast=fail_fast,
                    target=target,
                )
                execution.workspace_manifest = {
                    "bundle_hash": digest,
                    "folders": list(target.folders),
                    "executor": "terraform",
                    "fail_fast": fail_fast,
                    "target_kind": target.target_kind,
                    "detected_by": target.detected_by,
                    "layout_version": target.layout_version,
                    "execution_root": target.execution_root,
                    "executed_folders": [
                        {
                            "folder": str(item.get("folder") or ""),
                            "action_id": str(item.get("action_id") or ""),
                        }
                        for item in folder_results
                    ],
                    "non_executable_actions": target.non_executable_actions,
                    "non_executable_action_count": len(target.non_executable_actions),
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
                        _write_change_summary_artifact(run, applied_at=execution.completed_at)
                        try:
                            enqueue_post_apply_reconcile(session, run)
                        except Exception as exc:  # pragma: no cover - defensive, helper is best-effort
                            logger.exception(
                                "post-apply reconcile enqueue failed run_id=%s execution_id=%s: %s",
                                run.id,
                                execution.id,
                                exc,
                            )
                _sync_group_run_results(
                    session,
                    run=run,
                    execution=execution,
                    folder_results=folder_results,
                )
        except FileNotFoundError as exc:
            execution.status = RemediationRunExecutionStatus.failed
            execution.error_summary = "runtime_missing_dependency"
            execution.completed_at = datetime.now(timezone.utc)
            run.status = RemediationRunStatus.failed
            run.outcome = f"SaaS execution failed: {exc}"
            _append_run_log(run, f"SaaS execution failed: {exc}")
            _sync_group_run_results(session, run=run, execution=execution, folder_results=folder_results)
        except Exception as exc:
            logger.exception("bundle execution failed execution_id=%s: %s", execution.id, exc)
            execution.status = RemediationRunExecutionStatus.failed
            execution.error_summary = str(exc)[:500]
            execution.completed_at = datetime.now(timezone.utc)
            run.status = RemediationRunStatus.failed
            run.outcome = f"SaaS execution failed: {exc}"
            _append_run_log(run, f"SaaS execution failed: {exc}")
            _sync_group_run_results(session, run=run, execution=execution, folder_results=folder_results)

        session.flush()
