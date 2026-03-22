#!/usr/bin/env bash
set -euo pipefail

export AWS_PAGER=""

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${SAAS_ENV_FILE:-config/.env.ops}"
BACKUP_ROOT="${SAAS_LIFECYCLE_BACKUP_ROOT:-backups/runtime-control}"

read_env_file_value() {
  local key="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    return 0
  fi
  local line
  line="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    return 0
  fi
  line="${line#*=}"
  line="${line%\"}"
  line="${line#\"}"
  line="${line%\'}"
  line="${line#\'}"
  printf '%s' "$line"
}

AWS_REGION_EFFECTIVE="${AWS_REGION:-$(read_env_file_value AWS_REGION || true)}"
AWS_REGION_EFFECTIVE="${AWS_REGION_EFFECTIVE:-eu-north-1}"
BUILD_STACK_NAME="${SAAS_SERVERLESS_BUILD_STACK_NAME:-security-autopilot-saas-serverless-build}"
RUNTIME_STACK_NAME="${SAAS_SERVERLESS_RUNTIME_STACK_NAME:-security-autopilot-saas-serverless-runtime}"
SQS_STACK_NAME="${SQS_STACK_NAME:-security-autopilot-sqs-queues}"
NAME_PREFIX="${SAAS_SERVERLESS_NAME_PREFIX:-security-autopilot-dev}"
DB_INSTANCE_ID="${SAAS_DB_INSTANCE_ID:-security-autopilot-db-main}"
EXPORT_BUCKET_NAME="${S3_EXPORT_BUCKET:-$(read_env_file_value S3_EXPORT_BUCKET || true)}"
SUPPORT_BUCKET_NAME="${S3_SUPPORT_BUCKET:-$(read_env_file_value S3_SUPPORT_BUCKET || true)}"

ACTION="${1:-}"
if [[ $# -gt 0 ]]; then
  shift
fi

DRY_RUN="false"
FORCE="false"
BUNDLE_ID=""
REGION_EXPLICIT="false"

API_FUNCTION_NAME=""
WORKER_FUNCTION_NAME=""
API_IMAGE_URI=""
WORKER_IMAGE_URI=""
API_IMAGE_TAG=""
WORKER_IMAGE_TAG=""
API_BASE_URL=""
DB_SNAPSHOT_ID=""
WORKER_ENABLED_BEFORE="true"
WORKER_RESERVED_CONCURRENCY_BEFORE="0"

RUNTIME_PARAMETERS_FILE=""
RUNTIME_OUTPUTS_FILE=""
BUILD_OUTPUTS_FILE=""
DB_INSTANCE_FILE=""
CLOUDTRAIL_FILE=""
CONFIG_FILE=""
GUARDDUTY_FILE=""
EVENTBRIDGE_FILE=""
SECURITYHUB_HUB_FILE=""
SECURITYHUB_STANDARDS_FILE=""
API_IMAGE_ARCHIVE=""
WORKER_IMAGE_ARCHIVE=""
MANIFEST_ENV_FILE=""
MANIFEST_JSON_FILE=""

usage() {
  cat <<'EOF'
Usage:
  ./scripts/serverless_lifecycle.sh <status|pause|delete|redeploy|enable> [options]

Options:
  --region <region>              AWS region (default: env/.env.ops or eu-north-1)
  --build-stack <name>           Serverless build stack
  --runtime-stack <name>         Serverless runtime stack
  --sqs-stack <name>             SQS stack
  --name-prefix <prefix>         Lambda/resource name prefix
  --db-instance-id <identifier>  RDS instance identifier
  --env-file <path>              Env file with secrets/config (default: config/.env.ops)
  --backup-dir <path>            Local backup root (default: backups/runtime-control)
  --bundle <id>                  Existing backup bundle id for redeploy/enable
  --dry-run                      Print commands without executing them
  --force                        Required for delete
  --help                         Show this help
EOF
}

if [[ "$ACTION" == "--help" || "$ACTION" == "-h" ]]; then
  usage
  exit 0
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      AWS_REGION_EFFECTIVE="$2"; REGION_EXPLICIT="true"; shift 2 ;;
    --build-stack)
      BUILD_STACK_NAME="$2"; shift 2 ;;
    --runtime-stack)
      RUNTIME_STACK_NAME="$2"; shift 2 ;;
    --sqs-stack)
      SQS_STACK_NAME="$2"; shift 2 ;;
    --name-prefix)
      NAME_PREFIX="$2"; shift 2 ;;
    --db-instance-id)
      DB_INSTANCE_ID="$2"; shift 2 ;;
    --env-file)
      ENV_FILE="$2"; shift 2 ;;
    --backup-dir)
      BACKUP_ROOT="$2"; shift 2 ;;
    --bundle)
      BUNDLE_ID="$2"; shift 2 ;;
    --dry-run)
      DRY_RUN="true"; shift ;;
    --force)
      FORCE="true"; shift ;;
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

if [[ -z "$ACTION" ]]; then
  usage >&2
  exit 2
fi

if [[ "$REGION_EXPLICIT" != "true" && -z "${AWS_REGION:-}" ]]; then
  AWS_REGION_EFFECTIVE="$(read_env_file_value AWS_REGION || true)"
  AWS_REGION_EFFECTIVE="${AWS_REGION_EFFECTIVE:-eu-north-1}"
fi
EXPORT_BUCKET_NAME="${S3_EXPORT_BUCKET:-$(read_env_file_value S3_EXPORT_BUCKET || true)}"
SUPPORT_BUCKET_NAME="${S3_SUPPORT_BUCKET:-$(read_env_file_value S3_SUPPORT_BUCKET || true)}"

API_FUNCTION_NAME="${NAME_PREFIX}-api"
WORKER_FUNCTION_NAME="${NAME_PREFIX}-worker"

KNOWN_EVENTBRIDGE_RULES=(
  "SecurityAutopilotControlPlaneApiCallsRule-${AWS_REGION_EFFECTIVE}"
  "SecurityAutopilotReconcileGlobalAllTenants-${AWS_REGION_EFFECTIVE}"
  "creating-events-in-cloudwatch"
)

