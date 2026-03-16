"""
Remediation run job handler (Step 7.3 + 8.3).

Picks up remediation_run jobs from SQS, updates run status (pending → running → success/failed),
calls PR bundle generator for pr_only, or direct fix executor for direct_fix. Idempotent: skips
if run already success or failed.
"""
from __future__ import annotations

import copy
import logging
import json
import shlex
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.config import settings
from backend.models.action import Action
from backend.models.action_group_run import ActionGroupRun
from backend.models.aws_account import AwsAccount
from backend.models.enums import ActionGroupRunStatus, RemediationRunMode, RemediationRunStatus
from backend.models.remediation_run import RemediationRun
from backend.services.compliance_pack_spec import build_control_mapping_rows
from backend.services.pr_automation import build_pr_automation_artifacts
from backend.services.remediation_metrics import emit_worker_dispatch_error
from backend.services.pr_bundle import PRBundleGenerationError, generate_pr_bundle
from backend.services.direct_fix_approval import DirectFixApprovalDecision, evaluate_direct_fix_approval
from backend.services.remediation_audit import (
    allow_update_outcome,
    write_blocked_mutation_audit,
    write_remediation_run_audit,
)
from backend.services.remediation_profile_resolver import (
    build_compat_resolution_decision,
    normalize_resolution_decision,
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
from backend.workers.services.direct_fix import run_direct_fix

logger = logging.getLogger("worker.jobs.remediation_run")

# ---------------------------------------------------------------------------
# Contract: job dict must have job_type, run_id, tenant_id, action_id, mode, created_at
# ---------------------------------------------------------------------------

REMEDIATION_RUN_REQUIRED_FIELDS = {"job_type", "run_id", "tenant_id", "action_id", "mode", "created_at"}
_RUNNER_TEMPLATE_CACHE: dict[str, object] = {}


def _download_bundle_group_run_uses_callback(row: ActionGroupRun, run: RemediationRun) -> bool:
    if str(row.report_token_jti or "").strip():
        return True
    artifacts = run.artifacts if isinstance(run.artifacts, Mapping) else None
    if not isinstance(artifacts, Mapping):
        return False
    group_bundle = artifacts.get("group_bundle")
    if not isinstance(group_bundle, Mapping):
        return False
    reporting = group_bundle.get("reporting")
    if not isinstance(reporting, Mapping):
        return False
    callback_url = reporting.get("callback_url")
    token = reporting.get("token")
    return any(isinstance(value, str) and value.strip() for value in (callback_url, token))


def _mark_download_bundle_group_run_started(row: ActionGroupRun, *, started_at: datetime) -> None:
    if row.status == ActionGroupRunStatus.queued:
        row.status = ActionGroupRunStatus.started
    if row.started_at is None:
        row.started_at = started_at


def _download_bundle_group_run_terminal_status(run: RemediationRun) -> ActionGroupRunStatus | None:
    if run.status == RemediationRunStatus.success:
        return ActionGroupRunStatus.finished
    if run.status == RemediationRunStatus.failed:
        return ActionGroupRunStatus.failed
    if run.status == RemediationRunStatus.cancelled:
        return ActionGroupRunStatus.cancelled
    return None


def _sync_download_bundle_group_runs(session: Session, run: RemediationRun) -> None:
    """
    Keep action_group_runs in sync for download_bundle workflows.

    Group runs are created before remediation_run enqueue; if worker processes the run
    successfully, we should reflect lifecycle state on the associated group run row.
    """
    rows = (
        session.execute(
            select(ActionGroupRun).where(
                ActionGroupRun.tenant_id == run.tenant_id,
                ActionGroupRun.remediation_run_id == run.id,
                ActionGroupRun.mode == "download_bundle",
            )
        )
    ).scalars().all()
    if not rows:
        return

    now = datetime.now(timezone.utc)
    started_at = run.started_at or now
    finished_at = run.completed_at or now
    for row in rows:
        if run.status == RemediationRunStatus.running:
            _mark_download_bundle_group_run_started(row, started_at=started_at)
            continue

        terminal_status = _download_bundle_group_run_terminal_status(run)
        if terminal_status is None:
            continue
        if terminal_status == ActionGroupRunStatus.finished and _download_bundle_group_run_uses_callback(row, run):
            _mark_download_bundle_group_run_started(row, started_at=started_at)
            row.finished_at = None
            continue
        _mark_download_bundle_group_run_started(row, started_at=started_at)
        row.status = terminal_status
        row.finished_at = finished_at


def _parse_s3_uri(uri: str) -> tuple[str, str] | None:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        return None
    key = parsed.path.lstrip("/")
    if not key:
        return None
    return parsed.netloc, key


def _resolve_group_runner_template(default_script: str) -> tuple[str, str, str]:
    configured_uri = (settings.SAAS_BUNDLE_RUNNER_TEMPLATE_S3_URI or "").strip()
    configured_version = (settings.SAAS_BUNDLE_RUNNER_TEMPLATE_VERSION or "").strip() or "v1"
    cache_ttl = max(1, int(settings.SAAS_BUNDLE_RUNNER_TEMPLATE_CACHE_SECONDS or 300))

    if not configured_uri:
        return default_script, "embedded", configured_version

    parsed = _parse_s3_uri(configured_uri)
    if not parsed:
        logger.warning(
            "Invalid SAAS_BUNDLE_RUNNER_TEMPLATE_S3_URI '%s'; using embedded run_all.sh template.",
            configured_uri,
        )
        return default_script, "embedded_invalid_s3_uri", configured_version

    cached_uri = _RUNNER_TEMPLATE_CACHE.get("uri")
    cached_at = _RUNNER_TEMPLATE_CACHE.get("fetched_at")
    cached_content = _RUNNER_TEMPLATE_CACHE.get("content")
    cached_source = _RUNNER_TEMPLATE_CACHE.get("source")
    cached_version = _RUNNER_TEMPLATE_CACHE.get("version")
    if (
        isinstance(cached_uri, str)
        and cached_uri == configured_uri
        and isinstance(cached_at, (int, float))
        and (time.time() - float(cached_at)) < cache_ttl
        and isinstance(cached_content, str)
        and isinstance(cached_source, str)
        and isinstance(cached_version, str)
    ):
        return cached_content, cached_source, cached_version

    bucket, key = parsed
    try:
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=bucket, Key=key)
        body = obj.get("Body")
        if body is None:
            raise ValueError("S3 object body was empty.")
        content = body.read().decode("utf-8")
        source = f"s3://{bucket}/{key}"
        _RUNNER_TEMPLATE_CACHE["uri"] = configured_uri
        _RUNNER_TEMPLATE_CACHE["fetched_at"] = time.time()
        _RUNNER_TEMPLATE_CACHE["content"] = content
        _RUNNER_TEMPLATE_CACHE["source"] = source
        _RUNNER_TEMPLATE_CACHE["version"] = configured_version
        return content, source, configured_version
    except Exception as exc:
        logger.warning(
            "Failed to fetch centralized run_all.sh template from %s (%s). Using embedded fallback.",
            configured_uri,
            exc,
        )
        return default_script, "embedded_s3_fallback", configured_version


def _load_default_runner_script(fallback_script: str) -> str:
    """Load default run_all.sh from repo template file, fallback to embedded script."""
    try:
        template_path = Path(__file__).resolve().parents[2] / "infrastructure" / "templates" / "run_all.sh"
        if template_path.is_file():
            content = template_path.read_text(encoding="utf-8")
            if content.strip():
                return content
    except Exception as exc:
        logger.warning("Failed to load infrastructure/templates/run_all.sh; using embedded fallback (%s).", exc)
    return fallback_script


def _parse_group_action_ids(raw_ids: object) -> list[uuid.UUID]:
    """Parse group action IDs from payload/artifacts; keep input order and drop invalid values."""
    if not isinstance(raw_ids, list):
        return []
    parsed: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for raw_id in raw_ids:
        if not isinstance(raw_id, str):
            continue
        raw_id = raw_id.strip()
        if not raw_id:
            continue
        try:
            action_uuid = uuid.UUID(raw_id)
        except ValueError:
            continue
        if action_uuid in seen:
            continue
        seen.add(action_uuid)
        parsed.append(action_uuid)
    return parsed


@dataclass(frozen=True)
class _GroupedActionDecision:
    action_id: uuid.UUID
    strategy_id: str | None
    profile_id: str | None
    strategy_inputs: dict[str, Any]
    support_tier: str
    resolution: dict[str, Any] | None


def _grouped_resolution_field(raw_value: object, field_name: str) -> object:
    if isinstance(raw_value, Mapping):
        return raw_value.get(field_name)
    return getattr(raw_value, field_name, None)


def _grouped_resolution_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _grouped_resolution_error(
    code: str,
    detail: str,
    *,
    action_type: str | None,
) -> PRBundleGenerationError:
    return PRBundleGenerationError(
        {
            "code": code,
            "detail": detail,
            "action_type": action_type or "",
            "format": "terraform",
            "strategy_id": "",
            "variant": "",
        }
    )


def _raise_invalid_grouped_action_resolutions(detail: str, *, action_type: str | None) -> None:
    raise _grouped_resolution_error(
        "invalid_grouped_action_resolutions",
        detail,
        action_type=action_type,
    )


def _grouped_resolution_source(job: dict, run: RemediationRun) -> tuple[str, object | None]:
    if "action_resolutions" in job:
        return "queue_payload", job.get("action_resolutions")
    artifacts = run.artifacts if isinstance(run.artifacts, dict) else {}
    group_bundle = artifacts.get("group_bundle")
    if isinstance(group_bundle, dict) and "action_resolutions" in group_bundle:
        return "artifacts", group_bundle.get("action_resolutions")
    return "legacy", None


def _grouped_action_decisions(
    *,
    job: dict,
    run: RemediationRun,
    group_action_ids: Sequence[uuid.UUID],
    resolved_action_ids: Sequence[uuid.UUID],
    strategy_id: str | None,
    strategy_inputs: dict[str, Any] | None,
    risk_acknowledged: bool,
    action_type: str | None,
) -> tuple[str, list[_GroupedActionDecision]]:
    source_name, raw_entries = _grouped_resolution_source(job, run)
    if source_name == "legacy":
        decisions = _legacy_grouped_action_decisions(
            action_ids=resolved_action_ids,
            strategy_id=strategy_id,
            strategy_inputs=strategy_inputs,
            risk_acknowledged=risk_acknowledged,
            action_type=action_type,
        )
        return source_name, decisions
    decisions = _canonical_grouped_action_decisions(
        raw_entries=raw_entries,
        group_action_ids=group_action_ids,
        resolved_action_ids=resolved_action_ids,
        action_type=action_type,
    )
    return source_name, decisions


