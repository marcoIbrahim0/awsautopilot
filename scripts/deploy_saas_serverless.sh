#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${SAAS_ENV_FILE:-config/.env.ops}"

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
NAME_PREFIX="${SAAS_SERVERLESS_NAME_PREFIX:-security-autopilot-dev}"
SQS_STACK_NAME="${SQS_STACK_NAME:-security-autopilot-sqs-queues}"

APP_NAME="${APP_NAME:-$(read_env_file_value APP_NAME || true)}"
APP_NAME="${APP_NAME:-AWS Security Autopilot}"
APP_ENV="${ENV:-$(read_env_file_value ENV || true)}"
APP_ENV="${APP_ENV:-dev}"
LOG_LEVEL="${LOG_LEVEL:-$(read_env_file_value LOG_LEVEL || true)}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

FRONTEND_URL="${FRONTEND_URL:-$(read_env_file_value FRONTEND_URL || true)}"
FRONTEND_URL="${FRONTEND_URL:-https://ocypheris.com}"
CORS_ORIGINS="${CORS_ORIGINS:-$(read_env_file_value CORS_ORIGINS || true)}"
CORS_ORIGINS="${CORS_ORIGINS:-https://ocypheris.com,http://localhost:3000}"

CFN_FORWARDER_TEMPLATE_URL="${CLOUDFORMATION_CONTROL_PLANE_FORWARDER_TEMPLATE_URL:-$(read_env_file_value CLOUDFORMATION_CONTROL_PLANE_FORWARDER_TEMPLATE_URL || true)}"
SAAS_ADMIN_EMAILS_VALUE="${SAAS_ADMIN_EMAILS:-$(read_env_file_value SAAS_ADMIN_EMAILS || true)}"
S3_EXPORT_BUCKET_VALUE="${S3_EXPORT_BUCKET:-$(read_env_file_value S3_EXPORT_BUCKET || true)}"
S3_EXPORT_BUCKET_REGION_VALUE="${S3_EXPORT_BUCKET_REGION:-$(read_env_file_value S3_EXPORT_BUCKET_REGION || true)}"
S3_SUPPORT_BUCKET_VALUE="${S3_SUPPORT_BUCKET:-$(read_env_file_value S3_SUPPORT_BUCKET || true)}"
S3_SUPPORT_BUCKET_REGION_VALUE="${S3_SUPPORT_BUCKET_REGION:-$(read_env_file_value S3_SUPPORT_BUCKET_REGION || true)}"
SAAS_BUNDLE_EXECUTOR_ENABLED_VALUE="${SAAS_BUNDLE_EXECUTOR_ENABLED:-$(read_env_file_value SAAS_BUNDLE_EXECUTOR_ENABLED || true)}"
SAAS_BUNDLE_RUNNER_TEMPLATE_S3_URI_VALUE="${SAAS_BUNDLE_RUNNER_TEMPLATE_S3_URI:-$(read_env_file_value SAAS_BUNDLE_RUNNER_TEMPLATE_S3_URI || true)}"
SAAS_BUNDLE_RUNNER_TEMPLATE_VERSION_VALUE="${SAAS_BUNDLE_RUNNER_TEMPLATE_VERSION:-$(read_env_file_value SAAS_BUNDLE_RUNNER_TEMPLATE_VERSION || true)}"
SAAS_BUNDLE_RUNNER_TEMPLATE_CACHE_SECONDS_VALUE="${SAAS_BUNDLE_RUNNER_TEMPLATE_CACHE_SECONDS:-$(read_env_file_value SAAS_BUNDLE_RUNNER_TEMPLATE_CACHE_SECONDS || true)}"
TENANT_RECONCILIATION_ENABLED_VALUE="${TENANT_RECONCILIATION_ENABLED:-$(read_env_file_value TENANT_RECONCILIATION_ENABLED || true)}"
TENANT_RECONCILIATION_PILOT_TENANTS_VALUE="${TENANT_RECONCILIATION_PILOT_TENANTS:-$(read_env_file_value TENANT_RECONCILIATION_PILOT_TENANTS || true)}"
CONTROL_PLANE_SHADOW_MODE_VALUE="${CONTROL_PLANE_SHADOW_MODE:-$(read_env_file_value CONTROL_PLANE_SHADOW_MODE || true)}"
ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED_VALUE="${ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED:-$(read_env_file_value ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED || true)}"
CONTROL_PLANE_SOURCE_VALUE="${CONTROL_PLANE_SOURCE:-$(read_env_file_value CONTROL_PLANE_SOURCE || true)}"
CONTROL_PLANE_AUTHORITATIVE_CONTROLS_VALUE="${CONTROL_PLANE_AUTHORITATIVE_CONTROLS:-$(read_env_file_value CONTROL_PLANE_AUTHORITATIVE_CONTROLS || true)}"
CONTROL_PLANE_RECENT_TOUCH_LOOKBACK_MINUTES_VALUE="${CONTROL_PLANE_RECENT_TOUCH_LOOKBACK_MINUTES:-$(read_env_file_value CONTROL_PLANE_RECENT_TOUCH_LOOKBACK_MINUTES || true)}"
API_PUBLIC_URL_VALUE="${API_PUBLIC_URL:-$(read_env_file_value API_PUBLIC_URL || true)}"
FIREBASE_PROJECT_ID_VALUE="${FIREBASE_PROJECT_ID:-$(read_env_file_value FIREBASE_PROJECT_ID || true)}"
FIREBASE_EMAIL_CONTINUE_URL_BASE_VALUE="${FIREBASE_EMAIL_CONTINUE_URL_BASE:-$(read_env_file_value FIREBASE_EMAIL_CONTINUE_URL_BASE || true)}"
EMAIL_FROM_VALUE="${EMAIL_FROM:-$(read_env_file_value EMAIL_FROM || true)}"
EMAIL_SMTP_HOST_VALUE="${EMAIL_SMTP_HOST:-$(read_env_file_value EMAIL_SMTP_HOST || true)}"
EMAIL_SMTP_PORT_VALUE="${EMAIL_SMTP_PORT:-$(read_env_file_value EMAIL_SMTP_PORT || true)}"
EMAIL_SMTP_PORT_VALUE="${EMAIL_SMTP_PORT_VALUE:-587}"
EMAIL_SMTP_STARTTLS_VALUE="${EMAIL_SMTP_STARTTLS:-$(read_env_file_value EMAIL_SMTP_STARTTLS || true)}"
EMAIL_SMTP_STARTTLS_VALUE="${EMAIL_SMTP_STARTTLS_VALUE:-true}"
EMAIL_SMTP_CREDENTIALS_SECRET_ID_VALUE="${EMAIL_SMTP_CREDENTIALS_SECRET_ID:-$(read_env_file_value EMAIL_SMTP_CREDENTIALS_SECRET_ID || true)}"