log() {
  printf '%s\n' "$*"
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

run() {
  if [[ "$DRY_RUN" == "true" ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

stack_exists() {
  aws cloudformation describe-stacks \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$1" >/dev/null 2>&1
}

db_instance_exists() {
  aws rds describe-db-instances \
    --region "$AWS_REGION_EFFECTIVE" \
    --db-instance-identifier "$DB_INSTANCE_ID" >/dev/null 2>&1
}

lambda_exists() {
  aws lambda get-function \
    --region "$AWS_REGION_EFFECTIVE" \
    --function-name "$1" >/dev/null 2>&1
}

bundle_dir_from_id() {
  printf '%s/%s' "$BACKUP_ROOT" "$1"
}

latest_bundle_id() {
  if [[ ! -d "$BACKUP_ROOT" ]]; then
    return 0
  fi
  find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -print 2>/dev/null | sort | tail -n 1 | xargs -n 1 basename 2>/dev/null || true
}

set_bundle_paths() {
  local id="$1"
  local dir
  dir="$(bundle_dir_from_id "$id")"
  RUNTIME_PARAMETERS_FILE="${dir}/runtime-parameters.json"
  RUNTIME_OUTPUTS_FILE="${dir}/runtime-outputs.json"
  BUILD_OUTPUTS_FILE="${dir}/build-outputs.json"
  DB_INSTANCE_FILE="${dir}/db-instance.json"
  CLOUDTRAIL_FILE="${dir}/cloudtrail.tsv"
  CONFIG_FILE="${dir}/config-recorders.tsv"
  GUARDDUTY_FILE="${dir}/guardduty.tsv"
  EVENTBRIDGE_FILE="${dir}/eventbridge.tsv"
  SECURITYHUB_HUB_FILE="${dir}/securityhub-hub.json"
  SECURITYHUB_STANDARDS_FILE="${dir}/securityhub-standards.json"
  API_IMAGE_ARCHIVE="${dir}/images/api-image.tar"
  WORKER_IMAGE_ARCHIVE="${dir}/images/worker-image.tar"
  MANIFEST_ENV_FILE="${dir}/manifest.env"
  MANIFEST_JSON_FILE="${dir}/manifest.json"
}

prepare_new_bundle() {
  if [[ -z "$BUNDLE_ID" ]]; then
    BUNDLE_ID="$(date -u +%Y%m%dT%H%M%SZ)"
  fi
  set_bundle_paths "$BUNDLE_ID"
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$API_IMAGE_ARCHIVE")"
}

resolve_existing_bundle() {
  if [[ -z "$BUNDLE_ID" ]]; then
    BUNDLE_ID="$(latest_bundle_id)"
  fi
  [[ -n "$BUNDLE_ID" ]] || fail "No backup bundle found. Pass --bundle or create one with pause/delete."
  set_bundle_paths "$BUNDLE_ID"
  [[ -f "$MANIFEST_ENV_FILE" ]] || fail "Bundle missing manifest: ${MANIFEST_ENV_FILE}"
}

load_bundle() {
  resolve_existing_bundle
  # shellcheck disable=SC1090
  source "$MANIFEST_ENV_FILE"
}

json_value_from_file() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

path, key = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)
if data in (None, [], {}):
    raise SystemExit(0)
for item in data:
    if item.get("ParameterKey") == key:
        print(item.get("ParameterValue", ""))
        raise SystemExit(0)
    if item.get("OutputKey") == key:
        print(item.get("OutputValue", ""))
        raise SystemExit(0)
PY
}

db_restore_fields() {
  python3 - "$DB_INSTANCE_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)
if not data:
    raise SystemExit(1)
sg_ids = ",".join(item["VpcSecurityGroupId"] for item in data.get("VpcSecurityGroups", []))
values = [
    data.get("DBInstanceClass", ""),
    data.get("DBSubnetGroup", {}).get("DBSubnetGroupName", ""),
    str(bool(data.get("PubliclyAccessible", False))).lower(),
    str(bool(data.get("MultiAZ", False))).lower(),
    sg_ids,
]
print("\t".join(values))
PY
}

rewrite_database_url_host() {
  python3 - "$1" "$2" "$3" <<'PY'
import sys
from urllib.parse import urlsplit, urlunsplit

original, host, port = sys.argv[1], sys.argv[2], sys.argv[3]
parts = urlsplit(original)
if "@" not in parts.netloc:
    raise SystemExit("DATABASE_URL is missing credentials/host information.")
auth, _ = parts.netloc.rsplit("@", 1)
port_suffix = f":{port}" if port and port != "None" else ""
netloc = f"{auth}@{host}{port_suffix}"
print(urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment)))
PY
}

runtime_params_override_lines() {
  python3 - "$RUNTIME_PARAMETERS_FILE" "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9" <<'PY'
import json
import sys

(
    path,
    api_image,
    worker_image,
    database_url,
    jwt_secret,
    bundle_reporting_secret,
    cp_secret,
    enable_worker,
    worker_reserved_concurrency,
    sqs_stack_name,
) = sys.argv[1:]

with open(path, "r", encoding="utf-8") as handle:
    items = json.load(handle)

overrides = {
    "ApiImageUri": api_image,
    "WorkerImageUri": worker_image,
    "DatabaseUrl": database_url,
    "JwtSecret": jwt_secret,
    "BundleReportingTokenSecret": bundle_reporting_secret,
    "ControlPlaneEventsSecret": cp_secret,
    "EnableWorker": enable_worker,
    "WorkerReservedConcurrency": worker_reserved_concurrency,
    "SqsStackName": sqs_stack_name,
}

for item in items:
    key = item["ParameterKey"]
    value = overrides.get(key, item.get("ParameterValue", ""))
    print(f"{key}={value}")
PY
}

