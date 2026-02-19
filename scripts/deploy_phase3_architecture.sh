#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${PHASE3_ENV_FILE:-config/.env.ops}"

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

DR_STACK_NAME="${DR_STACK_NAME:-security-autopilot-dr-backup-controls}"
PRIMARY_REGION="${SECURITY_AUTOPILOT_PRIMARY_REGION:-eu-north-1}"
ALLOW_CROSS_REGION="${SECURITY_AUTOPILOT_ALLOW_CROSS_REGION_DEPLOY:-false}"
AWS_REGION_EFFECTIVE="${AWS_REGION:-$PRIMARY_REGION}"
if [[ -z "${AWS_REGION:-}" ]]; then
  AWS_REGION_EFFECTIVE="$(read_env_file_value AWS_REGION || true)"
fi
if [[ -z "$AWS_REGION_EFFECTIVE" ]]; then
  AWS_REGION_EFFECTIVE="$PRIMARY_REGION"
fi

ALARM_TOPIC_ARN="${DR_ALARM_TOPIC_ARN:-$(read_env_file_value DR_ALARM_TOPIC_ARN || true)}"
SECONDARY_BACKUP_VAULT_ARN="${DR_SECONDARY_BACKUP_VAULT_ARN:-$(read_env_file_value DR_SECONDARY_BACKUP_VAULT_ARN || true)}"
BACKUP_VAULT_NAME="${DR_BACKUP_VAULT_NAME:-$(read_env_file_value DR_BACKUP_VAULT_NAME || true)}"
BACKUP_PLAN_NAME="${DR_BACKUP_PLAN_NAME:-$(read_env_file_value DR_BACKUP_PLAN_NAME || true)}"

READINESS_URL="${API_READY_URL:-$(read_env_file_value API_READY_URL || true)}"
if [[ -z "$READINESS_URL" ]]; then
  api_public_url="$(read_env_file_value API_PUBLIC_URL || true)"
  if [[ -n "$api_public_url" ]]; then
    READINESS_URL="${api_public_url%/}/ready"
  fi
fi

SKIP_READINESS_GATE="no"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      AWS_REGION_EFFECTIVE="$2"
      shift 2
      ;;
    --dr-stack)
      DR_STACK_NAME="$2"
      shift 2
      ;;
    --alarm-topic-arn)
      ALARM_TOPIC_ARN="$2"
      shift 2
      ;;
    --secondary-backup-vault-arn)
      SECONDARY_BACKUP_VAULT_ARN="$2"
      shift 2
      ;;
    --backup-vault-name)
      BACKUP_VAULT_NAME="$2"
      shift 2
      ;;
    --backup-plan-name)
      BACKUP_PLAN_NAME="$2"
      shift 2
      ;;
    --api-ready-url)
      READINESS_URL="$2"
      shift 2
      ;;
    --skip-readiness-gate)
      SKIP_READINESS_GATE="yes"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$ALLOW_CROSS_REGION" != "true" && "$AWS_REGION_EFFECTIVE" != "$PRIMARY_REGION" ]]; then
  echo "Refusing to deploy ${DR_STACK_NAME} outside primary region (${PRIMARY_REGION})." >&2
  echo "Requested region: ${AWS_REGION_EFFECTIVE}" >&2
  echo "If you really intend a cross-region deploy, set SECURITY_AUTOPILOT_ALLOW_CROSS_REGION_DEPLOY=true." >&2
  exit 2
fi

echo "Deploying Phase 3 DR stack in region: ${AWS_REGION_EFFECTIVE}"
echo "DR stack: ${DR_STACK_NAME}"

params=()
if [[ -n "$ALARM_TOPIC_ARN" ]]; then
  params+=("AlarmTopicArn=${ALARM_TOPIC_ARN}")
fi
if [[ -n "$SECONDARY_BACKUP_VAULT_ARN" ]]; then
  params+=("SecondaryBackupVaultArn=${SECONDARY_BACKUP_VAULT_ARN}")
fi
if [[ -n "$BACKUP_VAULT_NAME" ]]; then
  params+=("BackupVaultName=${BACKUP_VAULT_NAME}")
fi
if [[ -n "$BACKUP_PLAN_NAME" ]]; then
  params+=("BackupPlanName=${BACKUP_PLAN_NAME}")
fi

if [[ ${#params[@]} -gt 0 ]]; then
  aws cloudformation deploy \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$DR_STACK_NAME" \
    --template-file infrastructure/cloudformation/dr-backup-controls.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides "${params[@]}" \
    --no-fail-on-empty-changeset
else
  aws cloudformation deploy \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$DR_STACK_NAME" \
    --template-file infrastructure/cloudformation/dr-backup-controls.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset
fi

if [[ "$SKIP_READINESS_GATE" != "yes" && -n "$READINESS_URL" ]]; then
  echo "Running readiness gate: ${READINESS_URL}"
  python3 scripts/check_api_readiness.py --url "$READINESS_URL"
else
  echo "Skipping readiness gate (no API_READY_URL/API_PUBLIC_URL or --skip-readiness-gate)."
fi

echo "Phase 3 deployment step completed."