DATABASE_URL="${DATABASE_URL:-$(read_env_file_value DATABASE_URL || true)}"
JWT_SECRET="${JWT_SECRET:-$(read_env_file_value JWT_SECRET || true)}"
CONTROL_PLANE_EVENTS_SECRET="${CONTROL_PLANE_EVENTS_SECRET:-$(read_env_file_value CONTROL_PLANE_EVENTS_SECRET || true)}"

API_DOMAIN="${SAAS_API_DOMAIN:-api.ocypheris.com}"
CERT_ARN="${SAAS_CERTIFICATE_ARN:-}"

ENABLE_WORKER="${SAAS_SERVERLESS_ENABLE_WORKER:-$(read_env_file_value SAAS_SERVERLESS_ENABLE_WORKER || true)}"
ENABLE_WORKER="${ENABLE_WORKER:-false}"
WORKER_RESERVED_CONCURRENCY="${SAAS_SERVERLESS_WORKER_RESERVED_CONCURRENCY:-$(read_env_file_value SAAS_SERVERLESS_WORKER_RESERVED_CONCURRENCY || true)}"
WORKER_RESERVED_CONCURRENCY="${WORKER_RESERVED_CONCURRENCY:-0}"
INGEST_MAXIMUM_CONCURRENCY="${SAAS_SERVERLESS_INGEST_MAXIMUM_CONCURRENCY:-$(read_env_file_value SAAS_SERVERLESS_INGEST_MAXIMUM_CONCURRENCY || true)}"
INGEST_MAXIMUM_CONCURRENCY="${INGEST_MAXIMUM_CONCURRENCY:-8}"
EVENTS_MAXIMUM_CONCURRENCY="${SAAS_SERVERLESS_EVENTS_MAXIMUM_CONCURRENCY:-$(read_env_file_value SAAS_SERVERLESS_EVENTS_MAXIMUM_CONCURRENCY || true)}"
EVENTS_MAXIMUM_CONCURRENCY="${EVENTS_MAXIMUM_CONCURRENCY:-2}"
INVENTORY_MAXIMUM_CONCURRENCY="${SAAS_SERVERLESS_INVENTORY_MAXIMUM_CONCURRENCY:-$(read_env_file_value SAAS_SERVERLESS_INVENTORY_MAXIMUM_CONCURRENCY || true)}"
INVENTORY_MAXIMUM_CONCURRENCY="${INVENTORY_MAXIMUM_CONCURRENCY:-2}"
EXPORT_MAXIMUM_CONCURRENCY="${SAAS_SERVERLESS_EXPORT_MAXIMUM_CONCURRENCY:-$(read_env_file_value SAAS_SERVERLESS_EXPORT_MAXIMUM_CONCURRENCY || true)}"
EXPORT_MAXIMUM_CONCURRENCY="${EXPORT_MAXIMUM_CONCURRENCY:-2}"