def _legacy_grouped_action_decisions(
    *,
    action_ids: Sequence[uuid.UUID],
    strategy_id: str | None,
    strategy_inputs: dict[str, Any] | None,
    risk_acknowledged: bool,
    action_type: str | None,
) -> list[_GroupedActionDecision]:
    copied_inputs = copy.deepcopy(strategy_inputs or {})
    support_tier = "review_required_bundle" if risk_acknowledged else "deterministic_bundle"
    profile_id: str | None = None
    resolution: dict[str, Any] | None = None
    if strategy_id:
        resolution = build_compat_resolution_decision(
            strategy_id=strategy_id,
            profile_id=strategy_id,
            support_tier=support_tier,
            resolved_inputs=copied_inputs,
        )
        profile_id = resolution["profile_id"]
    return [
        _GroupedActionDecision(
            action_id=action_id,
            strategy_id=strategy_id,
            profile_id=profile_id,
            strategy_inputs=copy.deepcopy(copied_inputs),
            support_tier=support_tier,
            resolution=copy.deepcopy(resolution),
        )
        for action_id in action_ids
    ]


def _canonical_grouped_action_decisions(
    *,
    raw_entries: object | None,
    group_action_ids: Sequence[uuid.UUID],
    resolved_action_ids: Sequence[uuid.UUID],
    action_type: str | None,
) -> list[_GroupedActionDecision]:
    if not isinstance(raw_entries, (list, tuple)):
        _raise_invalid_grouped_action_resolutions(
            "Grouped action_resolutions must be an array.",
            action_type=action_type,
        )
    allowed_action_ids = {str(action_id) for action_id in group_action_ids}
    decisions = _grouped_action_decision_map(raw_entries, allowed_action_ids, action_type=action_type)
    missing_ids = [str(action_id) for action_id in resolved_action_ids if str(action_id) not in decisions]
    if missing_ids:
        _raise_invalid_grouped_action_resolutions(
            "Grouped action_resolutions are missing entries for resolved actions: "
            + ", ".join(missing_ids),
            action_type=action_type,
        )
    return [decisions[str(action_id)] for action_id in resolved_action_ids]


def _grouped_action_decision_map(
    raw_entries: Sequence[object],
    allowed_action_ids: set[str],
    *,
    action_type: str | None,
) -> dict[str, _GroupedActionDecision]:
    decisions: dict[str, _GroupedActionDecision] = {}
    for raw_entry in raw_entries:
        decision = _canonical_grouped_action_decision(
            raw_entry,
            allowed_action_ids=allowed_action_ids,
            action_type=action_type,
        )
        action_key = str(decision.action_id)
        if action_key in decisions:
            _raise_invalid_grouped_action_resolutions(
                f"Duplicate grouped action_resolutions entry for action_id '{action_key}'.",
                action_type=action_type,
            )
        decisions[action_key] = decision
    return decisions


def _canonical_grouped_action_decision(
    raw_entry: object,
    *,
    allowed_action_ids: set[str],
    action_type: str | None,
) -> _GroupedActionDecision:
    action_id = _grouped_resolution_uuid(raw_entry, action_type=action_type)
    action_key = str(action_id)
    if action_key not in allowed_action_ids:
        _raise_invalid_grouped_action_resolutions(
            f"Grouped action_resolutions entry references action_id '{action_key}' outside group_action_ids.",
            action_type=action_type,
        )
    resolution = _canonical_grouped_resolution(raw_entry, action_id=action_key, action_type=action_type)
    strategy_id = _grouped_resolution_text(_grouped_resolution_field(raw_entry, "strategy_id")) or resolution["strategy_id"]
    profile_id = _grouped_resolution_text(_grouped_resolution_field(raw_entry, "profile_id")) or resolution["profile_id"]
    if strategy_id != resolution["strategy_id"] or profile_id != resolution["profile_id"]:
        _raise_invalid_grouped_action_resolutions(
            f"Grouped action_resolutions entry for action_id '{action_key}' conflicts with nested resolution.",
            action_type=action_type,
        )
    strategy_inputs = _grouped_resolution_inputs(raw_entry, action_id=action_key, action_type=action_type)
    return _GroupedActionDecision(
        action_id=action_id,
        strategy_id=strategy_id,
        profile_id=profile_id,
        strategy_inputs=strategy_inputs,
        support_tier=resolution["support_tier"],
        resolution=resolution,
    )


def _grouped_resolution_uuid(raw_entry: object, *, action_type: str | None) -> uuid.UUID:
    action_id = _grouped_resolution_text(_grouped_resolution_field(raw_entry, "action_id"))
    if action_id is None:
        _raise_invalid_grouped_action_resolutions(
            "Each grouped action_resolutions entry must include action_id.",
            action_type=action_type,
        )
    try:
        return uuid.UUID(action_id)
    except ValueError:
        _raise_invalid_grouped_action_resolutions(
            f"Grouped action_resolutions entry has invalid action_id '{action_id}'.",
            action_type=action_type,
        )


def _canonical_grouped_resolution(
    raw_entry: object,
    *,
    action_id: str,
    action_type: str | None,
) -> dict[str, Any]:
    raw_resolution = _grouped_resolution_field(raw_entry, "resolution")
    if not isinstance(raw_resolution, Mapping):
        _raise_invalid_grouped_action_resolutions(
            f"Grouped action_resolutions entry for action_id '{action_id}' is missing a valid resolution object.",
            action_type=action_type,
        )
    try:
        return normalize_resolution_decision(raw_resolution)
    except ValueError as exc:
        _raise_invalid_grouped_action_resolutions(
            f"Grouped action_resolutions entry for action_id '{action_id}' is invalid: {exc}",
            action_type=action_type,
        )


def _grouped_resolution_inputs(
    raw_entry: object,
    *,
    action_id: str,
    action_type: str | None,
) -> dict[str, Any]:
    raw_inputs = _grouped_resolution_field(raw_entry, "strategy_inputs")
    if raw_inputs is None:
        return {}
    if not isinstance(raw_inputs, Mapping):
        _raise_invalid_grouped_action_resolutions(
            f"Grouped action_resolutions entry for action_id '{action_id}' has invalid strategy_inputs.",
            action_type=action_type,
        )
    return copy.deepcopy(dict(raw_inputs))


def _shared_group_strategy_id(action_decisions: Sequence[_GroupedActionDecision]) -> str | None:
    strategy_ids = {decision.strategy_id for decision in action_decisions}
    if len(strategy_ids) != 1:
        return None
    return next(iter(strategy_ids))


def _selected_repo_target(job: dict, run: RemediationRun) -> dict[str, Any] | None:
    raw_target = job.get("repo_target")
    if isinstance(raw_target, dict):
        return raw_target
    artifacts = run.artifacts if isinstance(run.artifacts, dict) else {}
    stored_target = artifacts.get("repo_target")
    return stored_target if isinstance(stored_target, dict) else None


def _apply_pr_automation(
    *,
    session: Session,
    run: RemediationRun,
    bundle: dict[str, Any],
    actions: list[Action],
    repo_target: dict[str, Any] | None,
    strategy_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    control_rows = build_control_mapping_rows(session)
    enriched_bundle, artifacts = build_pr_automation_artifacts(
        run_id=str(run.id),
        actions=actions,
        bundle=bundle,
        repo_target=repo_target,
        strategy_id=strategy_id,
        control_mapping_rows=control_rows,
    )
    return enriched_bundle, artifacts


def _safe_group_folder_name(action: Action, index: int, *, root: str = "actions") -> str:
    """Build a stable, filesystem-safe folder path for one action in a group bundle."""
    base = (action.resource_id or action.target_id or action.action_type or "action").lower()
    normalized = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in base)
    normalized = "-".join(part for part in normalized.split("-") if part)
    if not normalized:
        normalized = "action"
    return f"{root}/{index + 1:02d}-{normalized[:48]}-{str(action.id)[:8]}"


GROUP_BUNDLE_MIXED_TIER_LAYOUT_VERSION = "grouped_bundle_mixed_tier/v1"
GROUP_BUNDLE_MIXED_TIER_EXECUTION_ROOT = "executable/actions"
_GROUP_BUNDLE_TIER_ROOTS = {
    "deterministic_bundle": GROUP_BUNDLE_MIXED_TIER_EXECUTION_ROOT,
    "review_required_bundle": "review_required/actions",
    "manual_guidance_only": "manual_guidance/actions",
}
_GROUP_BUNDLE_TIER_LABELS = {
    "deterministic_bundle": "executable",
    "review_required_bundle": "review_required",
    "manual_guidance_only": "manual_guidance",
}


def _grouped_bundle_layout_error(
    detail: str,
    *,
    action_type: str | None,
) -> PRBundleGenerationError:
    return PRBundleGenerationError(
        {
            "code": "invalid_grouped_bundle_layout",
            "detail": detail,
            "action_type": action_type or "",
            "format": "terraform",
            "strategy_id": "",
            "variant": "",
        }
    )


def _raise_invalid_grouped_bundle_layout(detail: str, *, action_type: str | None) -> None:
    raise _grouped_bundle_layout_error(detail, action_type=action_type)


