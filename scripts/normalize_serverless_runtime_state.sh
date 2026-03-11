#!/usr/bin/env bash
set -euo pipefail

AWS_REGION_EFFECTIVE="eu-north-1"
NAME_PREFIX="security-autopilot-dev"
ENABLE_WORKER="true"
WORKER_RESERVED_CONCURRENCY="0"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/normalize_serverless_runtime_state.sh \
    --region eu-north-1 \
    --name-prefix security-autopilot-dev \
    --enable-worker true \
    --worker-reserved-concurrency 10

Normalizes out-of-band Lambda drift after stop/redeploy flows:
- clears reserved concurrency from the API Lambda
- clears reserved concurrency from ReadRole/WriteRole helper Lambdas
- applies the requested worker reserved concurrency
- enables/disables worker event source mappings to match EnableWorker
EOF
}

lambda_exists() {
  aws lambda get-function \
    --region "$AWS_REGION_EFFECTIVE" \
    --function-name "$1" >/dev/null 2>&1
}

current_reserved_concurrency() {
  aws lambda get-function-concurrency \
    --region "$AWS_REGION_EFFECTIVE" \
    --function-name "$1" \
    --query "ReservedConcurrentExecutions" \
    --output text 2>/dev/null || true
}

clear_reserved_concurrency() {
  local function_name="$1"
  local current
  if ! lambda_exists "$function_name"; then
    echo "skip missing function: ${function_name}"
    return 0
  fi
  current="$(current_reserved_concurrency "$function_name")"
  if [[ -z "$current" || "$current" == "None" ]]; then
    echo "reserved concurrency already clear: ${function_name}"
    return 0
  fi
  echo "clearing reserved concurrency: ${function_name} (${current})"
  aws lambda delete-function-concurrency \
    --region "$AWS_REGION_EFFECTIVE" \
    --function-name "$function_name" >/dev/null
}

set_reserved_concurrency() {
  local function_name="$1"
  local desired="$2"
  local current
  if ! lambda_exists "$function_name"; then
    echo "skip missing function: ${function_name}"
    return 0
  fi
  current="$(current_reserved_concurrency "$function_name")"
  if [[ "$current" == "$desired" ]]; then
    echo "reserved concurrency already ${desired}: ${function_name}"
    return 0
  fi
  echo "setting reserved concurrency: ${function_name} -> ${desired}"
  aws lambda put-function-concurrency \
    --region "$AWS_REGION_EFFECTIVE" \
    --function-name "$function_name" \
    --reserved-concurrent-executions "$desired" >/dev/null
}

sync_worker_mappings() {
  local should_enable="$1"
  local mapping_ids
  mapping_ids="$(
    aws lambda list-event-source-mappings \
      --region "$AWS_REGION_EFFECTIVE" \
      --function-name "${NAME_PREFIX}-worker" \
      --query "EventSourceMappings[].UUID" \
      --output text 2>/dev/null || true
  )"
  if [[ -z "$mapping_ids" || "$mapping_ids" == "None" ]]; then
    echo "no worker event source mappings found"
    return 0
  fi
  for mapping_id in $mapping_ids; do
    local state
    state="$(
      aws lambda get-event-source-mapping \
        --region "$AWS_REGION_EFFECTIVE" \
        --uuid "$mapping_id" \
        --query "State" \
        --output text
    )"
    if [[ "$should_enable" == "true" ]]; then
      if [[ "$state" == "Enabled" || "$state" == "Enabling" ]]; then
        echo "worker mapping already enabled: ${mapping_id}"
        continue
      fi
      echo "enabling worker mapping: ${mapping_id}"
      aws lambda update-event-source-mapping \
        --region "$AWS_REGION_EFFECTIVE" \
        --uuid "$mapping_id" \
        --enabled >/dev/null
      continue
    fi
    if [[ "$state" == "Disabled" || "$state" == "Disabling" ]]; then
      echo "worker mapping already disabled: ${mapping_id}"
      continue
    fi
    echo "disabling worker mapping: ${mapping_id}"
    aws lambda update-event-source-mapping \
      --region "$AWS_REGION_EFFECTIVE" \
      --uuid "$mapping_id" \
      --no-enabled >/dev/null
  done
}

helper_functions() {
  aws lambda list-functions \
    --region "$AWS_REGION_EFFECTIVE" \
    --query "Functions[?contains(FunctionName, 'ReadRoleHelperFunction') || contains(FunctionName, 'WriteRoleHelperFunction')].FunctionName" \
    --output text 2>/dev/null || true
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      AWS_REGION_EFFECTIVE="$2"; shift 2 ;;
    --name-prefix)
      NAME_PREFIX="$2"; shift 2 ;;
    --enable-worker)
      ENABLE_WORKER="$2"; shift 2 ;;
    --worker-reserved-concurrency)
      WORKER_RESERVED_CONCURRENCY="$2"; shift 2 ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$ENABLE_WORKER" != "true" && "$ENABLE_WORKER" != "false" ]]; then
  echo "Expected --enable-worker true|false, got: ${ENABLE_WORKER}" >&2
  exit 2
fi

if ! [[ "$WORKER_RESERVED_CONCURRENCY" =~ ^[0-9]+$ ]]; then
  echo "Expected non-negative integer --worker-reserved-concurrency, got: ${WORKER_RESERVED_CONCURRENCY}" >&2
  exit 2
fi

echo "Region: ${AWS_REGION_EFFECTIVE}"
echo "Name prefix: ${NAME_PREFIX}"
echo "Enable worker: ${ENABLE_WORKER}"
echo "Worker reserved concurrency: ${WORKER_RESERVED_CONCURRENCY}"

clear_reserved_concurrency "${NAME_PREFIX}-api"

if [[ "$ENABLE_WORKER" == "true" ]]; then
  if [[ "$WORKER_RESERVED_CONCURRENCY" == "0" ]]; then
    clear_reserved_concurrency "${NAME_PREFIX}-worker"
  else
    set_reserved_concurrency "${NAME_PREFIX}-worker" "${WORKER_RESERVED_CONCURRENCY}"
  fi
  sync_worker_mappings "true"
else
  set_reserved_concurrency "${NAME_PREFIX}-worker" "0"
  sync_worker_mappings "false"
fi

for function_name in $(helper_functions); do
  clear_reserved_concurrency "$function_name"
done