IMAGE_TAG="${SAAS_SERVERLESS_IMAGE_TAG:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      AWS_REGION_EFFECTIVE="$2"; shift 2 ;;
    --build-stack)
      BUILD_STACK_NAME="$2"; shift 2 ;;
    --runtime-stack)
      RUNTIME_STACK_NAME="$2"; shift 2 ;;
    --name-prefix)
      NAME_PREFIX="$2"; shift 2 ;;
    --sqs-stack)
      SQS_STACK_NAME="$2"; shift 2 ;;
    --tag)
      IMAGE_TAG="$2"; shift 2 ;;
    --api-domain)
      API_DOMAIN="$2"; shift 2 ;;
    --certificate-arn)
      CERT_ARN="$2"; shift 2 ;;
    --enable-worker)
      ENABLE_WORKER="$2"; shift 2 ;;
    --worker-reserved-concurrency)
      WORKER_RESERVED_CONCURRENCY="$2"; shift 2 ;;
    --ingest-maximum-concurrency)
      INGEST_MAXIMUM_CONCURRENCY="$2"; shift 2 ;;
    --events-maximum-concurrency)
      EVENTS_MAXIMUM_CONCURRENCY="$2"; shift 2 ;;
    --inventory-maximum-concurrency)
      INVENTORY_MAXIMUM_CONCURRENCY="$2"; shift 2 ;;
    --export-maximum-concurrency)
      EXPORT_MAXIMUM_CONCURRENCY="$2"; shift 2 ;;
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

if [[ -z "$IMAGE_TAG" ]]; then
  IMAGE_TAG="$(date -u +%Y%m%dT%H%M%SZ)"
fi

echo "Region: ${AWS_REGION_EFFECTIVE}"
echo "Build stack: ${BUILD_STACK_NAME}"
echo "Runtime stack: ${RUNTIME_STACK_NAME}"
echo "Name prefix: ${NAME_PREFIX}"
echo "Image tag: ${IMAGE_TAG}"
echo "Enable worker mappings: ${ENABLE_WORKER}"

echo ""
echo "1) Deploying build stack (ECR + S3 + CodeBuild)..."
aws cloudformation deploy \
  --region "$AWS_REGION_EFFECTIVE" \
  --stack-name "$BUILD_STACK_NAME" \
  --template-file infrastructure/cloudformation/saas-serverless-build.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides "NamePrefix=${NAME_PREFIX}" \
  --no-fail-on-empty-changeset

