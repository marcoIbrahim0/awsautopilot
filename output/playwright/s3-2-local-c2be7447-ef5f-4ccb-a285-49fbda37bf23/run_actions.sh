#!/usr/bin/env bash
set -euo pipefail

EXECUTION_ROOT="${EXECUTION_ROOT:-executable/actions}"
MANIFEST_PATH="${BUNDLE_MANIFEST_PATH:-./bundle_manifest.json}"
SUMMARY_PATH="${BUNDLE_EXECUTION_SUMMARY_PATH:-./.bundle-execution-summary.json}"
STATUS_JOURNAL="$(mktemp)"

cleanup_temp_files() {
  rm -f "${STATUS_JOURNAL}"
}
trap cleanup_temp_files EXIT

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is required but not installed."
  exit 1
fi

# Shared Terraform provider cache across bundles.
CACHE_ROOT="${HOME}/.aws-security-autopilot/terraform"
mkdir -p "${CACHE_ROOT}/plugin-cache" "${CACHE_ROOT}/provider-mirror"
export TF_PLUGIN_CACHE_DIR="${CACHE_ROOT}/plugin-cache"
export TF_PROVIDER_MIRROR_DIR="${CACHE_ROOT}/provider-mirror"
PREFERRED_TF_PROVIDER_MIRROR_DIR="${HOME}/.terraform.d/plugin-cache"
ACTIVE_TF_PROVIDER_MIRROR_DIR="${TF_PROVIDER_MIRROR_DIR}"
export TF_REGISTRY_CLIENT_TIMEOUT="${TF_REGISTRY_CLIENT_TIMEOUT:-30}"
export TF_REGISTRY_DISCOVERY_RETRY="${TF_REGISTRY_DISCOVERY_RETRY:-3}"

# Use a dedicated CLI config so cache settings are applied consistently.
TFRC_PATH="${CACHE_ROOT}/terraformrc"
write_tfrc_with_cache_only() {
  cat > "${TFRC_PATH}" <<EOF
plugin_cache_dir = "${TF_PLUGIN_CACHE_DIR}"
EOF
}

write_tfrc_with_mirror() {
  local mirror_dir="$1"
  cat > "${TFRC_PATH}" <<EOF
provider_installation {
  filesystem_mirror {
    path    = "${mirror_dir}"
    include = ["registry.terraform.io/hashicorp/aws"]
  }
  direct {
    exclude = ["registry.terraform.io/hashicorp/aws"]
  }
}
EOF
}

export TF_CLI_CONFIG_FILE="${TFRC_PATH}"

AWS_PROVIDER_VERSION="5.100.0"
AWS_PROVIDER_LOCKFILE="${CACHE_ROOT}/.aws-provider-${AWS_PROVIDER_VERSION}.lock.hcl"
TERRAFORM_PROVIDER_OS="$(uname | tr '[:upper:]' '[:lower:]')"
TERRAFORM_PROVIDER_ARCH="$(uname -m)"
case "${TERRAFORM_PROVIDER_ARCH}" in
  x86_64)
    TERRAFORM_PROVIDER_ARCH="amd64"
    ;;
  aarch64|arm64)
    TERRAFORM_PROVIDER_ARCH="arm64"
    ;;
esac
TERRAFORM_PROVIDER_PLATFORM="${TERRAFORM_PROVIDER_OS}_${TERRAFORM_PROVIDER_ARCH}"

has_cached_aws_provider() {
  find -L "${TF_PLUGIN_CACHE_DIR}/registry.terraform.io/hashicorp/aws/${AWS_PROVIDER_VERSION}" -type f -name 'terraform-provider-aws_v*_x5' -print -quit 2>/dev/null | grep -q .
}

has_mirrored_aws_provider() {
  local mirror_dir="${1:-${ACTIVE_TF_PROVIDER_MIRROR_DIR}}"
  find -L "${mirror_dir}/registry.terraform.io/hashicorp/aws/${AWS_PROVIDER_VERSION}" -type f -print -quit 2>/dev/null | grep -q .
}

has_preferred_mirrored_aws_provider() {
  has_mirrored_aws_provider "${PREFERRED_TF_PROVIDER_MIRROR_DIR}"
}