write_manifest_files() {
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi
  {
    printf 'BUNDLE_ID=%q\n' "$BUNDLE_ID"
    printf 'AWS_REGION_EFFECTIVE=%q\n' "$AWS_REGION_EFFECTIVE"
    printf 'BUILD_STACK_NAME=%q\n' "$BUILD_STACK_NAME"
    printf 'RUNTIME_STACK_NAME=%q\n' "$RUNTIME_STACK_NAME"
    printf 'SQS_STACK_NAME=%q\n' "$SQS_STACK_NAME"
    printf 'NAME_PREFIX=%q\n' "$NAME_PREFIX"
    printf 'DB_INSTANCE_ID=%q\n' "$DB_INSTANCE_ID"
    printf 'DB_SNAPSHOT_ID=%q\n' "$DB_SNAPSHOT_ID"
    printf 'API_FUNCTION_NAME=%q\n' "$API_FUNCTION_NAME"
    printf 'WORKER_FUNCTION_NAME=%q\n' "$WORKER_FUNCTION_NAME"
    printf 'API_IMAGE_URI=%q\n' "$API_IMAGE_URI"
    printf 'WORKER_IMAGE_URI=%q\n' "$WORKER_IMAGE_URI"
    printf 'API_IMAGE_TAG=%q\n' "$API_IMAGE_TAG"
    printf 'WORKER_IMAGE_TAG=%q\n' "$WORKER_IMAGE_TAG"
    printf 'API_BASE_URL=%q\n' "$API_BASE_URL"
    printf 'WORKER_ENABLED_BEFORE=%q\n' "$WORKER_ENABLED_BEFORE"
    printf 'WORKER_RESERVED_CONCURRENCY_BEFORE=%q\n' "$WORKER_RESERVED_CONCURRENCY_BEFORE"
    printf 'RUNTIME_PARAMETERS_FILE=%q\n' "$RUNTIME_PARAMETERS_FILE"
    printf 'RUNTIME_OUTPUTS_FILE=%q\n' "$RUNTIME_OUTPUTS_FILE"
    printf 'BUILD_OUTPUTS_FILE=%q\n' "$BUILD_OUTPUTS_FILE"
    printf 'DB_INSTANCE_FILE=%q\n' "$DB_INSTANCE_FILE"
    printf 'CLOUDTRAIL_FILE=%q\n' "$CLOUDTRAIL_FILE"
    printf 'CONFIG_FILE=%q\n' "$CONFIG_FILE"
    printf 'GUARDDUTY_FILE=%q\n' "$GUARDDUTY_FILE"
    printf 'EVENTBRIDGE_FILE=%q\n' "$EVENTBRIDGE_FILE"
    printf 'SECURITYHUB_HUB_FILE=%q\n' "$SECURITYHUB_HUB_FILE"
    printf 'SECURITYHUB_STANDARDS_FILE=%q\n' "$SECURITYHUB_STANDARDS_FILE"
    printf 'API_IMAGE_ARCHIVE=%q\n' "$API_IMAGE_ARCHIVE"
    printf 'WORKER_IMAGE_ARCHIVE=%q\n' "$WORKER_IMAGE_ARCHIVE"
    printf 'EXPORT_BUCKET_NAME=%q\n' "$EXPORT_BUCKET_NAME"
    printf 'SUPPORT_BUCKET_NAME=%q\n' "$SUPPORT_BUCKET_NAME"
  } > "$MANIFEST_ENV_FILE"

  BUNDLE_ID="$BUNDLE_ID" \
  AWS_REGION_EFFECTIVE="$AWS_REGION_EFFECTIVE" \
  BUILD_STACK_NAME="$BUILD_STACK_NAME" \
  RUNTIME_STACK_NAME="$RUNTIME_STACK_NAME" \
  SQS_STACK_NAME="$SQS_STACK_NAME" \
  NAME_PREFIX="$NAME_PREFIX" \
  DB_INSTANCE_ID="$DB_INSTANCE_ID" \
  DB_SNAPSHOT_ID="$DB_SNAPSHOT_ID" \
  API_FUNCTION_NAME="$API_FUNCTION_NAME" \
  WORKER_FUNCTION_NAME="$WORKER_FUNCTION_NAME" \
  API_IMAGE_URI="$API_IMAGE_URI" \
  WORKER_IMAGE_URI="$WORKER_IMAGE_URI" \
  API_IMAGE_TAG="$API_IMAGE_TAG" \
  WORKER_IMAGE_TAG="$WORKER_IMAGE_TAG" \
  API_BASE_URL="$API_BASE_URL" \
  WORKER_ENABLED_BEFORE="$WORKER_ENABLED_BEFORE" \
  WORKER_RESERVED_CONCURRENCY_BEFORE="$WORKER_RESERVED_CONCURRENCY_BEFORE" \
  RUNTIME_PARAMETERS_FILE="$RUNTIME_PARAMETERS_FILE" \
  RUNTIME_OUTPUTS_FILE="$RUNTIME_OUTPUTS_FILE" \
  BUILD_OUTPUTS_FILE="$BUILD_OUTPUTS_FILE" \
  DB_INSTANCE_FILE="$DB_INSTANCE_FILE" \
  CLOUDTRAIL_FILE="$CLOUDTRAIL_FILE" \
  CONFIG_FILE="$CONFIG_FILE" \
  GUARDDUTY_FILE="$GUARDDUTY_FILE" \
  EVENTBRIDGE_FILE="$EVENTBRIDGE_FILE" \
  SECURITYHUB_HUB_FILE="$SECURITYHUB_HUB_FILE" \
  SECURITYHUB_STANDARDS_FILE="$SECURITYHUB_STANDARDS_FILE" \
  API_IMAGE_ARCHIVE="$API_IMAGE_ARCHIVE" \
  WORKER_IMAGE_ARCHIVE="$WORKER_IMAGE_ARCHIVE" \
  EXPORT_BUCKET_NAME="$EXPORT_BUCKET_NAME" \
  SUPPORT_BUCKET_NAME="$SUPPORT_BUCKET_NAME" \
  MANIFEST_JSON_FILE="$MANIFEST_JSON_FILE" \
  python3 - <<'PY'
import json
import os

keys = [
    "BUNDLE_ID",
    "AWS_REGION_EFFECTIVE",
    "BUILD_STACK_NAME",
    "RUNTIME_STACK_NAME",
    "SQS_STACK_NAME",
    "NAME_PREFIX",
    "DB_INSTANCE_ID",
    "DB_SNAPSHOT_ID",
    "API_FUNCTION_NAME",
    "WORKER_FUNCTION_NAME",
    "API_IMAGE_URI",
    "WORKER_IMAGE_URI",
    "API_IMAGE_TAG",
    "WORKER_IMAGE_TAG",
    "API_BASE_URL",
    "WORKER_ENABLED_BEFORE",
    "WORKER_RESERVED_CONCURRENCY_BEFORE",
    "RUNTIME_PARAMETERS_FILE",
    "RUNTIME_OUTPUTS_FILE",
    "BUILD_OUTPUTS_FILE",
    "DB_INSTANCE_FILE",
    "CLOUDTRAIL_FILE",
    "CONFIG_FILE",
    "GUARDDUTY_FILE",
    "EVENTBRIDGE_FILE",
    "SECURITYHUB_HUB_FILE",
    "SECURITYHUB_STANDARDS_FILE",
    "API_IMAGE_ARCHIVE",
    "WORKER_IMAGE_ARCHIVE",
    "EXPORT_BUCKET_NAME",
    "SUPPORT_BUCKET_NAME",
]
payload = {key: os.environ.get(key, "") for key in keys}
with open(os.environ["MANIFEST_JSON_FILE"], "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
PY
}

capture_runtime_stack_state() {
  if [[ "$DRY_RUN" == "true" ]]; then
    API_IMAGE_URI="dry-run/api:latest"
    WORKER_IMAGE_URI="dry-run/worker:latest"
    API_IMAGE_TAG="latest"
    WORKER_IMAGE_TAG="latest"
    API_BASE_URL="https://dry-run.invalid"
    WORKER_ENABLED_BEFORE="true"
    WORKER_RESERVED_CONCURRENCY_BEFORE="0"
    return 0
  fi
  if ! stack_exists "$RUNTIME_STACK_NAME"; then
    printf '[]\n' > "$RUNTIME_PARAMETERS_FILE"
    printf '[]\n' > "$RUNTIME_OUTPUTS_FILE"
    return 0
  fi
  aws cloudformation describe-stacks \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$RUNTIME_STACK_NAME" \
    --query "Stacks[0].Parameters" \
    --output json > "$RUNTIME_PARAMETERS_FILE"
  aws cloudformation describe-stacks \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$RUNTIME_STACK_NAME" \
    --query "Stacks[0].Outputs" \
    --output json > "$RUNTIME_OUTPUTS_FILE"
  API_IMAGE_URI="$(json_value_from_file "$RUNTIME_PARAMETERS_FILE" "ApiImageUri")"
  WORKER_IMAGE_URI="$(json_value_from_file "$RUNTIME_PARAMETERS_FILE" "WorkerImageUri")"
  API_IMAGE_TAG="${API_IMAGE_URI##*:}"
  WORKER_IMAGE_TAG="${WORKER_IMAGE_URI##*:}"
  API_BASE_URL="$(json_value_from_file "$RUNTIME_OUTPUTS_FILE" "ApiBaseUrl")"
  WORKER_ENABLED_BEFORE="$(json_value_from_file "$RUNTIME_PARAMETERS_FILE" "EnableWorker")"
  WORKER_RESERVED_CONCURRENCY_BEFORE="$(json_value_from_file "$RUNTIME_PARAMETERS_FILE" "WorkerReservedConcurrency")"
}

capture_build_stack_state() {
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi
  if ! stack_exists "$BUILD_STACK_NAME"; then
    printf '[]\n' > "$BUILD_OUTPUTS_FILE"
    return 0
  fi
  aws cloudformation describe-stacks \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$BUILD_STACK_NAME" \
    --query "Stacks[0].Outputs" \
    --output json > "$BUILD_OUTPUTS_FILE"
}

capture_db_state() {
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi
  if ! db_instance_exists; then
    printf 'null\n' > "$DB_INSTANCE_FILE"
    return 0
  fi
  aws rds describe-db-instances \
    --region "$AWS_REGION_EFFECTIVE" \
    --db-instance-identifier "$DB_INSTANCE_ID" \
    --query "DBInstances[0]" \
    --output json > "$DB_INSTANCE_FILE"
}

capture_cloudtrail_state() {
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi
  : > "$CLOUDTRAIL_FILE"
  local trails
  trails="$(aws cloudtrail describe-trails --region "$AWS_REGION_EFFECTIVE" --include-shadow-trails --query "trailList[].Name" --output text 2>/dev/null || true)"
  for trail in $trails; do
    local is_logging
    is_logging="$(aws cloudtrail get-trail-status --region "$AWS_REGION_EFFECTIVE" --name "$trail" --query "IsLogging" --output text 2>/dev/null || true)"
    printf '%s\t%s\n' "$trail" "$is_logging" >> "$CLOUDTRAIL_FILE"
  done
}

capture_config_state() {
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi
  aws configservice describe-configuration-recorders-status \
    --region "$AWS_REGION_EFFECTIVE" \
    --query "ConfigurationRecordersStatus[].[name,recording]" \
    --output text 2>/dev/null > "$CONFIG_FILE" || : > "$CONFIG_FILE"
}

capture_guardduty_state() {
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi
  : > "$GUARDDUTY_FILE"
  local detectors
  detectors="$(aws guardduty list-detectors --region "$AWS_REGION_EFFECTIVE" --query "DetectorIds[]" --output text 2>/dev/null || true)"
  for detector in $detectors; do
    local status
    status="$(aws guardduty get-detector --region "$AWS_REGION_EFFECTIVE" --detector-id "$detector" --query "Status" --output text 2>/dev/null || true)"
    printf '%s\t%s\n' "$detector" "$status" >> "$GUARDDUTY_FILE"
  done
}

capture_eventbridge_state() {
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi
  : > "$EVENTBRIDGE_FILE"
  local rule_name
  for rule_name in "${KNOWN_EVENTBRIDGE_RULES[@]}"; do
    if aws events describe-rule --region "$AWS_REGION_EFFECTIVE" --name "$rule_name" >/dev/null 2>&1; then
      local state
      state="$(aws events describe-rule --region "$AWS_REGION_EFFECTIVE" --name "$rule_name" --query "State" --output text)"
      printf '%s\t%s\n' "$rule_name" "$state" >> "$EVENTBRIDGE_FILE"
    fi
  done
}

capture_securityhub_state() {
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi
  if aws securityhub describe-hub --region "$AWS_REGION_EFFECTIVE" >/dev/null 2>&1; then
    aws securityhub describe-hub --region "$AWS_REGION_EFFECTIVE" --output json > "$SECURITYHUB_HUB_FILE"
    aws securityhub get-enabled-standards \
      --region "$AWS_REGION_EFFECTIVE" \
      --query "StandardsSubscriptions[].{StandardsArn:StandardsArn,StandardsInput:StandardsInput}" \
      --output json > "$SECURITYHUB_STANDARDS_FILE"
    return 0
  fi
  printf 'null\n' > "$SECURITYHUB_HUB_FILE"
  printf '[]\n' > "$SECURITYHUB_STANDARDS_FILE"
}

capture_bundle_state() {
  prepare_new_bundle
  capture_runtime_stack_state
  capture_build_stack_state
  capture_db_state
  capture_cloudtrail_state
  capture_config_state
  capture_guardduty_state
  capture_eventbridge_state
  capture_securityhub_state
  write_manifest_files
}

lambda_reserved_concurrency() {
  aws lambda get-function-concurrency \
    --region "$AWS_REGION_EFFECTIVE" \
    --function-name "$1" \
    --query "ReservedConcurrentExecutions" \
    --output text 2>/dev/null || true
}

set_api_reserved_concurrency_zero() {
  if ! lambda_exists "$API_FUNCTION_NAME"; then
    return 0
  fi
  run aws lambda put-function-concurrency \
    --region "$AWS_REGION_EFFECTIVE" \
    --function-name "$API_FUNCTION_NAME" \
    --reserved-concurrent-executions 0
}

clear_api_reserved_concurrency() {
  if ! lambda_exists "$API_FUNCTION_NAME"; then
    return 0
  fi
  local current
  current="$(lambda_reserved_concurrency "$API_FUNCTION_NAME")"
  if [[ -z "$current" || "$current" == "None" ]]; then
    return 0
  fi
  run aws lambda delete-function-concurrency \
    --region "$AWS_REGION_EFFECTIVE" \
    --function-name "$API_FUNCTION_NAME"
}

disable_cloudtrail_from_file() {
  [[ -f "$CLOUDTRAIL_FILE" ]] || return 0
  while IFS=$'\t' read -r trail_name was_logging; do
    [[ -n "$trail_name" ]] || continue
    if [[ "$was_logging" == "True" || "$was_logging" == "true" ]]; then
      run aws cloudtrail stop-logging --region "$AWS_REGION_EFFECTIVE" --name "$trail_name"
    fi
  done < "$CLOUDTRAIL_FILE"
}

enable_cloudtrail_from_file() {
  [[ -f "$CLOUDTRAIL_FILE" ]] || return 0
  while IFS=$'\t' read -r trail_name was_logging; do
    [[ -n "$trail_name" ]] || continue
    if [[ "$was_logging" == "True" || "$was_logging" == "true" ]]; then
      run aws cloudtrail start-logging --region "$AWS_REGION_EFFECTIVE" --name "$trail_name"
    fi
  done < "$CLOUDTRAIL_FILE"
}

disable_config_from_file() {
  [[ -f "$CONFIG_FILE" ]] || return 0
  while IFS=$'\t' read -r recorder_name is_recording; do
    [[ -n "$recorder_name" ]] || continue
    if [[ "$is_recording" == "True" || "$is_recording" == "true" ]]; then
      run aws configservice stop-configuration-recorder \
        --region "$AWS_REGION_EFFECTIVE" \
        --configuration-recorder-name "$recorder_name"
    fi
  done < "$CONFIG_FILE"
}

enable_config_from_file() {
  [[ -f "$CONFIG_FILE" ]] || return 0
  while IFS=$'\t' read -r recorder_name was_recording; do
    [[ -n "$recorder_name" ]] || continue
    if [[ "$was_recording" == "True" || "$was_recording" == "true" ]]; then
      run aws configservice start-configuration-recorder \
        --region "$AWS_REGION_EFFECTIVE" \
        --configuration-recorder-name "$recorder_name"
    fi
  done < "$CONFIG_FILE"
}

disable_guardduty_from_file() {
  [[ -f "$GUARDDUTY_FILE" ]] || return 0
  while IFS=$'\t' read -r detector_id status; do
    [[ -n "$detector_id" ]] || continue
    if [[ "$status" == "ENABLED" ]]; then
      run aws guardduty update-detector \
        --region "$AWS_REGION_EFFECTIVE" \
        --detector-id "$detector_id" \
        --no-enable
    fi
  done < "$GUARDDUTY_FILE"
}

enable_guardduty_from_file() {
  [[ -f "$GUARDDUTY_FILE" ]] || return 0
  while IFS=$'\t' read -r detector_id status; do
    [[ -n "$detector_id" ]] || continue
    if [[ "$status" == "ENABLED" ]]; then
      run aws guardduty update-detector \
        --region "$AWS_REGION_EFFECTIVE" \
        --detector-id "$detector_id" \
        --enable
    fi
  done < "$GUARDDUTY_FILE"
}

disable_eventbridge_from_file() {
  [[ -f "$EVENTBRIDGE_FILE" ]] || return 0
  while IFS=$'\t' read -r rule_name state; do
    [[ -n "$rule_name" ]] || continue
    if [[ "$state" == "ENABLED" ]]; then
      run aws events disable-rule --region "$AWS_REGION_EFFECTIVE" --name "$rule_name"
    fi
  done < "$EVENTBRIDGE_FILE"
}

enable_eventbridge_from_file() {
  [[ -f "$EVENTBRIDGE_FILE" ]] || return 0
  while IFS=$'\t' read -r rule_name state; do
    [[ -n "$rule_name" ]] || continue
    if [[ "$state" == "ENABLED" ]]; then
      run aws events enable-rule --region "$AWS_REGION_EFFECTIVE" --name "$rule_name"
    fi
  done < "$EVENTBRIDGE_FILE"
}

disable_securityhub_from_file() {
  [[ -f "$SECURITYHUB_HUB_FILE" ]] || return 0
  if grep -q '^null$' "$SECURITYHUB_HUB_FILE"; then
    return 0
  fi
  run aws securityhub disable-security-hub --region "$AWS_REGION_EFFECTIVE"
}

enable_securityhub_from_file() {
  [[ -f "$SECURITYHUB_HUB_FILE" ]] || return 0
  if grep -q '^null$' "$SECURITYHUB_HUB_FILE"; then
    return 0
  fi
  local control_finding_generator
  control_finding_generator="$(
    python3 - "$SECURITYHUB_HUB_FILE" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)
print(data.get("ControlFindingGenerator", ""))
PY
  )"
  if [[ -n "$control_finding_generator" ]]; then
    run aws securityhub enable-security-hub \
      --region "$AWS_REGION_EFFECTIVE" \
      --no-enable-default-standards \
      --control-finding-generator "$control_finding_generator"
  else
    run aws securityhub enable-security-hub \
      --region "$AWS_REGION_EFFECTIVE" \
      --no-enable-default-standards
  fi
  if [[ ! -f "$SECURITYHUB_STANDARDS_FILE" ]]; then
    return 0
  fi
  local tmp_request
  tmp_request="$(mktemp "/tmp/securityhub-standards-${BUNDLE_ID}-XXXXXX.json")"
  python3 - "$SECURITYHUB_STANDARDS_FILE" "$tmp_request" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    items = json.load(handle)
