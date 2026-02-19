#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

EDGE_STACK_NAME="${EDGE_STACK_NAME:-security-autopilot-edge-protection}"
PRIMARY_REGION="${SECURITY_AUTOPILOT_PRIMARY_REGION:-eu-north-1}"
ALLOW_CROSS_REGION="${SECURITY_AUTOPILOT_ALLOW_CROSS_REGION_DEPLOY:-false}"
AWS_REGION_EFFECTIVE="${AWS_REGION:-$PRIMARY_REGION}"
SCOPE="${EDGE_WAF_SCOPE:-REGIONAL}"
# Allow explicitly clearing the association by setting the env var (even to empty)
# or passing the CLI flag with an empty value.
API_GATEWAY_STAGE_ARN_SET="false"
if [[ ${EDGE_API_GATEWAY_STAGE_ARN+x} ]]; then
  API_GATEWAY_STAGE_ARN_SET="true"
  API_GATEWAY_STAGE_ARN="$EDGE_API_GATEWAY_STAGE_ARN"
else
  API_GATEWAY_STAGE_ARN=""
fi

ALB_ARN_SET="false"
if [[ ${EDGE_ALB_ARN+x} ]]; then
  ALB_ARN_SET="true"
  ALB_ARN="$EDGE_ALB_ARN"
else
  ALB_ARN=""
fi

ALARM_TOPIC_ARN="${EDGE_ALARM_TOPIC_ARN:-}"
RATE_LIMIT="${EDGE_RATE_LIMIT_REQUESTS_PER_5_MIN:-2000}"
BLOCKED_THRESHOLD="${EDGE_BLOCKED_REQUESTS_THRESHOLD:-}"
RATE_LIMITED_THRESHOLD="${EDGE_RATE_LIMITED_REQUESTS_THRESHOLD:-}"
ENABLE_ALLOW_LIST="${EDGE_ENABLE_IPV4_ALLOW_LIST:-false}"
ALLOWED_IPV4_CIDRS="${EDGE_ALLOWED_IPV4_CIDRS:-203.0.113.10/32}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      AWS_REGION_EFFECTIVE="$2"
      shift 2
      ;;
    --stack)
      EDGE_STACK_NAME="$2"
      shift 2
      ;;
    --scope)
      SCOPE="$2"
      shift 2
      ;;
    --api-gateway-stage-arn)
      API_GATEWAY_STAGE_ARN_SET="true"
      API_GATEWAY_STAGE_ARN="$2"
      shift 2
      ;;
    --alb-arn)
      ALB_ARN_SET="true"
      ALB_ARN="$2"
      shift 2
      ;;
    --alarm-topic-arn)
      ALARM_TOPIC_ARN="$2"
      shift 2
      ;;
    --rate-limit)
      RATE_LIMIT="$2"
      shift 2
      ;;
    --blocked-threshold)
      BLOCKED_THRESHOLD="$2"
      shift 2
      ;;
    --rate-limited-threshold)
      RATE_LIMITED_THRESHOLD="$2"
      shift 2
      ;;
    --enable-ipv4-allow-list)
      ENABLE_ALLOW_LIST="$2"
      shift 2
      ;;
    --allowed-ipv4-cidrs)
      ALLOWED_IPV4_CIDRS="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$SCOPE" == "CLOUDFRONT" && "$AWS_REGION_EFFECTIVE" != "us-east-1" ]]; then
  echo "CLOUDFRONT-scope Web ACLs must be deployed via the us-east-1 WAFv2 endpoint." >&2
  echo "Requested region: ${AWS_REGION_EFFECTIVE}" >&2
  echo "Re-run with: --region us-east-1 --scope CLOUDFRONT (and set SECURITY_AUTOPILOT_ALLOW_CROSS_REGION_DEPLOY=true)." >&2
  exit 2
fi