bootstrap_provider_cache() {
  local bootstrap_dir marker
  marker="${CACHE_ROOT}/.aws-provider-${AWS_PROVIDER_VERSION}.ready"
  ACTIVE_TF_PROVIDER_MIRROR_DIR="${TF_PROVIDER_MIRROR_DIR}"
  if has_preferred_mirrored_aws_provider; then
    ACTIVE_TF_PROVIDER_MIRROR_DIR="${PREFERRED_TF_PROVIDER_MIRROR_DIR}"
  fi
  if [ -f "${marker}" ] && has_mirrored_aws_provider "${ACTIVE_TF_PROVIDER_MIRROR_DIR}" && [ -s "${AWS_PROVIDER_LOCKFILE}" ]; then
    return 0
  fi

  bootstrap_dir=$(mktemp -d)
  cat > "${bootstrap_dir}/versions.tf" <<'EOF'
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.100.0"
    }
  }
}
EOF

  if [ "${ACTIVE_TF_PROVIDER_MIRROR_DIR}" = "${PREFERRED_TF_PROVIDER_MIRROR_DIR}" ]; then
    (
      cd "${bootstrap_dir}"
      terraform providers lock -fs-mirror="${ACTIVE_TF_PROVIDER_MIRROR_DIR}" -platform="${TERRAFORM_PROVIDER_PLATFORM}" >/dev/null
      cp .terraform.lock.hcl "${AWS_PROVIDER_LOCKFILE}"
    )
  else
    (
      cd "${bootstrap_dir}"
      env -u TF_CLI_CONFIG_FILE -u TF_PLUGIN_CACHE_DIR -u TF_PROVIDER_MIRROR_DIR terraform providers mirror "${ACTIVE_TF_PROVIDER_MIRROR_DIR}" >/dev/null
      terraform providers lock -fs-mirror="${ACTIVE_TF_PROVIDER_MIRROR_DIR}" -platform="${TERRAFORM_PROVIDER_PLATFORM}" >/dev/null
      cp .terraform.lock.hcl "${AWS_PROVIDER_LOCKFILE}"
    )
  fi
  rm -rf "${bootstrap_dir}"
  touch "${marker}"
}

seed_canonical_aws_lockfile() {
  local dir="$1"
  if [ ! -s "${AWS_PROVIDER_LOCKFILE}" ]; then
    echo "ERROR: canonical AWS provider lockfile is missing at ${AWS_PROVIDER_LOCKFILE}."
    return 1
  fi
  rm -rf "$dir/.terraform"
  cp "${AWS_PROVIDER_LOCKFILE}" "$dir/.terraform.lock.hcl"
}

terraform_init_with_lockfile_fallback() {
  local dir="$1"
  local log_file rc
  log_file=$(mktemp)
  set +e
  (
    cd "$dir"
    terraform init -input=false -lockfile=readonly
  ) 2>&1 | tee "$log_file"
  rc=${PIPESTATUS[0]}
  set -e
  if [ "$rc" -eq 0 ]; then
    rm -f "$log_file"
    return 0
  fi
  if ! grep -q "Provider dependency changes detected" "$log_file"; then
    rm -f "$log_file"
    return "$rc"
  fi
  echo "WARNING: terraform init detected additional providers for $dir; refreshing lockfile."
  rm -f "$log_file"
  (
    cd "$dir"
    terraform init -input=false
  )
}

copy_action_folder_to_workspace() {
  local source_dir="$1"
  local workspace_dir="$2"

  mkdir -p "$workspace_dir"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude '.terraform' --exclude '.terraform.tfstate*' "$source_dir"/ "$workspace_dir"/
    return 0
  fi

  (
    cd "$source_dir"
    tar --exclude='.terraform' --exclude='.terraform.tfstate*' -cf - .
  ) | (
    cd "$workspace_dir"
    tar -xf -
  )
}

prepare_action_workspace() {
  local source_dir="$1"
  local workspace_root workspace_dir

  workspace_root=$(mktemp -d "${TMPDIR:-/tmp}/aws-security-autopilot-tf-XXXXXX")
  workspace_dir="${workspace_root}/action"
  if ! copy_action_folder_to_workspace "$source_dir" "$workspace_dir"; then
    rm -rf "$workspace_root"
    return 1
  fi
  printf '%s\n' "$workspace_dir"
}

cleanup_action_workspace() {
  local workspace_dir="$1"
  local workspace_root

  workspace_root=$(dirname "$workspace_dir")
  rm -rf "$workspace_root"
}