SOURCE_BUCKET="$(
  aws cloudformation describe-stacks \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$BUILD_STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='SourceBucketName'].OutputValue" \
    --output text
)"
API_REPO_URI="$(
  aws cloudformation describe-stacks \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$BUILD_STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='ApiRepositoryUri'].OutputValue" \
    --output text
)"
WORKER_REPO_URI="$(
  aws cloudformation describe-stacks \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$BUILD_STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='WorkerRepositoryUri'].OutputValue" \
    --output text
)"
CODEBUILD_PROJECT="$(
  aws cloudformation describe-stacks \
    --region "$AWS_REGION_EFFECTIVE" \
    --stack-name "$BUILD_STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='CodeBuildProjectName'].OutputValue" \
    --output text
)"

if [[ -z "$SOURCE_BUCKET" || -z "$API_REPO_URI" || -z "$WORKER_REPO_URI" || -z "$CODEBUILD_PROJECT" ]]; then
  echo "Failed to read build stack outputs." >&2
  exit 2
fi

echo ""
echo "2) Creating source zip (excluding .env) for CodeBuild..."
TMP_ZIP="$(mktemp "/tmp/${NAME_PREFIX}-serverless-src-XXXXXX.zip")"
rm -f "$TMP_ZIP"
zip -r "$TMP_ZIP" \
  Containerfile.lambda-api \
  Containerfile.lambda-worker \
  alembic \
  alembic.ini \
  backend \
  worker \
  -x "*/__pycache__/*" \
  -x "__pycache__/*" \
  -x "*.pyc" \
  -x "*/.DS_Store" \
  -x ".DS_Store" \
  >/dev/null

S3_KEY="sources/${NAME_PREFIX}/serverless-${IMAGE_TAG}.zip"
echo "Uploading: s3://${SOURCE_BUCKET}/${S3_KEY}"
aws s3 cp "$TMP_ZIP" "s3://${SOURCE_BUCKET}/${S3_KEY}" --region "$AWS_REGION_EFFECTIVE" >/dev/null
rm -f "$TMP_ZIP"

echo ""
echo "3) Building/pushing images in CodeBuild..."
BUILD_ID="$(
  aws codebuild start-build \
    --region "$AWS_REGION_EFFECTIVE" \
    --project-name "$CODEBUILD_PROJECT" \
    --source-type-override S3 \
    --source-location-override "${SOURCE_BUCKET}/${S3_KEY}" \
    --environment-variables-override "name=IMAGE_TAG,value=${IMAGE_TAG},type=PLAINTEXT" \
    --query "build.id" \
    --output text
)"

if [[ -z "$BUILD_ID" || "$BUILD_ID" == "None" ]]; then
  echo "Failed to start CodeBuild build." >&2
  exit 2
fi

echo "Build ID: ${BUILD_ID}"

while true; do
  STATUS="$(
    aws codebuild batch-get-builds \
      --region "$AWS_REGION_EFFECTIVE" \
      --ids "$BUILD_ID" \
      --query "builds[0].buildStatus" \
      --output text
  )"
  case "$STATUS" in
    SUCCEEDED)
      break
      ;;
    FAILED|FAULT|STOPPED|TIMED_OUT)
      DEEP_LINK="$(
        aws codebuild batch-get-builds \
          --region "$AWS_REGION_EFFECTIVE" \
          --ids "$BUILD_ID" \
          --query "builds[0].logs.deepLink" \
          --output text
      )"
      echo "CodeBuild failed: ${STATUS}" >&2
      echo "Logs: ${DEEP_LINK}" >&2
      exit 2
      ;;
    IN_PROGRESS|QUEUED)
      sleep 10
      ;;
    *)
      echo "Unexpected CodeBuild status: ${STATUS}" >&2
      sleep 10
      ;;
  esac
done

API_IMAGE_URI="${API_REPO_URI}:${IMAGE_TAG}"
WORKER_IMAGE_URI="${WORKER_REPO_URI}:${IMAGE_TAG}"

