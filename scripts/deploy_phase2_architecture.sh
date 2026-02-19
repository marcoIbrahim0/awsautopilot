#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${PHASE2_ENV_FILE:-.env}"

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

SQS_STACK_NAME="${SQS_STACK_NAME:-security-autopilot-sqs-queues}"
FORWARDER_STACK_NAME="${FORWARDER_STACK_NAME:-security-autopilot-control-plane-forwarder}"
RECONCILE_STACK_NAME="${RECONCILE_STACK_NAME:-security-autopilot-reconcile-scheduler}"
PRIMARY_REGION="${SECURITY_AUTOPILOT_PRIMARY_REGION:-eu-north-1}"
ALLOW_CROSS_REGION="${SECURITY_AUTOPILOT_ALLOW_CROSS_REGION_DEPLOY:-false}"
AWS_REGION_EFFECTIVE="${AWS_REGION:-$PRIMARY_REGION}"
if [[ -z "${AWS_REGION:-}" ]]; then
  AWS_REGION_EFFECTIVE="$(read_env_file_value AWS_REGION || true)"
fi
if [[ -z "$AWS_REGION_EFFECTIVE" ]]; then
  AWS_REGION_EFFECTIVE="$PRIMARY_REGION"
fi

ALARM_TOPIC_ARN="${SQS_ALARM_TOPIC_ARN:-$(read_env_file_value SQS_ALARM_TOPIC_ARN || true)}"

DEPLOY_FORWARDER="auto"
DEPLOY_RECONCILE="auto"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      AWS_REGION_EFFECTIVE="$2"
      shift 2
      ;;
    --sqs-stack)
      SQS_STACK_NAME="$2"
      shift 2
      ;;
    --forwarder-stack)
      FORWARDER_STACK_NAME="$2"
      shift 2
      ;;
    --reconcile-stack)
      RECONCILE_STACK_NAME="$2"
      shift 2
      ;;
    --alarm-topic-arn)
      ALARM_TOPIC_ARN="$2"
      shift 2
      ;;
    --deploy-forwarder)
      DEPLOY_FORWARDER="yes"
      shift
      ;;
    --skip-forwarder)
      DEPLOY_FORWARDER="no"
      shift
      ;;
    --deploy-reconcile)
      DEPLOY_RECONCILE="yes"
      shift
      ;;
    --skip-reconcile)
      DEPLOY_RECONCILE="no"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$ALLOW_CROSS_REGION" != "true" && "$AWS_REGION_EFFECTIVE" != "$PRIMARY_REGION" ]]; then
  echo "Refusing to deploy Phase 2 stacks outside primary region (${PRIMARY_REGION})." >&2
  echo "Requested region: ${AWS_REGION_EFFECTIVE}" >&2
  echo "If you really intend a cross-region deploy, set SECURITY_AUTOPILOT_ALLOW_CROSS_REGION_DEPLOY=true." >&2
  exit 2
fi

FORWARDER_INGEST_URL="${CONTROL_PLANE_SAAS_INGEST_URL:-$(read_env_file_value CONTROL_PLANE_SAAS_INGEST_URL || true)}"
if [[ -z "$FORWARDER_INGEST_URL" && -n "${API_PUBLIC_URL:-}" ]]; then
  FORWARDER_INGEST_URL="${API_PUBLIC_URL%/}/api/control-plane/events"
fi
if [[ -z "$FORWARDER_INGEST_URL" ]]; then
  api_public_url="$(read_env_file_value API_PUBLIC_URL || true)"
  if [[ -n "$api_public_url" ]]; then
    FORWARDER_INGEST_URL="${api_public_url%/}/api/control-plane/events"
  fi
fi
FORWARDER_TOKEN="${CONTROL_PLANE_TOKEN:-$(read_env_file_value CONTROL_PLANE_TOKEN || true)}"

RECONCILE_BASE_URL="${RECONCILE_SAAS_BASE_URL:-$(read_env_file_value RECONCILE_SAAS_BASE_URL || true)}"
if [[ -z "$RECONCILE_BASE_URL" && -n "${API_PUBLIC_URL:-}" ]]; then
  RECONCILE_BASE_URL="${API_PUBLIC_URL%/}"
fi
if [[ -z "$RECONCILE_BASE_URL" ]]; then
  api_public_url="$(read_env_file_value API_PUBLIC_URL || true)"
  if [[ -n "$api_public_url" ]]; then
    RECONCILE_BASE_URL="${api_public_url%/}"
  fi