manifest_shared_field() {
  local folder="$1"
  local field="$2"
  if [ ! -f "${MANIFEST_PATH}" ]; then
    return 0
  fi
  python3 - "${MANIFEST_PATH}" "$folder" "$field" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
folder = sys.argv[2]
field = sys.argv[3]
try:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
except Exception:
    sys.exit(0)
for item in manifest.get("shared_execution_folders") or []:
    if not isinstance(item, dict):
        continue
    if str(item.get("folder") or "") != folder:
        continue
    value = item.get(field)
    if value is None:
        sys.exit(0)
    if isinstance(value, (dict, list)):
        print(json.dumps(value, separators=(",", ":")))
    else:
        print(str(value))
    break
PY
}

manifest_shared_folders() {
  if [ ! -f "${MANIFEST_PATH}" ]; then
    return 0
  fi
  python3 - "${MANIFEST_PATH}" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
try:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
except Exception:
    sys.exit(0)

for item in manifest.get("shared_execution_folders") or []:
    if not isinstance(item, dict):
        continue
    folder = str(item.get("folder") or "").strip()
    if folder:
        print(folder)
PY
}

prepare_shared_folder_tfvars() {
  local source_dir="$1"
  local workspace_dir="$2"
  local shared_kind bucket_name tfvars_path error_file
  shared_kind=$(manifest_shared_field "$source_dir" "kind")
  if [ "$shared_kind" != "s3_access_logging_destination_setup" ]; then
    return 0
  fi
  bucket_name=$(manifest_shared_field "$source_dir" "destination_bucket_name")
  if [ -z "$bucket_name" ]; then
    echo "ERROR: shared execution folder metadata is missing destination_bucket_name for $source_dir."
    return 1
  fi

  tfvars_path="${workspace_dir}/security_autopilot.auto.tfvars.json"
  if ! command -v aws >/dev/null 2>&1; then
    cat > "${tfvars_path}" <<EOF
{"create_log_bucket": true}
EOF
    return 0
  fi

  error_file=$(mktemp)
  if aws s3api get-bucket-location --bucket "$bucket_name" >/dev/null 2>"$error_file"; then
    cat > "${tfvars_path}" <<EOF
{"create_log_bucket": false}
EOF
    rm -f "$error_file"
    return 0
  fi
  if grep -Eiq 'NoSuchBucket|Not Found|404' "$error_file"; then
    cat > "${tfvars_path}" <<EOF
{"create_log_bucket": true}
EOF
    rm -f "$error_file"
    return 0
  fi
  echo "ERROR: unable to verify whether shared destination bucket ${bucket_name} already exists and is owned."
  cat "$error_file"
  rm -f "$error_file"
  return 1
}

bootstrap_provider_cache
write_tfrc_with_mirror "${ACTIVE_TF_PROVIDER_MIRROR_DIR}"

if [ -d "${EXECUTION_ROOT}" ]; then
  mapfile -t ACTION_DIRS < <(find "${EXECUTION_ROOT}" -mindepth 1 -maxdepth 1 -type d | sort)
else
  ACTION_DIRS=()
fi
mapfile -t SHARED_DIRS < <(manifest_shared_folders)
NON_SHARED_ACTION_DIRS=()
if [ "${#SHARED_DIRS[@]}" -gt 0 ]; then
  for dir in "${ACTION_DIRS[@]}"; do
    is_shared_dir=0
    for shared_dir in "${SHARED_DIRS[@]}"; do
      if [ "$dir" = "$shared_dir" ]; then
        is_shared_dir=1
        break
      fi
    done
    if [ "$is_shared_dir" -eq 0 ]; then
      NON_SHARED_ACTION_DIRS+=("$dir")
    fi
  done
else
  NON_SHARED_ACTION_DIRS=("${ACTION_DIRS[@]}")