echo ""
echo "4) Deploying runtime stack (API Gateway + Lambdas)..."
params=(
  "NamePrefix=${NAME_PREFIX}"
  "SqsStackName=${SQS_STACK_NAME}"
  "ApiImageUri=${API_IMAGE_URI}"
  "WorkerImageUri=${WORKER_IMAGE_URI}"
  "AppName=${APP_NAME}"
  "AppEnv=${APP_ENV}"
  "LogLevel=${LOG_LEVEL}"
  "FrontendUrl=${FRONTEND_URL}"
  "CorsOrigins=${CORS_ORIGINS}"
  "ApiPublicUrlOverride=${API_PUBLIC_URL_VALUE}"
  "DatabaseUrl=${DATABASE_URL}"
  "JwtSecret=${JWT_SECRET}"
  "ControlPlaneEventsSecret=${CONTROL_PLANE_EVENTS_SECRET}"
  "EnableWorker=${ENABLE_WORKER}"
  "WorkerReservedConcurrency=${WORKER_RESERVED_CONCURRENCY}"
  "IngestMaximumConcurrency=${INGEST_MAXIMUM_CONCURRENCY}"
  "EventsMaximumConcurrency=${EVENTS_MAXIMUM_CONCURRENCY}"
  "InventoryMaximumConcurrency=${INVENTORY_MAXIMUM_CONCURRENCY}"
  "ExportMaximumConcurrency=${EXPORT_MAXIMUM_CONCURRENCY}"
)

# Optional config (only passed when set).
if [[ -n "$CFN_FORWARDER_TEMPLATE_URL" ]]; then
  params+=("CloudFormationControlPlaneForwarderTemplateUrl=${CFN_FORWARDER_TEMPLATE_URL}")
fi
if [[ -n "$SAAS_ADMIN_EMAILS_VALUE" ]]; then
  params+=("SaasAdminEmails=${SAAS_ADMIN_EMAILS_VALUE}")
fi
if [[ -n "$S3_EXPORT_BUCKET_VALUE" ]]; then
  params+=("S3ExportBucket=${S3_EXPORT_BUCKET_VALUE}")
fi
if [[ -n "$S3_EXPORT_BUCKET_REGION_VALUE" ]]; then
  params+=("S3ExportBucketRegion=${S3_EXPORT_BUCKET_REGION_VALUE}")
fi
if [[ -n "$S3_SUPPORT_BUCKET_VALUE" ]]; then
  params+=("S3SupportBucket=${S3_SUPPORT_BUCKET_VALUE}")
fi
if [[ -n "$S3_SUPPORT_BUCKET_REGION_VALUE" ]]; then
  params+=("S3SupportBucketRegion=${S3_SUPPORT_BUCKET_REGION_VALUE}")
fi
if [[ -n "$SAAS_BUNDLE_EXECUTOR_ENABLED_VALUE" ]]; then
  params+=("SaasBundleExecutorEnabled=${SAAS_BUNDLE_EXECUTOR_ENABLED_VALUE}")
fi
if [[ -n "$SAAS_BUNDLE_RUNNER_TEMPLATE_S3_URI_VALUE" ]]; then
  params+=("SaasBundleRunnerTemplateS3Uri=${SAAS_BUNDLE_RUNNER_TEMPLATE_S3_URI_VALUE}")
fi
if [[ -n "$SAAS_BUNDLE_RUNNER_TEMPLATE_VERSION_VALUE" ]]; then
  params+=("SaasBundleRunnerTemplateVersion=${SAAS_BUNDLE_RUNNER_TEMPLATE_VERSION_VALUE}")
fi
if [[ -n "$SAAS_BUNDLE_RUNNER_TEMPLATE_CACHE_SECONDS_VALUE" ]]; then
  params+=("SaasBundleRunnerTemplateCacheSeconds=${SAAS_BUNDLE_RUNNER_TEMPLATE_CACHE_SECONDS_VALUE}")
fi
if [[ -n "$TENANT_RECONCILIATION_ENABLED_VALUE" ]]; then
  params+=("TenantReconciliationEnabled=${TENANT_RECONCILIATION_ENABLED_VALUE}")