fi
RECONCILE_SECRET="${RECONCILE_CONTROL_PLANE_SECRET:-$(read_env_file_value RECONCILE_CONTROL_PLANE_SECRET || true)}"
if [[ -z "$RECONCILE_SECRET" ]]; then
  RECONCILE_SECRET="${CONTROL_PLANE_EVENTS_SECRET:-}"
fi
if [[ -z "$RECONCILE_SECRET" ]]; then
  RECONCILE_SECRET="$(read_env_file_value CONTROL_PLANE_EVENTS_SECRET || true)"
fi

if [[ "$DEPLOY_FORWARDER" == "auto" ]]; then
  if [[ -n "$FORWARDER_INGEST_URL" && -n "$FORWARDER_TOKEN" ]]; then
    DEPLOY_FORWARDER="yes"
  else
    DEPLOY_FORWARDER="no"
  fi
fi

if [[ "$DEPLOY_RECONCILE" == "auto" ]]; then
  if [[ -n "$RECONCILE_BASE_URL" && -n "$RECONCILE_SECRET" ]]; then
    DEPLOY_RECONCILE="yes"
  else
    DEPLOY_RECONCILE="no"
  fi
fi

echo "Deploying Phase 2 architecture stacks in region: ${AWS_REGION_EFFECTIVE}"
echo "SQS stack: ${SQS_STACK_NAME}"

sqs_params=()
if [[ -n "$ALARM_TOPIC_ARN" ]]; then
  sqs_params+=("AlarmTopicArn=${ALARM_TOPIC_ARN}")
fi

if [[ ${#sqs_params[@]} -gt 0 ]]; then
  aws cloudformation deploy \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$SQS_STACK_NAME" \
    --template-file infrastructure/cloudformation/sqs-queues.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides "${sqs_params[@]}" \
    --no-fail-on-empty-changeset
else
  aws cloudformation deploy \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$SQS_STACK_NAME" \
    --template-file infrastructure/cloudformation/sqs-queues.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset
fi

python3 scripts/set_env_sqs_from_stack.py --stack-name "$SQS_STACK_NAME" --region "$AWS_REGION_EFFECTIVE"

if [[ "$DEPLOY_FORWARDER" == "yes" ]]; then
  echo "Forwarder stack: ${FORWARDER_STACK_NAME}"
  if [[ -z "$FORWARDER_INGEST_URL" || -z "$FORWARDER_TOKEN" ]]; then
    echo "Cannot deploy forwarder: missing CONTROL_PLANE_SAAS_INGEST_URL/API_PUBLIC_URL or CONTROL_PLANE_TOKEN" >&2
    exit 1
  fi

  forwarder_params=()
  forwarder_params+=("SaaSIngestUrl=${FORWARDER_INGEST_URL}")
  forwarder_params+=("ControlPlaneToken=${FORWARDER_TOKEN}")
  if [[ -n "$ALARM_TOPIC_ARN" ]]; then
    forwarder_params+=("AlarmTopicArn=${ALARM_TOPIC_ARN}")
  fi

  aws cloudformation deploy \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$FORWARDER_STACK_NAME" \
    --template-file infrastructure/cloudformation/control-plane-forwarder-template.yaml \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides "${forwarder_params[@]}" \
    --no-fail-on-empty-changeset
else
  echo "Skipping forwarder stack deployment (missing params or skip flag)."
fi

if [[ "$DEPLOY_RECONCILE" == "yes" ]]; then
  echo "Reconcile scheduler stack: ${RECONCILE_STACK_NAME}"
  if [[ -z "$RECONCILE_BASE_URL" || -z "$RECONCILE_SECRET" ]]; then
    echo "Cannot deploy reconcile scheduler: missing RECONCILE_SAAS_BASE_URL/API_PUBLIC_URL or RECONCILE_CONTROL_PLANE_SECRET/CONTROL_PLANE_EVENTS_SECRET" >&2
    exit 1
  fi

  reconcile_params=()
  reconcile_params+=("SaaSBaseUrl=${RECONCILE_BASE_URL}")
  reconcile_params+=("ControlPlaneSecret=${RECONCILE_SECRET}")
  if [[ -n "$ALARM_TOPIC_ARN" ]]; then
    reconcile_params+=("AlarmTopicArn=${ALARM_TOPIC_ARN}")
  fi

  aws cloudformation deploy \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$RECONCILE_STACK_NAME" \
    --template-file infrastructure/cloudformation/reconcile-scheduler-template.yaml \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides "${reconcile_params[@]}" \
    --no-fail-on-empty-changeset
else
  echo "Skipping reconcile scheduler deployment (missing params or skip flag)."
fi

echo "Phase 2 deployment step completed."