payload = [
    {
        "StandardsArn": item["StandardsArn"],
        "StandardsInput": item.get("StandardsInput", {}),
    }
    for item in items
    if item.get("StandardsArn")
]
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(payload, handle)
PY
  if [[ "$DRY_RUN" == "true" ]]; then
    log "+ aws securityhub batch-enable-standards --region ${AWS_REGION_EFFECTIVE} --standards-subscription-requests file://${tmp_request}"
  elif [[ "$(python3 - "$tmp_request" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)
print(len(payload))
PY
)" != "0" ]]; then
    aws securityhub batch-enable-standards \
      --region "$AWS_REGION_EFFECTIVE" \
      --standards-subscription-requests "file://${tmp_request}"
  fi
  rm -f "$tmp_request"
}

normalize_worker_runtime() {
  run ./scripts/normalize_serverless_runtime_state.sh \
    --region "$AWS_REGION_EFFECTIVE" \
    --name-prefix "$NAME_PREFIX" \
    --enable-worker "$1" \
    --worker-reserved-concurrency "$2"
}

suspend_runtime_state() {
  local stop_db="$1"
  normalize_worker_runtime "false" "0"
  set_api_reserved_concurrency_zero
  disable_eventbridge_from_file
  disable_cloudtrail_from_file
  disable_config_from_file
  disable_guardduty_from_file
  disable_securityhub_from_file
  if [[ "$stop_db" != "true" ]]; then
    return 0
  fi
  if db_instance_exists; then
    run aws rds stop-db-instance \
      --region "$AWS_REGION_EFFECTIVE" \
      --db-instance-identifier "$DB_INSTANCE_ID"
    if [[ "$DRY_RUN" != "true" ]]; then
      aws rds wait db-instance-stopped \
        --region "$AWS_REGION_EFFECTIVE" \
        --db-instance-identifier "$DB_INSTANCE_ID"
    fi
  fi
}