if [[ "$ALLOW_CROSS_REGION" != "true" && "$AWS_REGION_EFFECTIVE" != "$PRIMARY_REGION" ]]; then
  echo "Refusing to deploy ${EDGE_STACK_NAME} outside primary region (${PRIMARY_REGION})." >&2
  echo "Requested region: ${AWS_REGION_EFFECTIVE}" >&2
  echo "If you really intend a cross-region deploy, set SECURITY_AUTOPILOT_ALLOW_CROSS_REGION_DEPLOY=true." >&2
  exit 2
fi

echo "Deploying edge protection stack: ${EDGE_STACK_NAME}"
echo "Region: ${AWS_REGION_EFFECTIVE}"
echo "Scope: ${SCOPE}"

# CloudFormation stacks that fail create end up in ROLLBACK_COMPLETE and cannot be updated.
existing_status="$(aws cloudformation describe-stacks --region "$AWS_REGION_EFFECTIVE" --stack-name "$EDGE_STACK_NAME" --query "Stacks[0].StackStatus" --output text 2>/dev/null || true)"
if [[ "$existing_status" == "ROLLBACK_COMPLETE" ]]; then
  echo "Stack '${EDGE_STACK_NAME}' is in ROLLBACK_COMPLETE and cannot be updated." >&2
  echo "Delete it and retry:" >&2
  echo "  aws cloudformation delete-stack --region ${AWS_REGION_EFFECTIVE} --stack-name ${EDGE_STACK_NAME}" >&2
  echo "  aws cloudformation wait stack-delete-complete --region ${AWS_REGION_EFFECTIVE} --stack-name ${EDGE_STACK_NAME}" >&2
  exit 2
fi

if [[ -n "$API_GATEWAY_STAGE_ARN" ]]; then
  # HTTP API default stages use "$default", so allow "$" in stage names.
  if ! echo "$API_GATEWAY_STAGE_ARN" | grep -Eq '^arn:aws:apigateway:[a-z0-9-]+::/(restapis|apis)/[A-Za-z0-9]+/stages/[A-Za-z0-9._$-]+$'; then
    echo "EDGE_API_GATEWAY_STAGE_ARN does not look like a valid API Gateway stage ARN:" >&2
    echo "  ${API_GATEWAY_STAGE_ARN}" >&2
    echo "Expected formats:" >&2
    echo "  arn:aws:apigateway:<region>::/restapis/<apiId>/stages/<stageName>  (REST API)" >&2
    echo "  arn:aws:apigateway:<region>::/apis/<apiId>/stages/<stageName>      (HTTP/WebSocket API)" >&2
    exit 2
  fi
fi

params=(
  "Scope=${SCOPE}"
  "RateLimitRequestsPer5Min=${RATE_LIMIT}"
  "EnableIpv4AllowList=${ENABLE_ALLOW_LIST}"
  "AllowedIpv4Cidrs=${ALLOWED_IPV4_CIDRS}"
)

if [[ -n "$BLOCKED_THRESHOLD" ]]; then
  params+=("BlockedRequestsThreshold=${BLOCKED_THRESHOLD}")
fi
if [[ -n "$RATE_LIMITED_THRESHOLD" ]]; then
  params+=("RateLimitedRequestsThreshold=${RATE_LIMITED_THRESHOLD}")
fi

if [[ "$API_GATEWAY_STAGE_ARN_SET" == "true" ]]; then
  params+=("ApiGatewayStageArn=${API_GATEWAY_STAGE_ARN}")
fi
if [[ "$ALB_ARN_SET" == "true" ]]; then
  params+=("ApplicationLoadBalancerArn=${ALB_ARN}")
fi
if [[ -n "$ALARM_TOPIC_ARN" ]]; then
  params+=("AlarmTopicArn=${ALARM_TOPIC_ARN}")
fi

aws cloudformation deploy \
  --region "$AWS_REGION_EFFECTIVE" \
  --stack-name "$EDGE_STACK_NAME" \
  --template-file infrastructure/cloudformation/edge-protection.yaml \
  --parameter-overrides "${params[@]}" \
  --no-fail-on-empty-changeset

echo "Edge protection deployment completed."