fi
if [[ -n "$TENANT_RECONCILIATION_PILOT_TENANTS_VALUE" ]]; then
  params+=("TenantReconciliationPilotTenants=${TENANT_RECONCILIATION_PILOT_TENANTS_VALUE}")
fi
if [[ -n "$CONTROL_PLANE_SHADOW_MODE_VALUE" ]]; then
  params+=("ControlPlaneShadowMode=${CONTROL_PLANE_SHADOW_MODE_VALUE}")
fi
if [[ -n "$ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED_VALUE" ]]; then
  params+=("ActionsEffectiveOpenVisibilityEnabled=${ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED_VALUE}")
fi
if [[ -n "$CONTROL_PLANE_SOURCE_VALUE" ]]; then
  params+=("ControlPlaneSource=${CONTROL_PLANE_SOURCE_VALUE}")
fi
if [[ -n "$CONTROL_PLANE_AUTHORITATIVE_CONTROLS_VALUE" ]]; then
  params+=("ControlPlaneAuthoritativeControls=${CONTROL_PLANE_AUTHORITATIVE_CONTROLS_VALUE}")
fi
if [[ -n "$CONTROL_PLANE_RECENT_TOUCH_LOOKBACK_MINUTES_VALUE" ]]; then
  params+=("ControlPlaneRecentTouchLookbackMinutes=${CONTROL_PLANE_RECENT_TOUCH_LOOKBACK_MINUTES_VALUE}")
fi
if [[ -n "$FIREBASE_PROJECT_ID_VALUE" ]]; then
  params+=("FirebaseProjectId=${FIREBASE_PROJECT_ID_VALUE}")
fi
if [[ -n "$FIREBASE_EMAIL_CONTINUE_URL_BASE_VALUE" ]]; then
  params+=("FirebaseEmailContinueUrlBase=${FIREBASE_EMAIL_CONTINUE_URL_BASE_VALUE}")
fi
if [[ -n "$EMAIL_FROM_VALUE" ]]; then
  params+=("EmailFrom=${EMAIL_FROM_VALUE}")
fi
if [[ -n "$EMAIL_SMTP_HOST_VALUE" ]]; then
  params+=("EmailSmtpHost=${EMAIL_SMTP_HOST_VALUE}")
fi
if [[ -n "$EMAIL_SMTP_PORT_VALUE" ]]; then
  params+=("EmailSmtpPort=${EMAIL_SMTP_PORT_VALUE}")
fi
if [[ -n "$EMAIL_SMTP_STARTTLS_VALUE" ]]; then
  params+=("EmailSmtpStarttls=${EMAIL_SMTP_STARTTLS_VALUE}")
fi
if [[ -n "$EMAIL_SMTP_CREDENTIALS_SECRET_ID_VALUE" ]]; then
  params+=("EmailSmtpCredentialsSecretId=${EMAIL_SMTP_CREDENTIALS_SECRET_ID_VALUE}")
fi

# Always pass the custom-domain parameters so a prior domain can be cleared.
params+=("ApiDomainName=${API_DOMAIN}")
params+=("ApiCertificateArn=${CERT_ARN}")

aws cloudformation deploy \
  --region "$AWS_REGION_EFFECTIVE" \
  --stack-name "$RUNTIME_STACK_NAME" \
  --template-file infrastructure/cloudformation/saas-serverless-httpapi.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides "${params[@]}" \
  --no-fail-on-empty-changeset

echo ""
echo "5) Normalizing Lambda runtime/helper state drift..."
./scripts/normalize_serverless_runtime_state.sh \
  --region "$AWS_REGION_EFFECTIVE" \
  --name-prefix "$NAME_PREFIX" \
  --enable-worker "$ENABLE_WORKER" \
  --worker-reserved-concurrency "$WORKER_RESERVED_CONCURRENCY"

echo ""
echo "Deployed: ${RUNTIME_STACK_NAME} (${AWS_REGION_EFFECTIVE})"
aws cloudformation describe-stacks \
  --region "$AWS_REGION_EFFECTIVE" \
  --stack-name "$RUNTIME_STACK_NAME" \
  --query "Stacks[0].Outputs" \
  --output table
