#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${SAAS_ENV_FILE:-.env}"

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

STACK_NAME="${SAAS_ECS_STACK_NAME:-security-autopilot-saas-ecs-dev}"
NAME_PREFIX="${SAAS_ECS_NAME_PREFIX:-security-autopilot-dev}"
AWS_REGION_EFFECTIVE="${AWS_REGION:-$(read_env_file_value AWS_REGION || true)}"
AWS_REGION_EFFECTIVE="${AWS_REGION_EFFECTIVE:-eu-north-1}"

APP_NAME="${APP_NAME:-$(read_env_file_value APP_NAME || true)}"
APP_NAME="${APP_NAME:-AWS Security Autopilot}"
APP_ENV="${ENV:-$(read_env_file_value ENV || true)}"
APP_ENV="${APP_ENV:-dev}"
LOG_LEVEL="${LOG_LEVEL:-$(read_env_file_value LOG_LEVEL || true)}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

FRONTEND_URL="${FRONTEND_URL:-$(read_env_file_value FRONTEND_URL || true)}"
FRONTEND_URL="${FRONTEND_URL:-https://valensjewelry.com}"
CORS_ORIGINS="${CORS_ORIGINS:-$(read_env_file_value CORS_ORIGINS || true)}"
CORS_ORIGINS="${CORS_ORIGINS:-https://valensjewelry.com}"
WORKER_POOL="${WORKER_POOL:-$(read_env_file_value WORKER_POOL || true)}"
WORKER_POOL="${WORKER_POOL:-all}"

SQS_STACK_NAME="${SQS_STACK_NAME:-security-autopilot-sqs-queues}"

ECR_REPO_NAME="${SAAS_ECR_REPO_NAME:-security-autopilot-app}"
IMAGE_TAG="${SAAS_IMAGE_TAG:-dev}"
CPU_ARCH="${SAAS_CPU_ARCH:-ARM64}"

API_DOMAIN="${SAAS_API_DOMAIN:-api.valensjewelry.com}"
CERT_ARN="${SAAS_CERTIFICATE_ARN:-}"

API_DESIRED_COUNT="${SAAS_API_DESIRED_COUNT:-0}"
WORKER_DESIRED_COUNT="${SAAS_WORKER_DESIRED_COUNT:-0}"

DATABASE_URL="${DATABASE_URL:-$(read_env_file_value DATABASE_URL || true)}"
JWT_SECRET="${JWT_SECRET:-$(read_env_file_value JWT_SECRET || true)}"
CONTROL_PLANE_EVENTS_SECRET="${CONTROL_PLANE_EVENTS_SECRET:-$(read_env_file_value CONTROL_PLANE_EVENTS_SECRET || true)}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      AWS_REGION_EFFECTIVE="$2"; shift 2 ;;
    --stack)
      STACK_NAME="$2"; shift 2 ;;
    --name-prefix)
      NAME_PREFIX="$2"; shift 2 ;;
    --sqs-stack)
      SQS_STACK_NAME="$2"; shift 2 ;;
    --repo)
      ECR_REPO_NAME="$2"; shift 2 ;;
    --tag)
      IMAGE_TAG="$2"; shift 2 ;;
    --cpu-arch)
      CPU_ARCH="$2"; shift 2 ;;
    --api-domain)
      API_DOMAIN="$2"; shift 2 ;;
    --certificate-arn)
      CERT_ARN="$2"; shift 2 ;;
    --api-count)
      API_DESIRED_COUNT="$2"; shift 2 ;;
    --worker-count)
      WORKER_DESIRED_COUNT="$2"; shift 2 ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$DATABASE_URL" ]]; then
  echo "Missing DATABASE_URL (set in env or ${ENV_FILE})." >&2
  exit 2
fi
if [[ -z "$JWT_SECRET" ]]; then
  echo "Missing JWT_SECRET (set in env or ${ENV_FILE})." >&2
  exit 2
fi
if [[ -z "$CONTROL_PLANE_EVENTS_SECRET" ]]; then
  echo "Missing CONTROL_PLANE_EVENTS_SECRET (set in env or ${ENV_FILE})." >&2
  exit 2
fi

params=(
  "NamePrefix=${NAME_PREFIX}"
  "AppName=${APP_NAME}"
  "AppEnv=${APP_ENV}"
  "LogLevel=${LOG_LEVEL}"
  "FrontendUrl=${FRONTEND_URL}"
  "CorsOrigins=${CORS_ORIGINS}"
  "WorkerPool=${WORKER_POOL}"

  "EcrRepoName=${ECR_REPO_NAME}"
  "ImageTag=${IMAGE_TAG}"
  "CpuArchitecture=${CPU_ARCH}"

  "ApiDomain=${API_DOMAIN}"
  "CertificateArn=${CERT_ARN}"

  "SqsStackName=${SQS_STACK_NAME}"

  "DatabaseUrl=${DATABASE_URL}"
  "JwtSecret=${JWT_SECRET}"
  "ControlPlaneEventsSecret=${CONTROL_PLANE_EVENTS_SECRET}"

  "ApiDesiredCount=${API_DESIRED_COUNT}"
  "WorkerDesiredCount=${WORKER_DESIRED_COUNT}"
)

aws cloudformation deploy \
  --region "$AWS_REGION_EFFECTIVE" \
  --stack-name "$STACK_NAME" \
  --template-file infrastructure/cloudformation/saas-ecs-dev.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides "${params[@]}" \
  --no-fail-on-empty-changeset

echo "Deployed: ${STACK_NAME} (${AWS_REGION_EFFECTIVE})"
aws cloudformation describe-stacks \
  --region "$AWS_REGION_EFFECTIVE" \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs" \
  --output table