def _mixed_tier_runner_script() -> tuple[str, str, str]:
    script = f"""#!/usr/bin/env bash
set -euo pipefail

EXECUTION_ROOT="{GROUP_BUNDLE_MIXED_TIER_EXECUTION_ROOT}"

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is required but not installed."
  exit 1
fi

CACHE_ROOT="${{HOME}}/.aws-security-autopilot/terraform"
mkdir -p "${{CACHE_ROOT}}/plugin-cache"
export TF_PLUGIN_CACHE_DIR="${{CACHE_ROOT}}/plugin-cache"
export TF_REGISTRY_CLIENT_TIMEOUT="${{TF_REGISTRY_CLIENT_TIMEOUT:-30}}"
export TF_REGISTRY_DISCOVERY_RETRY="${{TF_REGISTRY_DISCOVERY_RETRY:-3}}"

TFRC_PATH="${{CACHE_ROOT}}/terraformrc"
if [ ! -f "${{TFRC_PATH}}" ]; then
  cat > "${{TFRC_PATH}}" <<EOF
plugin_cache_dir = "${{TF_PLUGIN_CACHE_DIR}}"
EOF
fi
export TF_CLI_CONFIG_FILE="${{TFRC_PATH}}"

bootstrap_provider_cache() {{
  local marker bootstrap_dir
  marker="${{CACHE_ROOT}}/.aws-provider-6.31.0.ready"

  if [ -f "${{marker}}" ] && find "${{TF_PLUGIN_CACHE_DIR}}" -type f -path '*registry.terraform.io/hashicorp/aws/6.31.0/*' -print -quit 2>/dev/null | grep -q .; then
    return 0
  fi

  bootstrap_dir=$(mktemp -d)
  cat > "${{bootstrap_dir}}/versions.tf" <<'EOF'
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "= 6.31.0"
    }}
  }}
}}
EOF

  (
    cd "${{bootstrap_dir}}"
    terraform init -backend=false -input=false >/dev/null
  )
  rm -rf "${{bootstrap_dir}}"
  touch "${{marker}}"
}}

collect_action_dirs() {{
  local dir
  while IFS= read -r dir; do
    if find "$dir" -maxdepth 1 -name '*.tf' -print -quit 2>/dev/null | grep -q .; then
      ACTION_DIRS+=("$dir")
    fi
  done < <(find "${{EXECUTION_ROOT}}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)
}}

is_known_duplicate_only() {{
  local log_file="$1"
  local duplicate_pattern
  duplicate_pattern='InvalidPermission\\.Duplicate|already exists|AlreadyExists|EntityAlreadyExists'

  if ! grep -Eiq "$duplicate_pattern" "$log_file"; then
    return 1
  fi
  if grep -Eiq 'AccessDenied|UnauthorizedOperation|InvalidGroupId|DependencyViolation|Throttl|ExpiredToken|not found|NoSuch' "$log_file"; then
    return 1
  fi
  return 0
}}

apply_with_duplicate_tolerance() {{
  local dir="$1"
  local log_file rc resource existing_id duplicate_line

  log_file=$(mktemp)
  set +e
  (
    cd "$dir"
    terraform apply -auto-approve
  ) >"$log_file" 2>&1
  rc=$?
  set -e
  cat "$log_file"

  if [ "$rc" -eq 0 ]; then
    rm -f "$log_file"
    return 0
  fi

  if is_known_duplicate_only "$log_file"; then
    resource=$(sed -n 's/.*with \\([^,]*\\),/\\1/p' "$log_file" | head -n 1)
    existing_id=$(grep -Eo 'sg-[0-9A-Za-z-]+' "$log_file" | head -n 1)
    duplicate_line=$(grep -Ei 'InvalidPermission\\.Duplicate|already exists|AlreadyExists|EntityAlreadyExists' "$log_file" | head -n 1)
    echo "WARNING: duplicate/already-existing resource detected; continuing without failure."
    echo "  action: $dir"
    if [ -n "$resource" ]; then
      echo "  resource: $resource"
    fi
    if [ -n "$existing_id" ]; then
      echo "  existing identifier: $existing_id"
    fi
    if [ -n "$duplicate_line" ]; then
      echo "  detail: $duplicate_line"
    fi
    rm -f "$log_file"
    return 0
  fi

  rm -f "$log_file"
  return "$rc"
}}

run_terraform_init_with_retry() {{
  local dir="$1"
  local attempts=5
  local attempt=1
  local sleep_seconds=3
  local rc=0

  while [ "$attempt" -le "$attempts" ]; do
    set +e
    (
      cd "$dir"
      terraform init -input=false
    )
    rc=$?
    set -e
    if [ "$rc" -eq 0 ]; then
      return 0
    fi
    if [ "$attempt" -lt "$attempts" ]; then
      echo "WARNING: terraform init failed for $dir (attempt $attempt/$attempts). Retrying in ${{sleep_seconds}}s..."
      sleep "$sleep_seconds"
      sleep_seconds=$((sleep_seconds * 2))
      if [ "$sleep_seconds" -gt 30 ]; then
        sleep_seconds=30
      fi
    fi
    attempt=$((attempt + 1))
  done

  return "$rc"
}}

has_unresolved_placeholders() {{
  local dir="$1"
  local placeholders
  placeholders=$(grep -R -n --include='*.tf' -E 'REPLACE_[A-Z0-9_]+' "$dir" 2>/dev/null || true)
  if [ -n "$placeholders" ]; then
    echo "ERROR: unresolved placeholder token(s) found in Terraform files for $dir:"
    echo "$placeholders"
    return 0
  fi
  return 1
}}

bootstrap_provider_cache

ACTION_DIRS=()
collect_action_dirs
TOTAL="${{#ACTION_DIRS[@]}}"
if [ "${{TOTAL:-0}}" -eq 0 ]; then
  echo "No executable Terraform action folders found under ${{EXECUTION_ROOT}}/."
  exit 0
fi

SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_ACTIONS=()

for dir in "${{ACTION_DIRS[@]}}"; do
  echo ""
  echo "=== Running terraform in $dir ==="

  if has_unresolved_placeholders "$dir"; then
    echo "ERROR: unresolved placeholders detected for $dir. Skipping this action folder."
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("$dir (precheck)")
    continue
  fi

  if ! run_terraform_init_with_retry "$dir"; then
    echo "ERROR: terraform init failed for $dir after retries. Skipping this action folder."
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("$dir (init)")
    continue
  fi

  set +e
  (
    cd "$dir"
    terraform plan -input=false
  )
  plan_rc=$?
  set -e
  if [ "$plan_rc" -ne 0 ]; then
    echo "ERROR: terraform plan failed for $dir. Skipping apply for this action folder."
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("$dir (plan)")
    continue
  fi

  if ! apply_with_duplicate_tolerance "$dir"; then
    echo "ERROR: terraform apply failed for $dir. Continuing with remaining action folders."
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("$dir (apply)")
    continue
  fi

  SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
done

echo "Bundle run completed."
echo "  Successful action folders: ${{SUCCESS_COUNT}}/${{TOTAL}}"
echo "  Failed action folders: ${{FAILED_COUNT}}/${{TOTAL}}"
if [ "$FAILED_COUNT" -gt 0 ]; then
  echo "Failed folders summary:"
  for failed in "${{FAILED_ACTIONS[@]}}"; do
    echo "  - $failed"
  done
  exit 1
fi
echo "All action folders completed successfully."
"""
    return script, "embedded_mixed_tier", GROUP_BUNDLE_MIXED_TIER_LAYOUT_VERSION


def _grouped_decision_payload(
    decision: _GroupedActionDecision,
    *,
    action_id: str,
    action_type: str | None,
) -> dict[str, Any]:
    if isinstance(decision.resolution, dict):
        return copy.deepcopy(decision.resolution)
    _raise_invalid_grouped_action_resolutions(
        f"Grouped action_resolutions entry for action_id '{action_id}' is missing normalized resolution data.",
        action_type=action_type,
    )


def _selected_resolution_payload(job: dict[str, Any], run: RemediationRun) -> dict[str, Any] | None:
    raw_resolution = job.get("resolution")
    if isinstance(raw_resolution, Mapping):
        try:
            return normalize_resolution_decision(raw_resolution)
        except ValueError:
            return None
    artifacts = run.artifacts if isinstance(run.artifacts, Mapping) else None
    if not isinstance(artifacts, Mapping):
        return None
    stored_resolution = artifacts.get("resolution")
    if not isinstance(stored_resolution, Mapping):
        return None
    try:
        return normalize_resolution_decision(stored_resolution)
    except ValueError:
        return None


def _grouped_tier_root(support_tier: str, *, action_type: str | None) -> str:
    tier_root = _GROUP_BUNDLE_TIER_ROOTS.get(support_tier)
    if isinstance(tier_root, str):
        return tier_root
    _raise_invalid_grouped_action_resolutions(
        f"Unsupported grouped support_tier '{support_tier}'.",
        action_type=action_type,
    )


def _grouped_tier_label(support_tier: str) -> str:
    return _GROUP_BUNDLE_TIER_LABELS.get(support_tier, "unknown")


def _grouped_action_outcome(support_tier: str, *, has_runnable_terraform: bool) -> str:
    if support_tier == "deterministic_bundle":
        return "executable_bundle_generated" if has_runnable_terraform else "executable_generation_failed"
    if support_tier == "review_required_bundle":
        return "review_required_metadata_only"
    return "manual_guidance_metadata_only"


def _grouped_decision_summary(
    resolution: Mapping[str, Any],
    *,
    support_tier: str,
    outcome: str,
) -> str:
    rationale = str(resolution.get("decision_rationale") or "").strip()
    if rationale:
        return rationale
    if outcome == "executable_generation_failed":
        return "Executable remediation failed to render; metadata was preserved without runnable Terraform."
    if support_tier == "deterministic_bundle":
        return "Executable Terraform was generated for this action."
    if support_tier == "review_required_bundle":
        return "Review is required before any implementation; this folder is metadata only."
    return "Manual guidance only; this folder does not contain runnable Terraform."


def _prefixed_group_bundle_files(
    bundle: Mapping[str, Any],
    *,
    folder: str,
) -> tuple[list[dict[str, str]], bool]:
    files: list[dict[str, str]] = []
    has_terraform = False
    for file_item in bundle.get("files", []):
        if not isinstance(file_item, dict):
            continue
        path = str(file_item.get("path") or "file")
        content = file_item.get("content")
        if content is None:
            content = ""
        elif not isinstance(content, str):
            content = str(content)
        if path.endswith(".tf"):
            has_terraform = True
        files.append({"path": f"{folder}/{path}", "content": content})
    return files, has_terraform


def _bundle_rollback_entry_for_action(
    bundle: Mapping[str, Any],
    *,
    action_id: str,
    folder: str | None = None,
) -> dict[str, str] | None:
    metadata = bundle.get("metadata")
    raw_entries = metadata.get("bundle_rollback_entries") if isinstance(metadata, Mapping) else None
    raw_entry = raw_entries.get(action_id) if isinstance(raw_entries, Mapping) else None
    if not isinstance(raw_entry, Mapping):
        return None
    path = str(raw_entry.get("path") or "").strip().lstrip("./")
    runner = str(raw_entry.get("runner") or "").strip()
    if not path or not runner:
        return None
    prefixed_path = f"{folder}/{path}" if folder else path
    return {"path": prefixed_path, "runner": runner}


def _bundle_rollback_command(entry: Mapping[str, Any] | None) -> str:
    if not isinstance(entry, Mapping):
        return ""
    path = str(entry.get("path") or "").strip()
    runner = str(entry.get("runner") or "").strip()
    if not path or not runner:
        return ""
    return f"{runner} ./{path}"