empty_bucket() {
  local bucket_name="$1"
  if [[ -z "$bucket_name" ]]; then
    return 0
  fi
  if ! aws s3api head-bucket --bucket "$bucket_name" >/dev/null 2>&1; then
    return 0
  fi
  run aws s3 rm "s3://${bucket_name}" --recursive
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi
  local tmp_delete
  tmp_delete="$(mktemp "/tmp/s3-delete-${bucket_name##*/}-XXXXXX.json")"
  python3 - "$bucket_name" "$tmp_delete" <<'PY'
import json
import subprocess
import sys

bucket, output = sys.argv[1], sys.argv[2]
raw = subprocess.check_output(
    [
        "aws",
        "s3api",
        "list-object-versions",
        "--bucket",
        bucket,
        "--output",
        "json",
    ],
    text=True,
)
payload = json.loads(raw)
items = []
for section in ("Versions", "DeleteMarkers"):
    for entry in payload.get(section, []):
        items.append({"Key": entry["Key"], "VersionId": entry["VersionId"]})
with open(output, "w", encoding="utf-8") as handle:
    json.dump({"Objects": items, "Quiet": True}, handle)
PY
  if [[ "$(python3 - "$tmp_delete" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)
print(len(payload.get("Objects", [])))
PY
)" != "0" ]]; then
    aws s3api delete-objects --bucket "$bucket_name" --delete "file://${tmp_delete}" >/dev/null
  fi
  rm -f "$tmp_delete"
}

build_output_value() {
  json_value_from_file "$BUILD_OUTPUTS_FILE" "$1"
}

ecr_repo_name_from_uri() {
  printf '%s\n' "${1#*/}"
}

clear_ecr_repository() {
  local repo_uri="$1"
  if [[ -z "$repo_uri" ]]; then
    return 0
  fi
  local repo_name image_ids
  repo_name="$(ecr_repo_name_from_uri "$repo_uri")"
  image_ids="$(aws ecr list-images --region "$AWS_REGION_EFFECTIVE" --repository-name "$repo_name" --query "imageIds[]" --output json 2>/dev/null || true)"
  if [[ -z "$image_ids" || "$image_ids" == "[]" ]]; then
    return 0
  fi
  local tmp_ids
  tmp_ids="$(mktemp "/tmp/ecr-images-${repo_name##*/}-XXXXXX.json")"
  printf '%s\n' "$image_ids" > "$tmp_ids"
  if [[ "$DRY_RUN" == "true" ]]; then
    log "+ aws ecr batch-delete-image --region ${AWS_REGION_EFFECTIVE} --repository-name ${repo_name} --image-ids file://${tmp_ids}"
  else
    aws ecr batch-delete-image \
      --region "$AWS_REGION_EFFECTIVE" \
      --repository-name "$repo_name" \
      --image-ids "file://${tmp_ids}" >/dev/null
  fi
  rm -f "$tmp_ids"
}

docker_login_registry() {
  local registry="$1"
  if [[ "$DRY_RUN" == "true" ]]; then
    log "+ aws ecr get-login-password --region ${AWS_REGION_EFFECTIVE} | docker login --username AWS --password-stdin ${registry}"
    return 0
  fi
  aws ecr get-login-password --region "$AWS_REGION_EFFECTIVE" | docker login --username AWS --password-stdin "$registry" >/dev/null
}

export_runtime_images() {
  [[ -n "$API_IMAGE_URI" && -n "$WORKER_IMAGE_URI" ]] || fail "Runtime image URIs are missing from the captured bundle."
  require_cmd docker
  docker_login_registry "${API_IMAGE_URI%%/*}"
  run docker pull "$API_IMAGE_URI"
  run docker pull "$WORKER_IMAGE_URI"
  run docker save -o "$API_IMAGE_ARCHIVE" "$API_IMAGE_URI"
  run docker save -o "$WORKER_IMAGE_ARCHIVE" "$WORKER_IMAGE_URI"
}

restore_runtime_images() {
  require_cmd docker
  [[ -f "$API_IMAGE_ARCHIVE" ]] || fail "Missing API image archive: ${API_IMAGE_ARCHIVE}"
  [[ -f "$WORKER_IMAGE_ARCHIVE" ]] || fail "Missing worker image archive: ${WORKER_IMAGE_ARCHIVE}"
  docker_login_registry "${1%%/*}"
  run docker load -i "$API_IMAGE_ARCHIVE"
  run docker load -i "$WORKER_IMAGE_ARCHIVE"
  if [[ "$API_IMAGE_URI" != "$1" ]]; then
    run docker tag "$API_IMAGE_URI" "$1"
  fi
  if [[ "$WORKER_IMAGE_URI" != "$2" ]]; then
    run docker tag "$WORKER_IMAGE_URI" "$2"
  fi
  run docker push "$1"
  run docker push "$2"
}

deploy_build_stack() {
  run aws cloudformation deploy \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$BUILD_STACK_NAME" \
    --template-file infrastructure/cloudformation/saas-serverless-build.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides "NamePrefix=${NAME_PREFIX}" \
    --no-fail-on-empty-changeset
  if [[ "$DRY_RUN" != "true" ]]; then
    capture_build_stack_state
  fi
}

deploy_sqs_stack() {
  run aws cloudformation deploy \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$SQS_STACK_NAME" \
    --template-file infrastructure/cloudformation/sqs-queues.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset
}

deploy_runtime_from_bundle() {
  local api_image_uri="$1"
  local worker_image_uri="$2"
  local database_url="$3"
  local enable_worker="$4"
  local worker_reserved="$5"
  local jwt_secret bundle_reporting_secret control_secret
  jwt_secret="${JWT_SECRET:-$(read_env_file_value JWT_SECRET || true)}"
  bundle_reporting_secret="${BUNDLE_REPORTING_TOKEN_SECRET:-$(read_env_file_value BUNDLE_REPORTING_TOKEN_SECRET || true)}"
  control_secret="${CONTROL_PLANE_EVENTS_SECRET:-$(read_env_file_value CONTROL_PLANE_EVENTS_SECRET || true)}"
  [[ -n "$jwt_secret" ]] || fail "Missing JWT_SECRET in env or ${ENV_FILE}"
  [[ -n "$bundle_reporting_secret" ]] || fail "Missing BUNDLE_REPORTING_TOKEN_SECRET in env or ${ENV_FILE}"
  [[ -n "$control_secret" ]] || fail "Missing CONTROL_PLANE_EVENTS_SECRET in env or ${ENV_FILE}"
  local params=()
  mapfile -t params < <(
    runtime_params_override_lines \
      "$api_image_uri" \
      "$worker_image_uri" \
      "$database_url" \
      "$jwt_secret" \
      "$bundle_reporting_secret" \
      "$control_secret" \
      "$enable_worker" \
      "$worker_reserved" \
      "$SQS_STACK_NAME"
  )
  run aws cloudformation deploy \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$RUNTIME_STACK_NAME" \
    --template-file infrastructure/cloudformation/saas-serverless-httpapi.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides "${params[@]}" \
    --no-fail-on-empty-changeset
}

delete_stack_if_present() {
  local stack_name="$1"
  if ! stack_exists "$stack_name"; then
    return 0
  fi
  run aws cloudformation delete-stack --region "$AWS_REGION_EFFECTIVE" --stack-name "$stack_name"
  if [[ "$DRY_RUN" != "true" ]]; then
    aws cloudformation wait stack-delete-complete \
      --region "$AWS_REGION_EFFECTIVE" \
      --stack-name "$stack_name"
  fi
}

delete_log_group_if_present() {
  local log_group_name="$1"
  if ! aws logs describe-log-groups \
    --region "$AWS_REGION_EFFECTIVE" \
    --log-group-name-prefix "$log_group_name" \
    --query "logGroups[?logGroupName=='${log_group_name}'].logGroupName" \
    --output text 2>/dev/null | grep -q "$log_group_name"; then
    return 0
  fi
  run aws logs delete-log-group \
    --region "$AWS_REGION_EFFECTIVE" \
    --log-group-name "$log_group_name"
}

create_db_snapshot() {
  local clean_bundle snapshot_suffix
  clean_bundle="$(printf '%s' "$BUNDLE_ID" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-')"
  snapshot_suffix="${clean_bundle#-}"
  DB_SNAPSHOT_ID="${DB_INSTANCE_ID}-lifecycle-${snapshot_suffix}"
  write_manifest_files
  run aws rds create-db-snapshot \
    --region "$AWS_REGION_EFFECTIVE" \
    --db-instance-identifier "$DB_INSTANCE_ID" \
    --db-snapshot-identifier "$DB_SNAPSHOT_ID"
  if [[ "$DRY_RUN" != "true" ]]; then
    aws rds wait db-snapshot-available \
      --region "$AWS_REGION_EFFECTIVE" \
      --db-snapshot-identifier "$DB_SNAPSHOT_ID"
  fi
  write_manifest_files
}

delete_db_instance() {
  if ! db_instance_exists; then
    return 0
  fi
  run aws rds delete-db-instance \
    --region "$AWS_REGION_EFFECTIVE" \
    --db-instance-identifier "$DB_INSTANCE_ID" \
    --skip-final-snapshot \
    --delete-automated-backups
  if [[ "$DRY_RUN" != "true" ]]; then
    aws rds wait db-instance-deleted \
      --region "$AWS_REGION_EFFECTIVE" \
      --db-instance-identifier "$DB_INSTANCE_ID"
  fi
}

ensure_db_available() {
  if ! db_instance_exists; then
    return 0
  fi
  local db_status
  db_status="$(aws rds describe-db-instances --region "$AWS_REGION_EFFECTIVE" --db-instance-identifier "$DB_INSTANCE_ID" --query "DBInstances[0].DBInstanceStatus" --output text)"
  if [[ "$db_status" != "stopped" ]]; then
    return 0
  fi
  run aws rds start-db-instance \
    --region "$AWS_REGION_EFFECTIVE" \
    --db-instance-identifier "$DB_INSTANCE_ID"
  if [[ "$DRY_RUN" != "true" ]]; then
    aws rds wait db-instance-available \
      --region "$AWS_REGION_EFFECTIVE" \
      --db-instance-identifier "$DB_INSTANCE_ID"
  fi
}

restore_db_instance() {
  [[ -f "$DB_INSTANCE_FILE" ]] || fail "Missing DB metadata file: ${DB_INSTANCE_FILE}"
  [[ -n "$DB_SNAPSHOT_ID" ]] || fail "Bundle does not include DB_SNAPSHOT_ID."
  local class_name subnet_group public_flag multi_az_flag sg_ids_raw
  IFS=$'\t' read -r class_name subnet_group public_flag multi_az_flag sg_ids_raw <<< "$(db_restore_fields)"
  local args=(
    --region "$AWS_REGION_EFFECTIVE"
    --db-instance-identifier "$DB_INSTANCE_ID"
    --db-snapshot-identifier "$DB_SNAPSHOT_ID"
    --db-instance-class "$class_name"
  )
  if [[ -n "$subnet_group" && "$subnet_group" != "None" ]]; then
    args+=(--db-subnet-group-name "$subnet_group")
  fi
  if [[ "$public_flag" == "true" ]]; then
    args+=(--publicly-accessible)
  else
    args+=(--no-publicly-accessible)
  fi
  if [[ "$multi_az_flag" == "true" ]]; then
    args+=(--multi-az)
  else
    args+=(--no-multi-az)
  fi
  if [[ -n "$sg_ids_raw" ]]; then
    IFS=',' read -r -a sg_ids <<< "$sg_ids_raw"
    args+=(--vpc-security-group-ids "${sg_ids[@]}")
  fi
  run aws rds restore-db-instance-from-db-snapshot "${args[@]}"
  if [[ "$DRY_RUN" != "true" ]]; then
    aws rds wait db-instance-available \
      --region "$AWS_REGION_EFFECTIVE" \
      --db-instance-identifier "$DB_INSTANCE_ID"
    capture_db_state
  fi
}

restored_database_url() {
  local current_url endpoint address port
  current_url="${DATABASE_URL:-$(read_env_file_value DATABASE_URL || true)}"
  [[ -n "$current_url" ]] || fail "Missing DATABASE_URL in env or ${ENV_FILE}"
  address="$(aws rds describe-db-instances --region "$AWS_REGION_EFFECTIVE" --db-instance-identifier "$DB_INSTANCE_ID" --query "DBInstances[0].Endpoint.Address" --output text)"
  port="$(aws rds describe-db-instances --region "$AWS_REGION_EFFECTIVE" --db-instance-identifier "$DB_INSTANCE_ID" --query "DBInstances[0].Endpoint.Port" --output text)"
  endpoint="${address}"
  rewrite_database_url_host "$current_url" "$endpoint" "$port"
}

api_base_url_for_stack() {
  aws cloudformation describe-stacks \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$RUNTIME_STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" \
    --output text 2>/dev/null || true
}

health_check_runtime() {
  local base_url
  base_url="$(api_base_url_for_stack)"
  if [[ -z "$base_url" || "$base_url" == "None" ]]; then
    return 0
  fi
  if [[ "$DRY_RUN" == "true" ]]; then
    log "+ curl --fail --silent --show-error ${base_url}/health"
    log "+ curl --fail --silent --show-error ${base_url}/ready"
    return 0
  fi
  curl --fail --silent --show-error "${base_url}/health" >/dev/null
  curl --fail --silent --show-error "${base_url}/ready" >/dev/null
}

status_stack_line() {
  local stack_name="$1" label="$2"
  if ! stack_exists "$stack_name"; then
    printf '%s: missing\n' "$label"
    return 0
  fi
  local stack_status
  stack_status="$(aws cloudformation describe-stacks --region "$AWS_REGION_EFFECTIVE" --stack-name "$stack_name" --query "Stacks[0].StackStatus" --output text)"
  printf '%s: %s\n' "$label" "$stack_status"
}

status_lambda_line() {
  local function_name="$1" label="$2"
  if ! lambda_exists "$function_name"; then
    printf '%s: missing\n' "$label"
    return 0
  fi
  local current
  current="$(lambda_reserved_concurrency "$function_name")"
  printf '%s: reserved_concurrency=%s\n' "$label" "${current:-None}"
}

status_db_line() {
  if ! db_instance_exists; then
    printf 'DB: missing\n'
    return 0
  fi
  local db_status
  db_status="$(aws rds describe-db-instances --region "$AWS_REGION_EFFECTIVE" --db-instance-identifier "$DB_INSTANCE_ID" --query "DBInstances[0].DBInstanceStatus" --output text)"
  printf 'DB: %s\n' "$db_status"
}

status_securityhub_line() {
  if aws securityhub describe-hub --region "$AWS_REGION_EFFECTIVE" >/dev/null 2>&1; then
    printf 'SecurityHub: enabled\n'
    return 0
  fi
  printf 'SecurityHub: disabled\n'
}

status_guardduty_line() {
  local detectors
  detectors="$(aws guardduty list-detectors --region "$AWS_REGION_EFFECTIVE" --query "DetectorIds[]" --output text 2>/dev/null || true)"
  if [[ -z "$detectors" ]]; then
    printf 'GuardDuty: no detectors\n'
    return 0
  fi
  local detector status
  detector="$(printf '%s\n' "$detectors" | awk '{print $1}')"
  status="$(aws guardduty get-detector --region "$AWS_REGION_EFFECTIVE" --detector-id "$detector" --query "Status" --output text)"
  printf 'GuardDuty: %s (%s)\n' "$status" "$detector"
}

status_config_line() {
  local summary
  summary="$(aws configservice describe-configuration-recorders-status --region "$AWS_REGION_EFFECTIVE" --query "ConfigurationRecordersStatus[].[name,recording]" --output text 2>/dev/null || true)"
  if [[ -z "$summary" ]]; then
    printf 'Config: no recorders\n'
    return 0
  fi
  printf 'Config: %s\n' "$summary"
}

status_cloudtrail_line() {
  local trails
  trails="$(aws cloudtrail describe-trails --region "$AWS_REGION_EFFECTIVE" --include-shadow-trails --query "trailList[].Name" --output text 2>/dev/null || true)"
  if [[ -z "$trails" ]]; then
    printf 'CloudTrail: no trails\n'
    return 0
  fi
  local trail state_text
  trail="$(printf '%s\n' "$trails" | awk '{print $1}')"
  state_text="$(aws cloudtrail get-trail-status --region "$AWS_REGION_EFFECTIVE" --name "$trail" --query "IsLogging" --output text)"
  printf 'CloudTrail: %s=%s\n' "$trail" "$state_text"
}

status_eventbridge_line() {
  local found="false"
  local rule_name
  for rule_name in "${KNOWN_EVENTBRIDGE_RULES[@]}"; do
    if aws events describe-rule --region "$AWS_REGION_EFFECTIVE" --name "$rule_name" >/dev/null 2>&1; then
      local state
      state="$(aws events describe-rule --region "$AWS_REGION_EFFECTIVE" --name "$rule_name" --query "State" --output text)"
      printf 'EventBridge: %s=%s\n' "$rule_name" "$state"
      found="true"
    fi
  done
  if [[ "$found" == "false" ]]; then
    printf 'EventBridge: no managed rules found\n'
  fi
}

perform_status() {
  status_stack_line "$BUILD_STACK_NAME" "Build stack"
  status_stack_line "$RUNTIME_STACK_NAME" "Runtime stack"
  status_stack_line "$SQS_STACK_NAME" "SQS stack"
  status_lambda_line "$API_FUNCTION_NAME" "API lambda"
  status_lambda_line "$WORKER_FUNCTION_NAME" "Worker lambda"
  status_db_line
  status_securityhub_line
  status_guardduty_line
  status_config_line
  status_cloudtrail_line
  status_eventbridge_line
  printf 'Latest bundle: %s\n' "$(latest_bundle_id || true)"
}

perform_pause() {
  require_cmd aws
  require_cmd python3
  capture_bundle_state
  suspend_runtime_state "true"
  log "Paused runtime with bundle ${BUNDLE_ID}"
}

perform_delete() {
  require_cmd aws
  require_cmd python3
  require_cmd docker
  if [[ "$FORCE" != "true" ]]; then
    fail "Delete requires --force."
  fi
  capture_bundle_state
  suspend_runtime_state "false"
  ensure_db_available
  create_db_snapshot
  export_runtime_images
  empty_bucket "$EXPORT_BUCKET_NAME"
  empty_bucket "$SUPPORT_BUCKET_NAME"
  empty_bucket "$(build_output_value "SourceBucketName")"
  clear_ecr_repository "$(build_output_value "ApiRepositoryUri")"
  clear_ecr_repository "$(build_output_value "WorkerRepositoryUri")"
  delete_stack_if_present "$RUNTIME_STACK_NAME"
  delete_log_group_if_present "/aws/lambda/${API_FUNCTION_NAME}"
  delete_log_group_if_present "/aws/lambda/${WORKER_FUNCTION_NAME}"
  delete_stack_if_present "$SQS_STACK_NAME"
  delete_db_instance
  delete_stack_if_present "$BUILD_STACK_NAME"
  write_manifest_files
  log "Deleted runtime resources with bundle ${BUNDLE_ID}"
}

perform_redeploy() {
  require_cmd aws
  require_cmd python3
  require_cmd docker
  load_bundle
  deploy_build_stack
  local restored_api_repo restored_worker_repo restored_db_url
  restored_api_repo="$(build_output_value "ApiRepositoryUri"):${API_IMAGE_TAG}"
  restored_worker_repo="$(build_output_value "WorkerRepositoryUri"):${WORKER_IMAGE_TAG}"
  restore_runtime_images "$restored_api_repo" "$restored_worker_repo"
  API_IMAGE_URI="$restored_api_repo"
  WORKER_IMAGE_URI="$restored_worker_repo"
  deploy_sqs_stack
  restore_db_instance
  restored_db_url="$(restored_database_url)"
  deploy_runtime_from_bundle "$API_IMAGE_URI" "$WORKER_IMAGE_URI" "$restored_db_url" "false" "0"
  normalize_worker_runtime "false" "0"
  clear_api_reserved_concurrency
  if [[ "$DRY_RUN" != "true" ]]; then
    API_BASE_URL="$(api_base_url_for_stack)"
    write_manifest_files
  fi
  health_check_runtime
  log "Redeployed runtime from bundle ${BUNDLE_ID}"
}

perform_enable() {
  require_cmd aws
  require_cmd python3
  load_bundle
  local current_db_url=""
  if db_instance_exists; then
    ensure_db_available
    current_db_url="$(restored_database_url)"
  fi
  clear_api_reserved_concurrency
  if stack_exists "$RUNTIME_STACK_NAME"; then
    if [[ -n "$current_db_url" ]]; then
      deploy_runtime_from_bundle \
        "$API_IMAGE_URI" \
        "$WORKER_IMAGE_URI" \
        "$current_db_url" \
        "$WORKER_ENABLED_BEFORE" \
        "$WORKER_RESERVED_CONCURRENCY_BEFORE"
    fi
    normalize_worker_runtime "$WORKER_ENABLED_BEFORE" "$WORKER_RESERVED_CONCURRENCY_BEFORE"
  fi
  enable_eventbridge_from_file
  enable_cloudtrail_from_file
  enable_config_from_file
  enable_guardduty_from_file
  enable_securityhub_from_file
  health_check_runtime
  log "Enabled runtime/account services from bundle ${BUNDLE_ID}"
}

case "$ACTION" in
  status)
    perform_status
    ;;
  pause)
    perform_pause
    ;;
  delete)
    perform_delete
    ;;
  redeploy)
    perform_redeploy
    ;;
  enable)
    perform_enable
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
