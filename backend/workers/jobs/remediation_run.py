"""
Remediation run job handler (Step 7.3 + 8.3).

Picks up remediation_run jobs from SQS, updates run status (pending → running → success/failed),
calls PR bundle generator for pr_only, or direct fix executor for direct_fix. Idempotent: skips
if run already success or failed.
"""
from __future__ import annotations

import logging
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
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
from backend.services.remediation_metrics import emit_worker_dispatch_error
from backend.services.pr_bundle import PRBundleGenerationError, generate_pr_bundle
from backend.services.remediation_audit import allow_update_outcome, write_remediation_run_audit
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
    for row in rows:
        if run.status == RemediationRunStatus.running:
            if row.status == ActionGroupRunStatus.queued:
                row.status = ActionGroupRunStatus.started
            if row.started_at is None:
                row.started_at = run.started_at or now
            continue

        if run.status == RemediationRunStatus.success:
            row.status = ActionGroupRunStatus.finished
        elif run.status == RemediationRunStatus.failed:
            row.status = ActionGroupRunStatus.failed
        elif run.status == RemediationRunStatus.cancelled:
            row.status = ActionGroupRunStatus.cancelled
        else:
            continue

        if row.started_at is None:
            row.started_at = run.started_at or now
        row.finished_at = run.completed_at or now


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


def _safe_group_folder_name(action: Action, index: int) -> str:
    """Build a stable, filesystem-safe folder path for one action in a group bundle."""
    base = (action.resource_id or action.target_id or action.action_type or "action").lower()
    normalized = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in base)
    normalized = "-".join(part for part in normalized.split("-") if part)
    if not normalized:
        normalized = "action"
    return f"actions/{index + 1:02d}-{normalized[:48]}-{str(action.id)[:8]}"


def _build_reporting_wrapper_script(
    *,
    callback_url: str,
    report_token: str,
    action_ids: list[uuid.UUID],
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
    finished_failed_template = {
        "token": report_token,
        "event": "finished",
        "reporting_source": "bundle_callback",
        "action_results": failed_results,
    }

    return f"""#!/usr/bin/env bash
set +e

REPORT_URL={json.dumps(callback_url)}
REPORT_TOKEN={json.dumps(report_token)}
STARTED_TEMPLATE={json.dumps(started_template)}
FINISHED_SUCCESS_TEMPLATE={json.dumps(finished_success_template)}
FINISHED_FAILED_TEMPLATE={json.dumps(finished_failed_template)}
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
    variant: str | None = None,
    strategy_id: str | None = None,
    strategy_inputs: dict | None = None,
    callback_url: str | None = None,
    report_token: str | None = None,
) -> dict:
    """
    Generate one combined PR bundle for an execution group.

    Files are namespaced into per-action folders to avoid Terraform resource-name collisions.
    """
    files: list[dict[str, str]] = []
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

    for index, action in enumerate(actions):
        per_action_bundle = generate_pr_bundle(
            action,
            format="terraform",
            strategy_id=strategy_id,
            strategy_inputs=strategy_inputs,
            variant=variant,
        )
        folder = _safe_group_folder_name(action, index)
        manifest_lines.append(
            f"- {index + 1}. {action.title} | {action.control_id or 'n/a'} | {action.target_id}"
        )
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
                    action_ids=[action.id for action in actions],
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
        run.artifacts["direct_fix"] = {"outcome": result.outcome}


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
                    if _ensure_manual_high_risk_marker(run, selected_strategy_id):
                        log_lines.append(
                            f"{MANUAL_HIGH_RISK_MARKER}: {ROOT_CREDENTIALS_REQUIRED_MESSAGE} "
                            f"Runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}."
                        )
                    raw_group_action_ids = job.get("group_action_ids")
                    group_reporting_callback_url: str | None = None
                    group_reporting_token: str | None = None
                    if raw_group_action_ids is None and isinstance(run.artifacts, dict):
                        raw_group = run.artifacts.get("group_bundle")
                        if isinstance(raw_group, dict):
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
                            pr_bundle = _generate_group_pr_bundle(
                                ordered_actions,
                                variant=effective_variant,
                                strategy_id=selected_strategy_id,
                                strategy_inputs=selected_strategy_inputs,
                                callback_url=group_reporting_callback_url,
                                report_token=group_reporting_token,
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
                            artifacts["pr_bundle"] = pr_bundle
                            run.artifacts = artifacts
                            run.outcome = f"Group PR bundle generated ({len(ordered_actions)} actions)"
                            run.status = RemediationRunStatus.success
                            if effective_variant:
                                log_lines.append(
                                    "Group PR bundle generated "
                                    f"(actions={len(ordered_actions)}, variant={effective_variant})."
                                )
                            elif selected_strategy_id:
                                log_lines.append(
                                    "Group PR bundle generated "
                                    f"(actions={len(ordered_actions)}, strategy={selected_strategy_id})."
                                )
                            else:
                                log_lines.append(
                                    f"Group PR bundle generated (actions={len(ordered_actions)})."
                                )
                            missing_count = max(0, len(group_action_ids) - len(ordered_actions))
                            if missing_count:
                                log_lines.append(
                                    f"Skipped {missing_count} action(s) missing at generation time."
                                )
                    else:
                        pr_bundle = generate_pr_bundle(
                            action,
                            format="terraform",
                            strategy_id=selected_strategy_id,
                            strategy_inputs=selected_strategy_inputs,
                            risk_snapshot=selected_risk_snapshot,
                            variant=effective_variant,
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
                        artifacts["pr_bundle"] = pr_bundle
                        run.artifacts = artifacts
                        run.outcome = "PR bundle generated"
                        run.status = RemediationRunStatus.success
                        if effective_variant:
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
            _execute_direct_fix(session, run, log_lines)

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
