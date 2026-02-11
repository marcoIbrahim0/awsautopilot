#!/usr/bin/env bash
set -euo pipefail

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is required but not installed."
  exit 1
fi

# Shared Terraform provider cache across bundles.
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

TOTAL=$(find actions -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
if [ "${TOTAL:-0}" -eq 0 ]; then
  TOTAL=1
  ACTION_DIRS=(".")
else
  mapfile -t ACTION_DIRS < <(find actions -mindepth 1 -maxdepth 1 -type d | sort)
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
  duplicate_pattern='InvalidPermission\.Duplicate|already exists|AlreadyExists|EntityAlreadyExists'

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
    resource=$(sed -n 's/.*with \([^,]*\),/\1/p' "$log_file" | head -n 1)
    existing_id=$(grep -Eo 'sg-[0-9A-Za-z-]+' "$log_file" | head -n 1)
    duplicate_line=$(grep -Ei 'InvalidPermission\.Duplicate|already exists|AlreadyExists|EntityAlreadyExists' "$log_file" | head -n 1)
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
COMPLETED_COUNT=0
pids=()
pid_dirs=()
pid_status=()

run_one_bundle() {
  local dir="$1"
  local status_file="$2"

  echo ""
  echo "=== Running terraform in $dir ==="

  if has_unresolved_placeholders "$dir"; then
    echo "ERROR: unresolved placeholders detected for $dir. Skipping this action folder."
    printf "failed|%s (precheck)\n" "$dir" > "$status_file"
    return 0
  fi

  if ! run_terraform_init_with_retry "$dir"; then
    echo "ERROR: terraform init failed for $dir after retries. Skipping this action folder."
    printf "failed|%s (init)\n" "$dir" > "$status_file"
    return 0
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
    printf "failed|%s (plan)\n" "$dir" > "$status_file"
    return 0
  fi

  if ! apply_with_duplicate_tolerance "$dir"; then
    echo "ERROR: terraform apply failed for $dir. Continuing with remaining action folders."
    printf "failed|%s (apply)\n" "$dir" > "$status_file"
    return 0
  fi
  printf "success|%s\n" "$dir" > "$status_file"
  return 0
}

wait_for_one_bundle() {
  local idx pid dir status_file line status detail
  while true; do
    for idx in "${!pids[@]}"; do
      pid="${pids[$idx]}"
      if ! kill -0 "$pid" 2>/dev/null; then
        set +e
        wait "$pid" >/dev/null 2>&1
        set -e
        dir="${pid_dirs[$idx]}"
        status_file="${pid_status[$idx]}"
        line="$(cat "$status_file" 2>/dev/null || true)"
        status="${line%%|*}"
        detail="${line#*|}"
        if [ "$status" = "success" ]; then
          SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
          FAILED_COUNT=$((FAILED_COUNT + 1))
          FAILED_ACTIONS+=("${detail:-$dir (unknown)}")
        fi
        rm -f "$status_file"
        unset 'pids[idx]'
        unset 'pid_dirs[idx]'
        unset 'pid_status[idx]'
        pids=("${pids[@]}")
        pid_dirs=("${pid_dirs[@]}")
        pid_status=("${pid_status[@]}")
        COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
        render_progress "$COMPLETED_COUNT" "(${COMPLETED_COUNT}/${TOTAL}) parallel=${PARALLEL_BUNDLE_EXECUTIONS}"
        return 0
      fi
    done
    sleep 1
  done
}

echo "Running ${TOTAL} bundle folder(s) with parallel executions=${PARALLEL_BUNDLE_EXECUTIONS} (max=${MAX_PARALLEL_BUNDLES})"
for dir in "${ACTION_DIRS[@]}"; do
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