fi
TOTAL="${#ACTION_DIRS[@]}"
if [ "${TOTAL:-0}" -eq 0 ]; then
  python3 - "${SUMMARY_PATH}" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    json.dumps({"action_results": [], "shared_execution_results": []}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
  echo "No executable Terraform action folders found under ${EXECUTION_ROOT}/."
  exit 0
fi

SHOW_BAR=0
if [ -t 1 ] && [ -z "${CI:-}" ] && [ "${TERM:-}" != "dumb" ]; then
  SHOW_BAR=1
fi

DEFAULT_ACTION_SECS="${ETA_DEFAULT_ACTION_SECS:-90}"
if ! [[ "${DEFAULT_ACTION_SECS}" =~ ^[0-9]+$ ]] || [ "${DEFAULT_ACTION_SECS}" -le 0 ]; then
  DEFAULT_ACTION_SECS=90
fi

ACTION_TIMEOUT_SECS="${ACTION_TIMEOUT_SECS:-300}"
if ! [[ "${ACTION_TIMEOUT_SECS}" =~ ^[0-9]+$ ]] || [ "${ACTION_TIMEOUT_SECS}" -le 0 ]; then
  ACTION_TIMEOUT_SECS=300
fi

START_TS=$(date +%s)
SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_ACTIONS=()

DEFAULT_PARALLEL_BUNDLES=3
MAX_PARALLEL_BUNDLES=5
REQUESTED_PARALLEL="${PARALLEL_BUNDLES:-$DEFAULT_PARALLEL_BUNDLES}"
if ! [[ "${REQUESTED_PARALLEL}" =~ ^[0-9]+$ ]] || [ "${REQUESTED_PARALLEL}" -le 0 ]; then
  REQUESTED_PARALLEL="$DEFAULT_PARALLEL_BUNDLES"
fi
if [ "${REQUESTED_PARALLEL}" -gt "${MAX_PARALLEL_BUNDLES}" ]; then
  REQUESTED_PARALLEL="${MAX_PARALLEL_BUNDLES}"
fi
if [ "${REQUESTED_PARALLEL}" -gt "${TOTAL}" ]; then
  REQUESTED_PARALLEL="${TOTAL}"
fi
PARALLEL_BUNDLE_EXECUTIONS="${REQUESTED_PARALLEL}"

is_known_duplicate_only() {
  local log_file="$1"
  local duplicate_pattern
  local error_lines
  duplicate_pattern='InvalidPermission\.Duplicate|already exists|AlreadyExists|EntityAlreadyExists'
  error_lines=$(sed -E $'s/\x1B\\[[0-9;]*[[:alpha:]]//g' "$log_file" | grep -E '^[[:space:]]*(Error:|│)' || true)

  if [ -z "$error_lines" ]; then
    return 1
  fi
  if ! printf '%s\n' "$error_lines" | grep -Eiq "$duplicate_pattern"; then
    return 1
  fi
  if printf '%s\n' "$error_lines" | grep -Eiq 'AccessDenied|UnauthorizedOperation|InvalidGroupId|DependencyViolation|Throttl|ExpiredToken|not found|NoSuch'; then
    return 1
  fi
  return 0
}

is_shared_s3_destination_owned_error() {
  local log_file="$1"
  if ! grep -Eiq 'BucketAlreadyOwnedByYou' "$log_file"; then
    return 1
  fi
  if grep -Eiq 'AccessDenied|UnauthorizedOperation|InvalidGroupId|DependencyViolation|Throttl|ExpiredToken|not found|NoSuch' "$log_file"; then
    return 1
  fi
  return 0
}

apply_with_duplicate_tolerance() {
  local dir="$1"
  local source_dir="$2"
  local timeout_secs="${3:-${ACTION_TIMEOUT_SECS}}"
  local log_file rc resource existing_id duplicate_line shared_kind
  export TF_DATA_DIR="${dir}/.terraform-data"
  mkdir -p "${TF_DATA_DIR}"

  log_file=$(mktemp)
  set +e
  (
    cd "$dir"
    run_with_timeout "$timeout_secs" terraform apply -auto-approve
  ) >"$log_file" 2>&1
  rc=$?
  set -e
  cat "$log_file"

  if [ "$rc" -eq 0 ]; then
    rm -f "$log_file"
    return 0
  fi

  shared_kind=$(manifest_shared_field "$source_dir" "kind")
  if [ "$shared_kind" = "s3_access_logging_destination_setup" ] && is_shared_s3_destination_owned_error "$log_file"; then
    duplicate_line=$(grep -Ei 'BucketAlreadyOwnedByYou' "$log_file" | head -n 1)
    echo "WARNING: shared S3.9 destination bucket already exists and is owned; continuing without failure."
    echo "  action: $source_dir"
    if [ -n "$duplicate_line" ]; then
      echo "  detail: $duplicate_line"
    fi
    rm -f "$log_file"
    return 0
  fi

  if is_known_duplicate_only "$log_file"; then
    resource=$(sed -n 's/.*with \([^,]*\),/\1/p' "$log_file" | head -n 1)
    existing_id=$(grep -Eo 'sg-[0-9A-Za-z-]+' "$log_file" | head -n 1)
    duplicate_line=$(grep -Ei 'InvalidPermission\.Duplicate|already exists|AlreadyExists|EntityAlreadyExists' "$log_file" | head -n 1)
    echo "WARNING: duplicate/already-existing resource detected; continuing without failure."
    echo "  action: $source_dir"
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
  export TF_DATA_DIR="${dir}/.terraform-data"
  mkdir -p "${TF_DATA_DIR}"

  while [ "$attempt" -le "$attempts" ]; do
    if ! seed_canonical_aws_lockfile "$dir"; then
      return 1
    fi
    set +e
    terraform_init_with_lockfile_fallback "$dir"
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

run_with_timeout() {
  local timeout_secs="$1"
  shift
  python3 - "$timeout_secs" "$@" <<'PY'
import subprocess
import sys

timeout_secs = int(sys.argv[1])
command = sys.argv[2:]
try:
    completed = subprocess.run(command, check=False, timeout=timeout_secs)
except subprocess.TimeoutExpired:
    print(f"ERROR: command timed out after {timeout_secs}s: {' '.join(command)}")
    sys.exit(124)
sys.exit(int(completed.returncode))
PY
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

write_status_journal() {
  local status="$1"
  local dir="$2"
  local stage="$3"
  printf '%s|%s|%s\n' "$status" "$dir" "$stage" >> "${STATUS_JOURNAL}"
}

build_execution_summary() {
  python3 - "${MANIFEST_PATH}" "${STATUS_JOURNAL}" "${SUMMARY_PATH}" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
journal_path = Path(sys.argv[2])
summary_path = Path(sys.argv[3])

manifest = {}
if manifest_path.is_file():
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        manifest = {}

statuses = {}
if journal_path.is_file():
    for raw_line in journal_path.read_text(encoding="utf-8").splitlines():
        parts = raw_line.split("|", 2)
        if len(parts) != 3:
            continue
        statuses[parts[1]] = {"status": parts[0], "stage": parts[2]}

def result_for_folder(folder: str) -> dict:
    entry = statuses.get(folder) or {"status": "failed", "stage": "missing"}
    if entry["status"] == "success":
        return {"execution_status": "success"}
    stage = entry["stage"] or "unknown"
    return {
        "execution_status": "failed",
        "execution_error_code": f"bundle_runner_{stage}",
        "execution_error_message": f"run_all.sh failed during {stage} for folder {folder}",
    }

action_results = []
for item in manifest.get("actions") or []:
    if not isinstance(item, dict) or not item.get("has_runnable_terraform"):
        continue
    folder = str(item.get("folder") or "").strip()
    action_id = str(item.get("action_id") or "").strip()
    if not folder or not action_id:
        continue
    result = result_for_folder(folder)
    result["action_id"] = action_id
    action_results.append(result)

shared_execution_results = []
for item in manifest.get("shared_execution_folders") or []:
    if not isinstance(item, dict):
        continue
    folder = str(item.get("folder") or "").strip()
    kind = str(item.get("kind") or "").strip()
    if not folder or not kind:
        continue
    result = result_for_folder(folder)
    shared_execution_results.append(
        {
            "folder": folder,
            "kind": kind,
            "execution_status": result["execution_status"],
            "execution_error_code": result.get("execution_error_code"),
            "execution_error_message": result.get("execution_error_message"),
            "details": {
                key: value
                for key, value in item.items()
                if key not in {"folder", "kind"}
            },
        }
    )

summary_path.write_text(
    json.dumps(
        {
            "action_results": action_results,
            "shared_execution_results": shared_execution_results,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY
}

i=0
COMPLETED_COUNT=0
pids=()
pid_dirs=()
pid_status=()

run_one_bundle() {
  local dir="$1"
  local status_file="$2"
  local workspace_dir=""

  echo ""
  echo "=== Running terraform in $dir ==="

  if has_unresolved_placeholders "$dir"; then
    echo "ERROR: unresolved placeholders detected for $dir. Skipping this action folder."
    printf "failed|%s|precheck\n" "$dir" > "$status_file"
    return 0
  fi

  workspace_dir=$(prepare_action_workspace "$dir") || {
    echo "ERROR: failed to prepare isolated terraform workspace for $dir. Skipping this action folder."
    printf "failed|%s|workspace\n" "$dir" > "$status_file"
    return 0
  }

  if ! prepare_shared_folder_tfvars "$dir" "$workspace_dir"; then
    cleanup_action_workspace "$workspace_dir"
    printf "failed|%s|shared_preflight\n" "$dir" > "$status_file"
    return 0
  fi

  if ! run_terraform_init_with_retry "$workspace_dir"; then
    echo "ERROR: terraform init failed for $dir after retries. Skipping this action folder."
    cleanup_action_workspace "$workspace_dir"
    printf "failed|%s|init\n" "$dir" > "$status_file"
    return 0
  fi

  set +e
  (
    cd "$workspace_dir"
    run_with_timeout "$ACTION_TIMEOUT_SECS" terraform plan -input=false
  )
  plan_rc=$?
  set -e
  if [ "$plan_rc" -ne 0 ]; then
    echo "ERROR: terraform plan failed for $dir. Skipping apply for this action folder."
    cleanup_action_workspace "$workspace_dir"
    printf "failed|%s|plan\n" "$dir" > "$status_file"
    return 0
  fi

  if ! apply_with_duplicate_tolerance "$workspace_dir" "$dir" "$ACTION_TIMEOUT_SECS"; then
    echo "ERROR: terraform apply failed for $dir. Continuing with remaining action folders."
    cleanup_action_workspace "$workspace_dir"
    printf "failed|%s|apply\n" "$dir" > "$status_file"
    return 0
  fi
  cleanup_action_workspace "$workspace_dir"
  printf "success|%s|done\n" "$dir" > "$status_file"
  return 0
}

consume_status_file() {
  local dir="$1"
  local status_file="$2"
  local line status detail stage

  line="$(cat "$status_file" 2>/dev/null || true)"
  status="${line%%|*}"
  detail="${line#*|}"
  stage="${detail##*|}"
  detail="${detail%|*}"
  if [ "$status" = "success" ]; then
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
  else
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("${detail:-$dir} (${stage:-unknown})")
  fi
  write_status_journal "${status:-failed}" "${detail:-$dir}" "${stage:-unknown}"
  rm -f "$status_file"
  COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
  render_progress "$COMPLETED_COUNT" "(${COMPLETED_COUNT}/${TOTAL}) parallel=${PARALLEL_BUNDLE_EXECUTIONS}"
}

wait_for_one_bundle() {
  local idx pid dir status_file
  while true; do
    for idx in "${!pids[@]}"; do
      pid="${pids[$idx]}"
      if ! kill -0 "$pid" 2>/dev/null; then
        set +e
        wait "$pid" >/dev/null 2>&1
        set -e
        dir="${pid_dirs[$idx]}"
        status_file="${pid_status[$idx]}"
        consume_status_file "$dir" "$status_file"
        unset 'pids[idx]'
        unset 'pid_dirs[idx]'
        unset 'pid_status[idx]'
        pids=("${pids[@]}")
        pid_dirs=("${pid_dirs[@]}")
        pid_status=("${pid_status[@]}")
        return 0
      fi
    done
    sleep 1
  done
}

echo "Running ${TOTAL} bundle folder(s) from ${EXECUTION_ROOT} with shared folders=${#SHARED_DIRS[@]} and parallel action executions=${PARALLEL_BUNDLE_EXECUTIONS} (max=${MAX_PARALLEL_BUNDLES})"
for dir in "${SHARED_DIRS[@]}"; do
  i=$((i + 1))
  render_progress "$COMPLETED_COUNT" "(${i}/${TOTAL}) shared ${dir}"
  status_file="$(mktemp)"
  run_one_bundle "$dir" "$status_file"
  consume_status_file "$dir" "$status_file"
done

for dir in "${NON_SHARED_ACTION_DIRS[@]}"; do
  i=$((i + 1))
  render_progress "$COMPLETED_COUNT" "(${i}/${TOTAL}) queued ${dir}"
  status_file="$(mktemp)"
  ( run_one_bundle "$dir" "$status_file" ) &
  pids+=("$!")
  pid_dirs+=("$dir")
  pid_status+=("$status_file")

  while [ "${#pids[@]}" -ge "${PARALLEL_BUNDLE_EXECUTIONS}" ]; do
    wait_for_one_bundle
  done
done

while [ "${#pids[@]}" -gt 0 ]; do
  wait_for_one_bundle
done

build_execution_summary

if [ "$SHOW_BAR" -eq 1 ]; then
  printf "\n"
fi
echo "Bundle run completed."
echo "  Successful action folders: ${SUCCESS_COUNT}/${TOTAL}"
echo "  Failed action folders: ${FAILED_COUNT}/${TOTAL}"
echo "  Summary file: ${SUMMARY_PATH}"
if [ "$FAILED_COUNT" -gt 0 ]; then
  echo "Failed folders summary:"
  for failed in "${FAILED_ACTIONS[@]}"; do
    echo "  - $failed"
  done
  exit 1
fi
echo "All action folders completed successfully."