def _grouped_action_record(
    action: Action,
    decision: _GroupedActionDecision,
    *,
    index: int,
    folder: str,
    tier_root: str,
    outcome: str,
    has_runnable_terraform: bool,
    bundle_rollback_entry: Mapping[str, Any] | None = None,
    generation_error: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    action_id = str(action.id)
    resolution = _grouped_decision_payload(decision, action_id=action_id, action_type=action.action_type)
    record = {
        "index": index + 1,
        "action_id": action_id,
        "action_type": str(action.action_type or ""),
        "title": str(action.title or ""),
        "control_id": str(action.control_id or ""),
        "target_id": str(action.target_id or ""),
        "strategy_id": str(resolution.get("strategy_id") or ""),
        "profile_id": str(resolution.get("profile_id") or ""),
        "support_tier": decision.support_tier,
        "tier": _grouped_tier_label(decision.support_tier),
        "tier_root": tier_root,
        "folder": folder,
        "outcome": outcome,
        "has_runnable_terraform": has_runnable_terraform,
        "decision_version": str(resolution.get("decision_version") or ""),
        "decision_rationale": str(resolution.get("decision_rationale") or ""),
        "decision_summary": _grouped_decision_summary(
            resolution,
            support_tier=decision.support_tier,
            outcome=outcome,
        ),
        "strategy_inputs": copy.deepcopy(decision.strategy_inputs),
        "missing_inputs": copy.deepcopy(list(resolution.get("missing_inputs") or [])),
        "missing_defaults": copy.deepcopy(list(resolution.get("missing_defaults") or [])),
        "blocked_reasons": copy.deepcopy(list(resolution.get("blocked_reasons") or [])),
        "rejected_profiles": copy.deepcopy(list(resolution.get("rejected_profiles") or [])),
        "finding_coverage": copy.deepcopy(dict(resolution.get("finding_coverage") or {})),
        "preservation_summary": copy.deepcopy(dict(resolution.get("preservation_summary") or {})),
    }
    rollback_command = _bundle_rollback_command(bundle_rollback_entry)
    if rollback_command:
        record["bundle_rollback_command"] = rollback_command
        record["bundle_rollback_path"] = str(bundle_rollback_entry.get("path") or "")
        record["bundle_rollback_runner"] = str(bundle_rollback_entry.get("runner") or "")
    if generation_error is not None:
        record["generation_error"] = copy.deepcopy(dict(generation_error))
    return record


def _grouped_action_readme(record: Mapping[str, Any]) -> str:
    lines = [
        "AWS Security Autopilot — Group action artifact",
        "",
        f"Action: {record.get('title') or 'Untitled action'}",
        f"Action ID: {record.get('action_id') or ''}",
        f"Tier: {record.get('tier') or ''}",
        f"Tier root: {record.get('tier_root') or ''}",
        f"Outcome: {record.get('outcome') or ''}",
        f"Strategy: {record.get('strategy_id') or ''}",
        f"Profile: {record.get('profile_id') or ''}",
        "",
        f"Decision summary: {record.get('decision_summary') or ''}",
    ]
    if record.get("has_runnable_terraform"):
        lines.append("Runnable Terraform is present in this folder.")
    else:
        lines.append("This folder is metadata only and does not contain runnable Terraform.")
    return "\n".join(lines) + "\n"


def _grouped_action_decision_file(record: Mapping[str, Any]) -> str:
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def _append_grouped_action_metadata_files(files: list[dict[str, str]], record: Mapping[str, Any]) -> None:
    folder = str(record.get("folder") or "")
    files.append({"path": f"{folder}/README_ACTION.txt", "content": _grouped_action_readme(record)})
    files.append({"path": f"{folder}/decision.json", "content": _grouped_action_decision_file(record)})
    generation_error = record.get("generation_error")
    if isinstance(generation_error, Mapping):
        files.append(
            {
                "path": f"{folder}/generation_error.json",
                "content": json.dumps(dict(generation_error), indent=2, sort_keys=True) + "\n",
            }
        )


def _grouped_tier_counts(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "executable": sum(1 for record in records if record.get("tier") == "executable"),
        "review_required": sum(1 for record in records if record.get("tier") == "review_required"),
        "manual_guidance": sum(1 for record in records if record.get("tier") == "manual_guidance"),
    }


def _grouped_bundle_manifest(
    records: Sequence[Mapping[str, Any]],
    *,
    runner_template_source: str,
    runner_template_version: str,
) -> dict[str, Any]:
    return {
        "layout_version": GROUP_BUNDLE_MIXED_TIER_LAYOUT_VERSION,
        "execution_root": GROUP_BUNDLE_MIXED_TIER_EXECUTION_ROOT,
        "action_count": len(records),
        "grouped_actions": [record["action_id"] for record in records],
        "actions": [copy.deepcopy(dict(record)) for record in records],
        "tier_counts": _grouped_tier_counts(records),
        "runnable_action_count": sum(
            1 for record in records if bool(record.get("has_runnable_terraform"))
        ),
        "runner_template_source": runner_template_source,
        "runner_template_version": runner_template_version,
    }


def _grouped_decision_log(records: Sequence[Mapping[str, Any]]) -> str:
    lines = ["# Decision Log", ""]
    for record in records:
        lines.extend(
            [
                f"## {record.get('index')}. {record.get('title') or 'Untitled action'}",
                f"- Action ID: {record.get('action_id') or ''}",
                f"- Tier: {record.get('tier_root') or ''}",
                f"- Outcome: {record.get('outcome') or ''}",
                f"- Strategy/Profile: {record.get('strategy_id') or ''} / {record.get('profile_id') or ''}",
                f"- Summary: {record.get('decision_summary') or ''}",
                "",
            ]
        )
    return "\n".join(lines)


def _grouped_finding_coverage(records: Sequence[Mapping[str, Any]]) -> str:
    payload = {
        "layout_version": GROUP_BUNDLE_MIXED_TIER_LAYOUT_VERSION,
        "actions": [
            {
                "action_id": record["action_id"],
                "support_tier": record["support_tier"],
                "finding_coverage": copy.deepcopy(dict(record.get("finding_coverage") or {})),
            }
            for record in records
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _grouped_tier_section(records: Sequence[Mapping[str, Any]], *, tier: str) -> list[str]:
    lines: list[str] = []
    for record in records:
        if record.get("tier") != tier:
            continue
        lines.append(
            f"- {record.get('index')}. {record.get('title') or 'Untitled action'} "
            f"({record.get('outcome') or ''}) -> {record.get('folder') or ''}"
        )
    if lines:
        return lines
    return ["- none"]


def _grouped_bundle_readme(records: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "AWS Security Autopilot — Mixed-tier Group PR bundle",
        "",
        f"Layout version: {GROUP_BUNDLE_MIXED_TIER_LAYOUT_VERSION}",
        f"Execution root: {GROUP_BUNDLE_MIXED_TIER_EXECUTION_ROOT}",
        "",
        "Only executable Terraform lives under executable/actions/.",
        "review_required/actions/ and manual_guidance/actions/ contain metadata-only guidance.",
        "run_all.sh executes only executable/actions/ and no-ops successfully when no runnable Terraform folders exist.",
        "",
        "Run from bundle root:",
        "  chmod +x ./run_all.sh",
        "  ./run_all.sh",
        "",
        "Executable actions:",
        *_grouped_tier_section(records, tier="executable"),
        "",
        "Review-required actions:",
        *_grouped_tier_section(records, tier="review_required"),
        "",
        "Manual-guidance actions:",
        *_grouped_tier_section(records, tier="manual_guidance"),
    ]
    return "\n".join(lines) + "\n"


def _validate_grouped_bundle_records(
    records: Sequence[Mapping[str, Any]],
    *,
    action_type: str | None,
) -> None:
    if not records:
        _raise_invalid_grouped_bundle_layout(
            "Grouped bundle generation produced zero represented actions.",
            action_type=action_type,
        )
    folders = [str(record.get("folder") or "") for record in records]
    if any(not folder for folder in folders):
        _raise_invalid_grouped_bundle_layout(
            "Grouped bundle generation produced an empty action folder path.",
            action_type=action_type,
        )
    if len(set(folders)) != len(folders):
        _raise_invalid_grouped_bundle_layout(
            "Grouped bundle generation produced duplicate action folder paths.",
            action_type=action_type,
        )


def _reporting_non_executable_result(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "action_id": str(record.get("action_id") or ""),
        "support_tier": str(record.get("support_tier") or ""),
        "profile_id": str(record.get("profile_id") or ""),
        "strategy_id": str(record.get("strategy_id") or ""),
        "reason": str(record.get("outcome") or "non_executable_grouped_action"),
        "blocked_reasons": copy.deepcopy(list(record.get("blocked_reasons") or [])),
    }


def _build_reporting_wrapper_script(
    *,
    callback_url: str,
    report_token: str,
    action_ids: list[uuid.UUID],
    non_executable_results: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    success_results = [
        {
            "action_id": str(action_id),
            "execution_status": "success",
        }
        for action_id in action_ids
    ]
    failed_results = [
        {
            "action_id": str(action_id),
            "execution_status": "failed",
            "execution_error_code": "bundle_runner_failed",
            "execution_error_message": "run_actions.sh exited non-zero",
        }
        for action_id in action_ids
    ]
    reporting_non_executable_results = [
        dict(item)
        for item in (non_executable_results or [])
        if isinstance(item, Mapping)
    ]
    started_template = {
        "token": report_token,
        "event": "started",
        "reporting_source": "bundle_callback",
    }
    finished_success_template = {
        "token": report_token,
        "event": "finished",
        "reporting_source": "bundle_callback",
        "action_results": success_results,
    }
    if reporting_non_executable_results:
        finished_success_template["non_executable_results"] = reporting_non_executable_results
    finished_failed_template = {
        "token": report_token,
        "event": "finished",
        "reporting_source": "bundle_callback",
        "action_results": failed_results,
    }
    if reporting_non_executable_results:
        finished_failed_template["non_executable_results"] = reporting_non_executable_results

    shell_callback_url = shlex.quote(callback_url)
    shell_report_token = shlex.quote(report_token)
    shell_started_template = shlex.quote(json.dumps(started_template, separators=(",", ":")))
    shell_finished_success_template = shlex.quote(json.dumps(finished_success_template, separators=(",", ":")))
    shell_finished_failed_template = shlex.quote(json.dumps(finished_failed_template, separators=(",", ":")))

    return f"""#!/usr/bin/env bash
set +e

REPORT_URL={shell_callback_url}
REPORT_TOKEN={shell_report_token}
STARTED_TEMPLATE={shell_started_template}
FINISHED_SUCCESS_TEMPLATE={shell_finished_success_template}
FINISHED_FAILED_TEMPLATE={shell_finished_failed_template}
REPLAY_DIR="./.bundle-callback-replay"
RUNNER="./run_actions.sh"

mkdir -p "$REPLAY_DIR"

iso_now() {{
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}}

inject_timestamp() {{
  local template_json="$1"
  local field_name="$2"
  local field_value="$3"
  python3 - "$template_json" "$field_name" "$field_value" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
payload[str(sys.argv[2])] = str(sys.argv[3])
print(json.dumps(payload, separators=(",", ":")))
PY
}}

post_payload() {{
  local payload="$1"
  if [ -z "$REPORT_URL" ] || [ -z "$REPORT_TOKEN" ]; then
    return 1
  fi
  if command -v curl >/dev/null 2>&1; then
    curl -sS -X POST "$REPORT_URL" -H "Content-Type: application/json" -d "$payload" >/dev/null 2>&1
    return $?
  fi
  return 1
}}

persist_replay() {{
  local suffix="$1"
  local payload="$2"
  local file="$REPLAY_DIR/${{suffix}}-$(date +%s).json"
  printf '%s\\n' "$payload" > "$file"
}}

STARTED_AT="$(iso_now)"
START_PAYLOAD="$(inject_timestamp "$STARTED_TEMPLATE" "started_at" "$STARTED_AT")"
if ! post_payload "$START_PAYLOAD"; then
  persist_replay "started" "$START_PAYLOAD"
fi

chmod +x "$RUNNER"
"$RUNNER"
RUN_RC=$?

FINISHED_AT="$(iso_now)"
if [ "$RUN_RC" -eq 0 ]; then
  FINISH_PAYLOAD="$(inject_timestamp "$FINISHED_SUCCESS_TEMPLATE" "finished_at" "$FINISHED_AT")"
else
  FINISH_PAYLOAD="$(inject_timestamp "$FINISHED_FAILED_TEMPLATE" "finished_at" "$FINISHED_AT")"
fi

if ! post_payload "$FINISH_PAYLOAD"; then
  persist_replay "finished" "$FINISH_PAYLOAD"
fi

exit "$RUN_RC"
"""


def _generate_group_pr_bundle(
    actions: list[Action],
    *,
    action_decisions: Sequence[_GroupedActionDecision],
    variant: str | None = None,
    callback_url: str | None = None,
    report_token: str | None = None,
) -> dict:
    """
    Generate one combined PR bundle for an execution group.

    Files are namespaced into per-action folders to avoid Terraform resource-name collisions.
    """
    files: list[dict[str, str]] = []
    generated_action_ids: list[uuid.UUID] = []
    generated_action_count = 0
    bundle_rollback_entries: dict[str, dict[str, str]] = {}
    skipped_actions: list[dict[str, str]] = []
    first_generation_error: PRBundleGenerationError | None = None
    run_all_script = """#!/usr/bin/env bash
set -euo pipefail

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is required but not installed."
  exit 1
fi

# Shared Terraform provider cache across bundles (persists under user HOME).
CACHE_ROOT="${HOME}/.aws-security-autopilot/terraform"
mkdir -p "${CACHE_ROOT}/plugin-cache"
export TF_PLUGIN_CACHE_DIR="${CACHE_ROOT}/plugin-cache"
export TF_REGISTRY_CLIENT_TIMEOUT="${TF_REGISTRY_CLIENT_TIMEOUT:-30}"
export TF_REGISTRY_DISCOVERY_RETRY="${TF_REGISTRY_DISCOVERY_RETRY:-3}"

# Use a dedicated CLI config so cache settings are applied consistently.
TFRC_PATH="${CACHE_ROOT}/terraformrc"
if [ ! -f "${TFRC_PATH}" ]; then
  cat > "${TFRC_PATH}" <<EOF
plugin_cache_dir = "${TF_PLUGIN_CACHE_DIR}"
EOF
fi
export TF_CLI_CONFIG_FILE="${TFRC_PATH}"

bootstrap_provider_cache() {
  local marker bootstrap_dir
  marker="${CACHE_ROOT}/.aws-provider-6.31.0.ready"

  if [ -f "${marker}" ] && find "${TF_PLUGIN_CACHE_DIR}" -type f -path '*registry.terraform.io/hashicorp/aws/6.31.0/*' -print -quit 2>/dev/null | grep -q .; then
    return 0
  fi

  bootstrap_dir=$(mktemp -d)
  cat > "${bootstrap_dir}/versions.tf" <<'EOF'
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.31.0"
    }
  }
}
EOF

  (
    cd "${bootstrap_dir}"
    terraform init -backend=false -input=false >/dev/null
  )
  rm -rf "${bootstrap_dir}"
  touch "${marker}"
}

bootstrap_provider_cache

TOTAL=$(find actions -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
if [ "${TOTAL:-0}" -eq 0 ]; then
  echo "No action folders found under actions/."
  exit 0
fi

SHOW_BAR=0
if [ -t 1 ] && [ -z "${CI:-}" ] && [ "${TERM:-}" != "dumb" ]; then
  SHOW_BAR=1
fi

# Fallback ETA (seconds per action) until at least one action completes.
DEFAULT_ACTION_SECS="${ETA_DEFAULT_ACTION_SECS:-90}"
if ! [[ "${DEFAULT_ACTION_SECS}" =~ ^[0-9]+$ ]] || [ "${DEFAULT_ACTION_SECS}" -le 0 ]; then
  DEFAULT_ACTION_SECS=90
fi

START_TS=$(date +%s)
CURRENT_ACTION=""
CURRENT_INDEX=0
SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_ACTIONS=()

is_known_duplicate_only() {
  local log_file="$1"
  local duplicate_pattern
  duplicate_pattern='InvalidPermission\\.Duplicate|already exists|AlreadyExists|EntityAlreadyExists'

  if ! grep -Eiq "$duplicate_pattern" "$log_file"; then
    return 1
  fi
  if grep -Eiq 'AccessDenied|UnauthorizedOperation|InvalidGroupId|DependencyViolation|Throttl|ExpiredToken|not found|NoSuch' "$log_file"; then
    return 1
  fi
  return 0
}

apply_with_duplicate_tolerance() {
  local dir="$1"
  local log_file rc resource existing_id duplicate_line

  log_file=$(mktemp)
  set +e
  (
    cd "$dir"
    terraform apply -auto-approve
  ) >"$log_file" 2>&1
  rc=$?
  set -e
  cat "$log_file"

  if [ "$rc" -eq 0 ]; then
    rm -f "$log_file"
    return 0
  fi

  if is_known_duplicate_only "$log_file"; then
    resource=$(sed -n 's/.*with \\([^,]*\\),/\\1/p' "$log_file" | head -n 1)
    existing_id=$(grep -Eo 'sg-[0-9A-Za-z-]+' "$log_file" | head -n 1)
    duplicate_line=$(grep -Ei 'InvalidPermission\\.Duplicate|already exists|AlreadyExists|EntityAlreadyExists' "$log_file" | head -n 1)
    echo "WARNING: duplicate/already-existing resource detected; continuing without failure."
    echo "  action: $dir"
    if [ -n "$resource" ]; then
      echo "  resource: $resource"
    fi
    if [ -n "$existing_id" ]; then
      echo "  existing identifier: $existing_id"
    fi
    if [ -n "$duplicate_line" ]; then
      echo "  detail: $duplicate_line"
    fi
    rm -f "$log_file"
    return 0
  fi

  rm -f "$log_file"
  return "$rc"
}

format_eta() {
  local seconds="$1"
  local mm ss
  mm=$((seconds / 60))
  ss=$((seconds % 60))
  printf "%02d:%02d" "$mm" "$ss"
}

run_terraform_init_with_retry() {
  local dir="$1"
  local attempts=5
  local attempt=1
  local sleep_seconds=3
  local rc=0

  while [ "$attempt" -le "$attempts" ]; do
    set +e
    (
      cd "$dir"
      terraform init -input=false
    )
    rc=$?
    set -e
    if [ "$rc" -eq 0 ]; then
      return 0
    fi
    if [ "$attempt" -lt "$attempts" ]; then
      echo "WARNING: terraform init failed for $dir (attempt $attempt/$attempts). Retrying in ${sleep_seconds}s..."
      sleep "$sleep_seconds"
      sleep_seconds=$((sleep_seconds * 2))
      if [ "$sleep_seconds" -gt 30 ]; then
        sleep_seconds=30
      fi
    fi
    attempt=$((attempt + 1))
  done

  return "$rc"
}

has_unresolved_placeholders() {
  local dir="$1"
  local placeholders
  placeholders=$(grep -R -n --include='*.tf' -E 'REPLACE_[A-Z0-9_]+' "$dir" 2>/dev/null || true)
  if [ -n "$placeholders" ]; then
    echo "ERROR: unresolved placeholder token(s) found in Terraform files for $dir:"
    echo "$placeholders"
    return 0
  fi
  return 1
}

render_progress() {
  local completed="$1"
  local current_label="$2"
  local pct elapsed remaining eta_secs eta
  local cols bar_width filled empty
  local bar_fill bar_empty

  if [ "$SHOW_BAR" -ne 1 ]; then
    return
  fi

  pct=$((completed * 100 / TOTAL))
  elapsed=$(( $(date +%s) - START_TS ))
  if [ "$completed" -gt 0 ]; then
    remaining=$((TOTAL - completed))
    eta_secs=$((elapsed * remaining / completed))
    eta=$(format_eta "$eta_secs")
  else
    remaining=$((TOTAL - completed))
    eta_secs=$((DEFAULT_ACTION_SECS * remaining))
    eta=$(format_eta "$eta_secs")
  fi

  cols=$(tput cols 2>/dev/null || echo 100)
  bar_width=$((cols - 48))
  if [ "$bar_width" -lt 10 ]; then
    bar_width=10
  fi

  filled=$((pct * bar_width / 100))
  empty=$((bar_width - filled))
  bar_fill=$(printf "%*s" "$filled" "" | tr ' ' '#')
  bar_empty=$(printf "%*s" "$empty" "" | tr ' ' '-')

  printf "\r[%s%s] %3d%% (%d/%d) %s ETA %s" "$bar_fill" "$bar_empty" "$pct" "$completed" "$TOTAL" "$current_label" "$eta"
}

i=0
while IFS= read -r dir; do
  i=$((i + 1))
  CURRENT_INDEX="$i"
  CURRENT_ACTION="$dir"

  render_progress "$((i - 1))" "(${CURRENT_INDEX}/${TOTAL}) ${dir}"
  echo ""
  echo "=== Running terraform in $dir ==="

  if has_unresolved_placeholders "$dir"; then
    echo "ERROR: unresolved placeholders detected for $dir. Skipping this action folder."
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("$dir (precheck)")
    render_progress "$i" "(${CURRENT_INDEX}/${TOTAL}) ${dir}"
    continue
  fi

  if ! run_terraform_init_with_retry "$dir"; then
    echo "ERROR: terraform init failed for $dir after retries. Skipping this action folder."
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("$dir (init)")
    render_progress "$i" "(${CURRENT_INDEX}/${TOTAL}) ${dir}"
    continue
  fi
  render_progress "$((i - 1))" "(${CURRENT_INDEX}/${TOTAL}) ${dir}"

  set +e
  (
    cd "$dir"
    terraform plan -input=false
  )
  plan_rc=$?
  set -e
  if [ "$plan_rc" -ne 0 ]; then
    echo "ERROR: terraform plan failed for $dir. Skipping apply for this action folder."
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("$dir (plan)")
    render_progress "$i" "(${CURRENT_INDEX}/${TOTAL}) ${dir}"
    continue
  fi
  render_progress "$((i - 1))" "(${CURRENT_INDEX}/${TOTAL}) ${dir}"

  if ! apply_with_duplicate_tolerance "$dir"; then
    echo "ERROR: terraform apply failed for $dir. Continuing with remaining action folders."
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("$dir (apply)")
    render_progress "$i" "(${CURRENT_INDEX}/${TOTAL}) ${dir}"
    continue
  fi
  SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
  render_progress "$i" "(${CURRENT_INDEX}/${TOTAL}) ${dir}"
done < <(find actions -mindepth 1 -maxdepth 1 -type d | sort)

if [ "$SHOW_BAR" -eq 1 ]; then
  printf "\n"
fi
echo "Bundle run completed."
echo "  Successful action folders: ${SUCCESS_COUNT}/${TOTAL}"
echo "  Failed action folders: ${FAILED_COUNT}/${TOTAL}"
if [ "$FAILED_COUNT" -gt 0 ]; then
  echo "Failed folders summary:"
  for failed in "${FAILED_ACTIONS[@]}"; do
    echo "  - $failed"
  done
  exit 1
fi
echo "All action folders completed successfully."
    """
    run_all_script = _load_default_runner_script(run_all_script)
    run_all_script, template_source, template_version = _resolve_group_runner_template(run_all_script)
    manifest_lines = [
        "AWS Security Autopilot — Group PR bundle",
        "",
        f"Actions included: {len(actions)}",
        "",
        "Each action is generated in its own Terraform subfolder under actions/.",
        "Use run_all.sh to apply all action folders, or apply folders independently.",
        "run_all.sh preloads hashicorp/aws v6.31.0 once and reuses provider cache at ~/.aws-security-autopilot/terraform/plugin-cache for future bundles.",
        "Run from terminal:",
        "  chmod +x ./run_all.sh",
        "  ./run_all.sh",
        "",
        "Included actions:",
    ]

    if len(actions) != len(action_decisions):
        raise ValueError("grouped action decision count does not match grouped action count")

    for index, (action, decision) in enumerate(zip(actions, action_decisions)):
        if decision.action_id != action.id:
            raise ValueError("grouped action decision order does not match grouped action order")
        folder = _safe_group_folder_name(action, index)
        action_line = f"- {index + 1}. {action.title} | {action.control_id or 'n/a'} | {action.target_id}"
        try:
            per_action_bundle = generate_pr_bundle(
                action,
                format="terraform",
                strategy_id=decision.strategy_id,
                strategy_inputs=decision.strategy_inputs,
                variant=variant,
                resolution=decision.resolution,
            )
        except PRBundleGenerationError as error:
            if first_generation_error is None:
                first_generation_error = error
            payload = error.as_dict()
            code = str(payload.get("code") or "pr_bundle_generation_error")
            detail = str(payload.get("detail") or "PR bundle generation failed for this action.")
            skipped_actions.append(
                {
                    "action_id": str(action.id),
                    "code": code,
                    "detail": detail,
                    "target_id": str(action.target_id or ""),
                }
            )
            manifest_lines.append(f"{action_line} | SKIPPED ({code})")
            files.append(
                {
                    "path": f"errors/{index + 1:02d}-{str(action.id)[:8]}.txt",
                    "content": (
                        f"Action {action.id} was skipped during bundle generation.\n"
                        f"Code: {code}\n"
                        f"Detail: {detail}\n"
                    ),
                }
            )
            continue

        generated_action_count += 1
        generated_action_ids.append(action.id)
        manifest_lines.append(action_line)
        rollback_entry = _bundle_rollback_entry_for_action(
            per_action_bundle,
            action_id=str(action.id),
            folder=folder,
        )
        if rollback_entry is not None:
            bundle_rollback_entries[str(action.id)] = rollback_entry
        for file_item in per_action_bundle.get("files", []):
            if not isinstance(file_item, dict):
                continue
            path = str(file_item.get("path") or "file")
            content = file_item.get("content")
            if content is None:
                content = ""
            elif not isinstance(content, str):
                content = str(content)
            files.append(
                {
                    "path": f"{folder}/{path}",
                    "content": content,
                }
            )

    if generated_action_count == 0 and first_generation_error is not None:
        raise first_generation_error
    if skipped_actions:
        manifest_lines.extend(
            [
                "",
                f"Skipped actions: {len(skipped_actions)}",
                "See errors/*.txt for per-action generation failures.",
            ]
        )

    if callback_url and report_token:
        files.insert(
            0,
            {
                "path": "run_actions.sh",
                "content": run_all_script,
            },
        )
        files.insert(
            0,
            {
                "path": "run_all.sh",
                "content": _build_reporting_wrapper_script(
                    callback_url=callback_url,
                    report_token=report_token,
                    action_ids=generated_action_ids,
                ),
            },
        )
    else:
        files.insert(
            0,
            {
                "path": "run_all.sh",
                "content": run_all_script,
            },
        )
    files.insert(
        0,
        {
            "path": "README_GROUP.txt",
            "content": "\n".join(manifest_lines) + "\n",
        },
    )
    steps = [
        "Open README_GROUP.txt to review all included actions and folders.",
        "Run from bundle root: `chmod +x ./run_all.sh && ./run_all.sh`.",
        "Recompute actions after applying the remediations.",
    ]
    return {
        "format": "terraform",
        "files": files,
        "steps": steps,
        "metadata": {
            "runner_template_source": template_source,
            "runner_template_version": template_version,
            "requested_action_count": len(actions),
            "generated_action_count": generated_action_count,
            "skipped_action_count": len(skipped_actions),
            "skipped_actions": skipped_actions,
            "bundle_rollback_entries": bundle_rollback_entries,
        },
    }


def _generate_mixed_tier_group_pr_bundle(
    actions: list[Action],
    *,
    action_decisions: Sequence[_GroupedActionDecision],
    callback_url: str | None = None,
    report_token: str | None = None,
) -> dict[str, Any]:
    files: list[dict[str, str]] = []
    records: list[dict[str, Any]] = []
    runnable_action_ids: list[uuid.UUID] = []
    bundle_rollback_entries: dict[str, dict[str, str]] = {}
    skipped_actions: list[dict[str, Any]] = []
    first_generation_error: PRBundleGenerationError | None = None
    action_type = actions[0].action_type if actions else None

    if len(actions) != len(action_decisions):
        _raise_invalid_grouped_bundle_layout(
            "Grouped action decision count does not match grouped action count.",
            action_type=action_type,
        )

    runner_script, template_source, template_version = _mixed_tier_runner_script()

    for index, (action, decision) in enumerate(zip(actions, action_decisions)):
        if decision.action_id != action.id:
            _raise_invalid_grouped_bundle_layout(
                "Grouped action decision order does not match grouped action order.",
                action_type=action.action_type,
            )
        tier_root = _grouped_tier_root(decision.support_tier, action_type=action.action_type)
        folder = _safe_group_folder_name(action, index, root=tier_root)
        has_runnable_terraform = False
        generation_error: dict[str, Any] | None = None
        rollback_entry: dict[str, str] | None = None
        if decision.support_tier == "deterministic_bundle":
            try:
                per_action_bundle = generate_pr_bundle(
                    action,
                    format="terraform",
                    strategy_id=decision.strategy_id,
                    strategy_inputs=decision.strategy_inputs,
                    resolution=decision.resolution,
                )
            except PRBundleGenerationError as error:
                if first_generation_error is None:
                    first_generation_error = error
                generation_error = error.as_dict()
                skipped_actions.append(
                    {
                        "action_id": str(action.id),
                        "code": str(generation_error.get("code") or "pr_bundle_generation_error"),
                        "detail": str(
                            generation_error.get("detail") or "PR bundle generation failed for this action."
                        ),
                        "target_id": str(action.target_id or ""),
                        "support_tier": decision.support_tier,
                    }
                )
            else:
                action_files, has_runnable_terraform = _prefixed_group_bundle_files(
                    per_action_bundle,
                    folder=folder,
                )
                if not has_runnable_terraform:
                    _raise_invalid_grouped_bundle_layout(
                        f"Executable action '{action.id}' produced no Terraform files.",
                        action_type=action.action_type,
                    )
                files.extend(action_files)
                runnable_action_ids.append(action.id)
                rollback_entry = _bundle_rollback_entry_for_action(
                    per_action_bundle,
                    action_id=str(action.id),
                    folder=folder,
                )
                if rollback_entry is not None:
                    bundle_rollback_entries[str(action.id)] = rollback_entry
        outcome = _grouped_action_outcome(
            decision.support_tier,
            has_runnable_terraform=has_runnable_terraform,
        )
        record = _grouped_action_record(
            action,
            decision,
            index=index,
            folder=folder,
            tier_root=tier_root,
            outcome=outcome,
            has_runnable_terraform=has_runnable_terraform,
            bundle_rollback_entry=rollback_entry,
            generation_error=generation_error,
        )
        records.append(record)
        _append_grouped_action_metadata_files(files, record)

    _validate_grouped_bundle_records(records, action_type=action_type)
    if not runnable_action_ids and first_generation_error is not None:
        if all(record.get("tier") == "executable" for record in records):
            raise first_generation_error

    manifest = _grouped_bundle_manifest(
        records,
        runner_template_source=template_source,
        runner_template_version=template_version,
    )
    files.insert(
        0,
        {
            "path": "finding_coverage.json",
            "content": _grouped_finding_coverage(records),
        },
    )
    files.insert(
        0,
        {
            "path": "decision_log.md",
            "content": _grouped_decision_log(records) + "\n",
        },
    )
    files.insert(
        0,
        {
            "path": "bundle_manifest.json",
            "content": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        },
    )
    files.insert(
        0,
        {
            "path": "README_GROUP.txt",
            "content": _grouped_bundle_readme(records),
        },
    )
    if callback_url and report_token:
        non_executable_results = [
            _reporting_non_executable_result(record)
            for record in records
            if not bool(record.get("has_runnable_terraform"))
        ]
        files.insert(0, {"path": "run_actions.sh", "content": runner_script})
        files.insert(
            0,
            {
                "path": "run_all.sh",
                "content": _build_reporting_wrapper_script(
                    callback_url=callback_url,
                    report_token=report_token,
                    action_ids=runnable_action_ids,
                    non_executable_results=non_executable_results,
                ),
            },
        )
    else:
        files.insert(0, {"path": "run_all.sh", "content": runner_script})

    tier_counts = manifest["tier_counts"]
    return {
        "format": "terraform",
        "files": files,
        "steps": [
            "Open bundle_manifest.json and decision_log.md to review grouped action outcomes.",
            "Run from bundle root: `chmod +x ./run_all.sh && ./run_all.sh`.",
            "Only executable/actions is runnable; review_required/actions and manual_guidance/actions are metadata only.",
        ],
        "metadata": {
            "layout_version": GROUP_BUNDLE_MIXED_TIER_LAYOUT_VERSION,
            "execution_root": GROUP_BUNDLE_MIXED_TIER_EXECUTION_ROOT,
            "runner_template_source": template_source,
            "runner_template_version": template_version,
            "requested_action_count": len(actions),
            "generated_action_count": len(records),
            "represented_action_count": len(records),
            "runnable_action_count": len(runnable_action_ids),
            "skipped_action_count": len(skipped_actions),
            "skipped_actions": skipped_actions,
            "tier_counts": tier_counts,
            "executable_action_count": int(tier_counts["executable"]),
            "review_required_action_count": int(tier_counts["review_required"]),
            "manual_guidance_action_count": int(tier_counts["manual_guidance"]),
            "bundle_rollback_entries": bundle_rollback_entries,
        },
    }


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
        emit_worker_dispatch_error(
            logger,
            phase="direct_fix_action_missing",
            run_id=str(run.id),
            mode="direct_fix",
        )
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
        emit_worker_dispatch_error(
            logger,
            phase="direct_fix_account_missing",
            run_id=str(run.id),
            action_type=action.action_type,
            mode="direct_fix",
        )
        return

    if not account.role_write_arn:
        run.outcome = (
            "WriteRole not configured for this account. "
            "Use PR-only or add WriteRole ARN in account settings."
        )
        run.status = RemediationRunStatus.failed
        log_lines.append(run.outcome)
        emit_worker_dispatch_error(
            logger,
            phase="direct_fix_writerole_missing",
            run_id=str(run.id),
            action_type=action.action_type,
            mode="direct_fix",
        )
        return

    selected_strategy_id = None

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
        emit_worker_dispatch_error(
            logger,
            phase="assume_role_client_error",
            run_id=str(run.id),
            action_type=action.action_type,
            strategy_id=selected_strategy_id,
            mode="direct_fix",
        )
        return
    except Exception as e:
        logger.exception("Assume WriteRole failed for run_id=%s: %s", run.id, e)
        run.outcome = f"Failed to assume WriteRole: {e}"
        run.status = RemediationRunStatus.failed
        log_lines.append(str(e))
        emit_worker_dispatch_error(
            logger,
            phase="assume_role_exception",
            run_id=str(run.id),
            action_type=action.action_type,
            strategy_id=selected_strategy_id,
            mode="direct_fix",
        )
        return

    # Resolve strategy metadata carried from API validation phase.
    selected_strategy_id = None
    selected_strategy_inputs: dict | None = None
    if isinstance(run.artifacts, dict):
        raw_strategy = run.artifacts.get("selected_strategy")
        if isinstance(raw_strategy, str) and raw_strategy.strip():
            selected_strategy_id = raw_strategy.strip()
        raw_inputs = run.artifacts.get("strategy_inputs")
        if isinstance(raw_inputs, dict):
            selected_strategy_inputs = raw_inputs

    # Run direct fix executor
    log_lines.append(f"Running direct fix: action_type={action.action_type}.")
    try:
        result = run_direct_fix(
            wr_session,
            action_type=action.action_type,
            account_id=action.account_id,
            region=action.region,
            strategy_id=selected_strategy_id,
            strategy_inputs=selected_strategy_inputs,
            run_id=run.id,
            action_id=action.id,
        )
    except Exception as e:
        logger.exception("Direct fix executor failed for run_id=%s: %s", run.id, e)
        run.outcome = f"Direct fix failed: {e}"
        run.status = RemediationRunStatus.failed
        log_lines.append(str(e))
        emit_worker_dispatch_error(
            logger,
            phase="direct_fix_executor_exception",
            run_id=str(run.id),
            action_type=action.action_type,
            strategy_id=selected_strategy_id,
            mode="direct_fix",
        )
        return

    # Update run from executor result
    run.outcome = result.outcome
    run.status = RemediationRunStatus.success if result.success else RemediationRunStatus.failed
    log_lines.extend(result.logs)
    if result.success and result.outcome != "Already compliant; no change needed":
        run.artifacts = run.artifacts or {}
        run.artifacts["direct_fix"] = _direct_fix_artifact_payload(result)


def _block_direct_fix_mutation(
    session: Session,
    run: RemediationRun,
    log_lines: list[str],
    decision: DirectFixApprovalDecision,
) -> None:
    """Fail closed before any direct mutation when approval proof is missing or invalid."""
    approval_path = decision.approval_path or "missing"
    detail = f"Blocked direct_fix mutation: {decision.reason} ({decision.detail})"
    run.outcome = detail
    run.status = RemediationRunStatus.failed
    log_lines.append(detail)
    log_lines.append(f"Approval path: {approval_path}.")
    write_blocked_mutation_audit(
        session,
        run,
        reason=decision.reason,
        detail=decision.detail,
        requested_mode="direct_fix",
        approval_path=decision.approval_path,
    )


def _direct_fix_artifact_payload(result: object) -> dict[str, object]:
    logs = list(getattr(result, "logs", []) or [])
    return {
        "outcome": str(getattr(result, "outcome", "") or "Direct fix applied"),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "post_check_passed": bool(getattr(result, "success", False)),
        "log_count": len(logs),
        "log_excerpt": logs[-3:],
    }


def _ensure_manual_high_risk_marker(run: RemediationRun, strategy_id: str | None) -> bool:
    """Attach manual/high-risk marker for root-credentials-required remediation runs."""
    action_type = run.action.action_type if run.action else None
    if not is_root_credentials_required_action(action_type):
        return False
    approved_by_user_id = getattr(run, "approved_by_user_id", None)
    if not isinstance(approved_by_user_id, uuid.UUID):
        approved_by_user_id = None
    artifacts: dict[str, object] = {}
    if isinstance(run.artifacts, dict):
        artifacts.update(run.artifacts)
    artifacts["manual_high_risk"] = build_manual_high_risk_marker(
        approved_by_user_id=approved_by_user_id,
        strategy_id=strategy_id,
        action_type=action_type,
    )
    run.artifacts = artifacts
    return True


def _apply_pr_bundle_error(
    run: RemediationRun,
    *,
    error: PRBundleGenerationError,
    log_lines: list[str],
) -> str:
    """Store structured PR-bundle error details on remediation run artifacts."""
    payload = error.as_dict()
    artifacts: dict = {}
    if isinstance(run.artifacts, dict):
        artifacts.update(run.artifacts)
    artifacts["pr_bundle_error"] = payload
    run.artifacts = artifacts
    raw_strategy = payload.get("strategy_id")
    selected_strategy_id = raw_strategy if isinstance(raw_strategy, str) and raw_strategy.strip() else None
    _ensure_manual_high_risk_marker(run, selected_strategy_id)
    code = payload.get("code") or "pr_bundle_generation_error"
    detail = payload.get("detail") or "PR bundle generation failed."
    run.outcome = f"PR bundle generation failed: {code}"
    run.status = RemediationRunStatus.failed
    log_lines.append(f"PR bundle generation failed ({code}): {detail}")
    return code


def execute_remediation_run_job(job: dict) -> None:
    """
    Process a remediation_run job: update run row, call PR bundle scaffold for pr_only,
    write outcome, logs, and artifacts. Idempotent: no-op if run is already success/failed.

    Args:
        job: Payload with run_id, tenant_id, action_id, mode (pr_only | direct_fix), created_at.
             Optional key: pr_bundle_variant for PR-only template variants.
    """
    run_id_str = job.get("run_id")
    tenant_id_str = job.get("tenant_id")
    action_id_str = job.get("action_id")
    mode_str = job.get("mode")
    pr_bundle_variant = job.get("pr_bundle_variant")
    strategy_id_raw = job.get("strategy_id")
    strategy_inputs_raw = job.get("strategy_inputs")
    risk_acknowledged_raw = job.get("risk_acknowledged")

    if not run_id_str or not tenant_id_str or not action_id_str or not mode_str:
        emit_worker_dispatch_error(
            logger,
            phase="payload_missing_fields",
            run_id=run_id_str if isinstance(run_id_str, str) else None,
            mode=mode_str if isinstance(mode_str, str) else None,
        )
        raise ValueError("job missing run_id, tenant_id, action_id, or mode")

    try:
        run_uuid = uuid.UUID(run_id_str)
        tenant_uuid = uuid.UUID(tenant_id_str)
        action_uuid = uuid.UUID(action_id_str)
    except (TypeError, ValueError) as e:
        emit_worker_dispatch_error(
            logger,
            phase="payload_invalid_uuid",
            run_id=run_id_str if isinstance(run_id_str, str) else None,
            mode=mode_str if isinstance(mode_str, str) else None,
        )
        raise ValueError(f"invalid run_id/tenant_id/action_id: {e}") from e

    if mode_str not in ("pr_only", "direct_fix"):
        emit_worker_dispatch_error(
            logger,
            phase="payload_invalid_mode",
            run_id=run_id_str,
            mode=mode_str,
        )
        raise ValueError(f"invalid mode: {mode_str}")

    final_status = "unknown"
    worker_error_emitted = False
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
            emit_worker_dispatch_error(
                logger,
                phase="run_not_found",
                run_id=run_id_str,
                mode=mode_str,
            )
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
        _sync_download_bundle_group_runs(session, run)
        session.flush()

        log_lines = [f"Run started at {now.isoformat()}."]

        if mode_str == "pr_only":
            selected_strategy_id: str | None = None
            try:
                action = run.action
                if not action:
                    run.outcome = "Action not found (may have been deleted)"
                    run.status = RemediationRunStatus.failed
                    log_lines.append(run.outcome)
                    emit_worker_dispatch_error(
                        logger,
                        phase="pr_bundle_action_missing",
                        run_id=run_id_str,
                        mode=mode_str,
                    )
                    worker_error_emitted = True
                else:
                    effective_variant = None
                    if isinstance(pr_bundle_variant, str) and pr_bundle_variant.strip():
                        effective_variant = pr_bundle_variant.strip()
                    elif isinstance(run.artifacts, dict):
                        stored_variant = run.artifacts.get("pr_bundle_variant")
                        if isinstance(stored_variant, str) and stored_variant.strip():
                            effective_variant = stored_variant.strip()
                    if isinstance(strategy_id_raw, str) and strategy_id_raw.strip():
                        selected_strategy_id = strategy_id_raw.strip()
                    elif isinstance(run.artifacts, dict):
                        stored_strategy = run.artifacts.get("selected_strategy")
                        if isinstance(stored_strategy, str) and stored_strategy.strip():
                            selected_strategy_id = stored_strategy.strip()
                    selected_strategy_inputs: dict | None = None
                    if isinstance(strategy_inputs_raw, dict):
                        selected_strategy_inputs = strategy_inputs_raw
                    elif isinstance(run.artifacts, dict):
                        stored_inputs = run.artifacts.get("strategy_inputs")
                        if isinstance(stored_inputs, dict):
                            selected_strategy_inputs = stored_inputs
                    risk_acknowledged = bool(risk_acknowledged_raw)
                    if not risk_acknowledged and isinstance(run.artifacts, dict):
                        risk_acknowledged = bool(run.artifacts.get("risk_acknowledged"))
                    selected_risk_snapshot: dict | None = None
                    if isinstance(run.artifacts, dict):
                        stored_risk = run.artifacts.get("risk_snapshot")
                        if isinstance(stored_risk, dict):
                            selected_risk_snapshot = stored_risk
                    selected_resolution = _selected_resolution_payload(job, run)
                    repo_target = _selected_repo_target(job, run)
                    if _ensure_manual_high_risk_marker(run, selected_strategy_id):
                        log_lines.append(
                            f"{MANUAL_HIGH_RISK_MARKER}: {ROOT_CREDENTIALS_REQUIRED_MESSAGE} "
                            f"Runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}."
                        )
                    raw_group_action_ids = job.get("group_action_ids")
                    group_reporting_callback_url: str | None = None
                    group_reporting_token: str | None = None
                    if isinstance(run.artifacts, dict):
                        raw_group = run.artifacts.get("group_bundle")
                        if isinstance(raw_group, dict):
                            if raw_group_action_ids is None:
                                raw_group_action_ids = raw_group.get("action_ids")
                            reporting_config = raw_group.get("reporting")
                            if isinstance(reporting_config, dict):
                                callback_value = reporting_config.get("callback_url")
                                token_value = reporting_config.get("token")
                                if isinstance(callback_value, str) and callback_value.strip():
                                    group_reporting_callback_url = callback_value.strip()
                                if isinstance(token_value, str) and token_value.strip():
                                    group_reporting_token = token_value.strip()
                    group_action_ids = _parse_group_action_ids(raw_group_action_ids)

                    if group_action_ids:
                        group_result = session.execute(
                            select(Action).where(
                                Action.tenant_id == run.tenant_id,
                                Action.id.in_(group_action_ids),
                            )
                        )
                        grouped_actions = group_result.scalars().all()
                        grouped_by_id = {grouped.id: grouped for grouped in grouped_actions}
                        ordered_actions = [grouped_by_id[action_id] for action_id in group_action_ids if action_id in grouped_by_id]

                        if not ordered_actions:
                            run.outcome = "Group bundle generation failed: no actions found for group."
                            run.status = RemediationRunStatus.failed
                            log_lines.append(run.outcome)
                        else:
                            resolved_action_ids = [grouped.id for grouped in ordered_actions]
                            decision_source, action_decisions = _grouped_action_decisions(
                                job=job,
                                run=run,
                                group_action_ids=group_action_ids,
                                resolved_action_ids=resolved_action_ids,
                                strategy_id=selected_strategy_id,
                                strategy_inputs=selected_strategy_inputs,
                                risk_acknowledged=risk_acknowledged,
                                action_type=action.action_type,
                            )
                            if decision_source == "legacy":
                                pr_bundle = _generate_group_pr_bundle(
                                    ordered_actions,
                                    action_decisions=action_decisions,
                                    variant=effective_variant,
                                    callback_url=group_reporting_callback_url,
                                    report_token=group_reporting_token,
                                )
                            else:
                                pr_bundle = _generate_mixed_tier_group_pr_bundle(
                                    ordered_actions,
                                    action_decisions=action_decisions,
                                    callback_url=group_reporting_callback_url,
                                    report_token=group_reporting_token,
                                )
                            grouped_strategy_id = _shared_group_strategy_id(action_decisions)
                            logged_variant = effective_variant if decision_source == "legacy" else None
                            pr_bundle, automation_artifacts = _apply_pr_automation(
                                session=session,
                                run=run,
                                bundle=pr_bundle,
                                actions=ordered_actions,
                                repo_target=repo_target,
                                strategy_id=grouped_strategy_id,
                            )
                            artifacts: dict = {}
                            if isinstance(run.artifacts, dict):
                                artifacts.update(run.artifacts)
                            if effective_variant:
                                artifacts["pr_bundle_variant"] = effective_variant
                            if selected_strategy_id:
                                artifacts["selected_strategy"] = selected_strategy_id
                            if selected_strategy_inputs:
                                artifacts["strategy_inputs"] = selected_strategy_inputs
                            if risk_acknowledged:
                                artifacts["risk_acknowledged"] = True
                            artifacts.update(automation_artifacts)
                            group_bundle = artifacts.get("group_bundle")
                            if not isinstance(group_bundle, dict):
                                # Ensure grouped runs always persist a canonical group bundle payload,
                                # even when triggered without pre-seeded artifacts.
                                group_bundle = {
                                    "action_ids": [str(action_id) for action_id in group_action_ids],
                                    "action_count": len(group_action_ids),
                                }
                                artifacts["group_bundle"] = group_bundle

                            group_bundle["resolved_action_ids"] = [str(grouped.id) for grouped in ordered_actions]
                            group_bundle["resolved_action_count"] = len(ordered_actions)
                            missing_count = max(0, len(group_action_ids) - len(ordered_actions))
                            if missing_count:
                                group_bundle["missing_action_count"] = missing_count
                            if isinstance(pr_bundle, dict):
                                metadata = pr_bundle.get("metadata")
                                if isinstance(metadata, dict):
                                    source = metadata.get("runner_template_source")
                                    version = metadata.get("runner_template_version")
                                    if isinstance(source, str) and source:
                                        group_bundle["runner_template_source"] = source
                                    if isinstance(version, str) and version:
                                        group_bundle["runner_template_version"] = version
                                    generated_count = metadata.get("generated_action_count")
                                    skipped_count = metadata.get("skipped_action_count")
                                    skipped_actions = metadata.get("skipped_actions")
                                    if isinstance(generated_count, int):
                                        group_bundle["generated_action_count"] = generated_count
                                    if isinstance(skipped_count, int):
                                        group_bundle["skipped_action_count"] = skipped_count
                                    if isinstance(skipped_actions, list):
                                        group_bundle["skipped_actions"] = skipped_actions
                                    for key in (
                                        "layout_version",
                                        "execution_root",
                                        "represented_action_count",
                                        "runnable_action_count",
                                        "executable_action_count",
                                        "review_required_action_count",
                                        "manual_guidance_action_count",
                                    ):
                                        value = metadata.get(key)
                                        if isinstance(value, (str, int)):
                                            group_bundle[key] = value
                                    tier_counts = metadata.get("tier_counts")
                                    if isinstance(tier_counts, dict):
                                        group_bundle["tier_counts"] = copy.deepcopy(tier_counts)
                                    for key in (
                                        "diff_fingerprint_sha256",
                                        "repo_target_configured",
                                        "repo_repository",
                                        "repo_base_branch",
                                        "repo_head_branch",
                                        "repo_root_path",
                                    ):
                                        value = metadata.get(key)
                                        if isinstance(value, (str, bool)):
                                            group_bundle[key] = value
                            artifacts["pr_bundle"] = pr_bundle
                            run.artifacts = artifacts
                            generated_count = len(ordered_actions)
                            skipped_generation_count = 0
                            if isinstance(pr_bundle, dict):
                                metadata = pr_bundle.get("metadata")
                                if isinstance(metadata, dict):
                                    generated_value = metadata.get("generated_action_count")
                                    skipped_value = metadata.get("skipped_action_count")
                                    if isinstance(generated_value, int):
                                        generated_count = generated_value
                                    if isinstance(skipped_value, int):
                                        skipped_generation_count = skipped_value
                            if skipped_generation_count > 0:
                                run.outcome = (
                                    "Group PR bundle generated "
                                    f"({generated_count} actions; {skipped_generation_count} skipped)"
                                )
                            else:
                                run.outcome = f"Group PR bundle generated ({generated_count} actions)"
                            run.status = RemediationRunStatus.success
                            if logged_variant:
                                log_lines.append(
                                    "Group PR bundle generated "
                                    f"(actions={generated_count}, variant={logged_variant})."
                                )
                            elif grouped_strategy_id:
                                log_lines.append(
                                    "Group PR bundle generated "
                                    f"(actions={generated_count}, strategy={grouped_strategy_id})."
                                )
                            else:
                                log_lines.append(
                                    f"Group PR bundle generated (actions={generated_count})."
                                )
                            missing_count = max(0, len(group_action_ids) - len(ordered_actions))
                            if missing_count:
                                log_lines.append(
                                    f"Skipped {missing_count} action(s) missing at generation time."
                                )
                            if skipped_generation_count:
                                log_lines.append(
                                    f"Skipped {skipped_generation_count} action(s) with generation errors."
                                )
                            if repo_target:
                                log_lines.append(
                                    "Provider-agnostic PR payload attached for "
                                    f"{repo_target.get('repository', 'configured repository')}."
                                )
                    else:
                        pr_bundle = generate_pr_bundle(
                            action,
                            format="terraform",
                            strategy_id=selected_strategy_id,
                            strategy_inputs=selected_strategy_inputs,
                            risk_snapshot=selected_risk_snapshot,
                            variant=effective_variant,
                            resolution=selected_resolution,
                        )
                        pr_bundle, automation_artifacts = _apply_pr_automation(
                            session=session,
                            run=run,
                            bundle=pr_bundle,
                            actions=[action],
                            repo_target=repo_target,
                            strategy_id=selected_strategy_id,
                        )
                        artifacts: dict = {}
                        if isinstance(run.artifacts, dict):
                            artifacts.update(run.artifacts)
                        if effective_variant:
                            artifacts["pr_bundle_variant"] = effective_variant
                        if selected_strategy_id:
                            artifacts["selected_strategy"] = selected_strategy_id
                        if selected_strategy_inputs:
                            artifacts["strategy_inputs"] = selected_strategy_inputs
                        if risk_acknowledged:
                            artifacts["risk_acknowledged"] = True
                        artifacts.update(automation_artifacts)
                        artifacts["pr_bundle"] = pr_bundle
                        run.artifacts = artifacts
                        bundle_metadata = pr_bundle.get("metadata")
                        non_executable_bundle = (
                            isinstance(bundle_metadata, dict)
                            and bundle_metadata.get("non_executable_bundle") is True
                        )
                        run.outcome = (
                            "Non-executable remediation guidance bundle generated"
                            if non_executable_bundle
                            else "PR bundle generated"
                        )
                        run.status = RemediationRunStatus.success
                        if non_executable_bundle:
                            log_lines.append(
                                "Non-executable remediation guidance bundle generated for "
                                f"action_type={action.action_type}."
                            )
                        elif effective_variant:
                            log_lines.append(
                                "PR bundle generated for "
                                f"action_type={action.action_type} variant={effective_variant}."
                            )
                        elif selected_strategy_id:
                            log_lines.append(
                                "PR bundle generated for "
                                f"action_type={action.action_type} strategy={selected_strategy_id}."
                            )
                        else:
                            log_lines.append(
                                f"PR bundle generated for action_type={action.action_type}."
                            )
                        if repo_target:
                            log_lines.append(
                                "Provider-agnostic PR payload attached for "
                                f"{repo_target.get('repository', 'configured repository')}."
                            )
            except PRBundleGenerationError as error:
                error_code = _apply_pr_bundle_error(run, error=error, log_lines=log_lines)
                emit_worker_dispatch_error(
                    logger,
                    phase=f"pr_bundle_generation_error:{error_code}",
                    run_id=run_id_str,
                    action_type=run.action.action_type if run.action else None,
                    strategy_id=selected_strategy_id,
                    mode=mode_str,
                )
                worker_error_emitted = True
            except Exception as e:
                logger.exception("PR bundle generation failed for run_id=%s: %s", run_id_str, e)
                run.outcome = f"PR bundle generation failed: {e}"
                run.status = RemediationRunStatus.failed
                emit_worker_dispatch_error(
                    logger,
                    phase="pr_bundle_generation_exception",
                    run_id=run_id_str,
                    action_type=run.action.action_type if run.action else None,
                    strategy_id=selected_strategy_id,
                    mode=mode_str,
                )
                worker_error_emitted = True
        else:
            # direct_fix (Step 8.3): load action, account, assume WriteRole, run executor
            decision = evaluate_direct_fix_approval(run, requested_mode=mode_str)
            if decision.allowed:
                _execute_direct_fix(session, run, log_lines)
            else:
                _block_direct_fix_mutation(session, run, log_lines, decision)
                emit_worker_dispatch_error(
                    logger,
                    phase="direct_fix_approval_gate_failed",
                    run_id=run_id_str,
                    action_type=run.action.action_type if run.action else None,
                    mode=mode_str,
                )
                worker_error_emitted = True

        if run.status == RemediationRunStatus.failed and not worker_error_emitted:
            selected_strategy_id = None
            if isinstance(run.artifacts, dict):
                raw_strategy = run.artifacts.get("selected_strategy")
                if isinstance(raw_strategy, str) and raw_strategy.strip():
                    selected_strategy_id = raw_strategy.strip()
            emit_worker_dispatch_error(
                logger,
                phase="run_failed",
                run_id=run_id_str,
                action_type=run.action.action_type if run.action else None,
                strategy_id=selected_strategy_id,
                mode=mode_str,
            )

        run.completed_at = datetime.now(timezone.utc)
        log_lines.append(f"Run completed at {run.completed_at.isoformat()}.")
        run.logs = "\n".join(log_lines)
        _sync_download_bundle_group_runs(session, run)

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
