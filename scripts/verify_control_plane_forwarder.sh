#!/usr/bin/env bash

set -u -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/verify_control_plane_forwarder.sh \
    --stack-name <stack_name> \
    --account-id <12_digit_account_id> \
    --region <aws_region> \
    --saas-api-url <https://api.example.com> \
    --saas-token <bearer_token>
USAGE
}

fail_phase() {
  local phase="$1"
  shift
  echo "[FAIL Phase ${phase}: $*]"
  exit 1
}

require_cmd() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || {
    echo "[FAIL: missing required command '${cmd}']"
    exit 1
  }
}

is_nonnegative_int() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

to_int() {
  awk -v value="${1:-0}" 'BEGIN { printf "%d", (value + 0) }'
}

extract_stack_output() {
  local stack_json="$1"
  local output_key="$2"
  jq -r --arg key "${output_key}" '
    (.Stacks[0].Outputs // [])
    | map(select(.OutputKey == $key) | .OutputValue)
    | .[0] // empty
  ' <<<"${stack_json}"
}

resolve_dlq_url() {
  local stack_json="$1"
  local rule_name="$2"
  local region="$3"
  local dlq_url=""
  local dlq_arn=""

  dlq_url="$(extract_stack_output "${stack_json}" "TargetDLQUrl")"
  if [[ -n "${dlq_url}" ]]; then
    echo "${dlq_url}"
    return 0
  fi

  dlq_arn="$(extract_stack_output "${stack_json}" "TargetDLQArn")"

  if [[ -z "${dlq_arn}" ]]; then
    local targets_json
    if ! targets_json="$(aws events list-targets-by-rule --rule "${rule_name}" --region "${region}" --output json 2>/dev/null)"; then
      return 1
    fi
    dlq_arn="$(jq -r '.Targets[0].DeadLetterConfig.Arn // empty' <<<"${targets_json}")"
  fi

  [[ -n "${dlq_arn}" ]] || return 1

  local queue_name="${dlq_arn##*:}"
  local queue_account_id
  queue_account_id="$(awk -F: '{print $5}' <<<"${dlq_arn}")"
  [[ -n "${queue_name}" && -n "${queue_account_id}" ]] || return 1

  local queue_url_json
  if ! queue_url_json="$(
    aws sqs get-queue-url \
      --queue-name "${queue_name}" \
      --queue-owner-aws-account-id "${queue_account_id}" \
      --region "${region}" \
      --output json 2>/dev/null
  )"; then
    return 1
  fi
  dlq_url="$(jq -r '.QueueUrl // empty' <<<"${queue_url_json}")"
  [[ -n "${dlq_url}" ]] || return 1
  echo "${dlq_url}"
}

extract_first_allowlisted_event_name() {
  local intake_file="${REPO_ROOT}/backend/services/control_plane_intake.py"
  local allowlist_file="${REPO_ROOT}/backend/services/control_plane_event_allowlist.py"

  [[ -f "${intake_file}" ]] || return 1
  [[ -f "${allowlist_file}" ]] || return 1

  grep -q "SUPPORTED_CONTROL_PLANE_EVENT_NAMES" "${intake_file}" || return 1
  grep -q "from backend.services.control_plane_event_allowlist import" "${intake_file}" || return 1

  local first_set_name
  first_set_name="$(
    awk '
      /SUPPORTED_CONTROL_PLANE_EVENT_NAMES[[:space:]]*:/ { in_block=1; next }
      in_block {
        if ($0 ~ /set\([A-Z0-9_]+\)/) {
          line=$0
          sub(/^.*set\(/, "", line)
          sub(/\).*/, "", line)
          print line
          exit
        }
        if ($0 ~ /\)/) { exit }
      }
    ' "${allowlist_file}"
  )"

  [[ -n "${first_set_name}" ]] || return 1

  awk -v set_name="${first_set_name}" '
    $0 ~ "^" set_name "[[:space:]]*:" { in_set=1 }
    in_set {
      if (match($0, /"[^"]+"/)) {
        print substr($0, RSTART + 1, RLENGTH - 2)
        exit
      }
    }
  ' "${allowlist_file}"
}

parse_name_from_events_arn() {
  local arn="$1"
  local resource_type="$2"
  local tail="${arn#*:${resource_type}/}"
  if [[ "${tail}" == "${arn}" || -z "${tail}" ]]; then
    return 1
  fi
  echo "${tail%%/*}"
}

get_rule_metric_sum() {
  local metric_name="$1"
  local start_time="$2"
  local end_time="$3"
  local region="$4"
  local rule_name="$5"
  local metric_json

  if ! metric_json="$(
    aws cloudwatch get-metric-statistics \
      --namespace AWS/Events \
      --metric-name "${metric_name}" \
      --start-time "${start_time}" \
      --end-time "${end_time}" \
      --period 60 \
      --statistics Sum \
      --dimensions Name=RuleName,Value="${rule_name}" \
      --region "${region}" \
      --output json 2>&1
  )"; then
    echo "__ERROR__${metric_json}"
    return 0
  fi

  jq -r '([.Datapoints[]?.Sum] | add) // 0' <<<"${metric_json}" 2>/dev/null
}

STACK_NAME=""
ACCOUNT_ID=""
REGION=""
SAAS_API_URL=""
SAAS_TOKEN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack-name)
      STACK_NAME="${2:-}"
      shift 2
      ;;
    --account-id)
      ACCOUNT_ID="${2:-}"
      shift 2
      ;;
    --region)
      REGION="${2:-}"
      shift 2
      ;;
    --saas-api-url)
      SAAS_API_URL="${2:-}"
      shift 2
      ;;
    --saas-token)
      SAAS_TOKEN="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      echo "[FAIL: unknown argument '$1']"
      exit 1
      ;;
  esac
done

if [[ -z "${STACK_NAME}" || -z "${ACCOUNT_ID}" || -z "${REGION}" || -z "${SAAS_API_URL}" || -z "${SAAS_TOKEN}" ]]; then
  usage
  echo "[FAIL: missing required arguments]"
  exit 1
fi

if [[ ! "${ACCOUNT_ID}" =~ ^[0-9]{12}$ ]]; then
  echo "[FAIL: --account-id must be a 12-digit AWS account ID]"
  exit 1
fi

require_cmd aws
require_cmd curl
require_cmd jq
require_cmd date
require_cmd awk
require_cmd sed
require_cmd grep
require_cmd python3

# Phase 1 - Structural wiring verification
STACK_JSON=""
if ! STACK_JSON="$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${REGION}" --output json 2>&1)"; then
  fail_phase 1 "Unable to describe stack '${STACK_NAME}' in region '${REGION}' - ${STACK_JSON}"
fi

RULE_ARN="$(extract_stack_output "${STACK_JSON}" "RuleArn")"
API_DESTINATION_ARN="$(extract_stack_output "${STACK_JSON}" "ApiDestinationArn")"
CONNECTION_ARN="$(extract_stack_output "${STACK_JSON}" "ConnectionArn")"
[[ -n "${RULE_ARN}" ]] || fail_phase 1 "Stack output RuleArn is missing"
[[ -n "${API_DESTINATION_ARN}" ]] || fail_phase 1 "Stack output ApiDestinationArn is missing"
[[ -n "${CONNECTION_ARN}" ]] || fail_phase 1 "Stack output ConnectionArn is missing"

RULE_NAME="${RULE_ARN##*/}"
API_DESTINATION_NAME="$(parse_name_from_events_arn "${API_DESTINATION_ARN}" "api-destination" || true)"
CONNECTION_NAME="$(parse_name_from_events_arn "${CONNECTION_ARN}" "connection" || true)"

[[ -n "${RULE_NAME}" ]] || fail_phase 1 "Could not parse rule name from RuleArn"
[[ -n "${API_DESTINATION_NAME}" ]] || fail_phase 1 "Could not parse API destination name from ApiDestinationArn"
[[ -n "${CONNECTION_NAME}" ]] || fail_phase 1 "Could not parse connection name from ConnectionArn"

RULE_JSON=""
if ! RULE_JSON="$(aws events describe-rule --name "${RULE_NAME}" --region "${REGION}" --output json 2>&1)"; then
  fail_phase 1 "Unable to describe EventBridge rule '${RULE_NAME}' - ${RULE_JSON}"
fi
RULE_STATE="$(jq -r '.State // empty' <<<"${RULE_JSON}")"
[[ "${RULE_STATE}" == "ENABLED" ]] || fail_phase 1 "EventBridge rule '${RULE_NAME}' state is '${RULE_STATE:-unknown}', expected ENABLED"

API_DESTINATION_JSON=""
if ! API_DESTINATION_JSON="$(
  aws events describe-api-destination --name "${API_DESTINATION_NAME}" --region "${REGION}" --output json 2>&1
)"; then
  fail_phase 1 "Unable to describe API destination '${API_DESTINATION_NAME}' - ${API_DESTINATION_JSON}"
fi
API_DESTINATION_STATE="$(jq -r '.ApiDestinationState // empty' <<<"${API_DESTINATION_JSON}")"
INVOCATION_ENDPOINT="$(jq -r '.InvocationEndpoint // empty' <<<"${API_DESTINATION_JSON}")"
[[ "${API_DESTINATION_STATE}" == "ACTIVE" ]] || fail_phase 1 "API destination '${API_DESTINATION_NAME}' state is '${API_DESTINATION_STATE:-unknown}', expected ACTIVE"
[[ "${INVOCATION_ENDPOINT}" == *"/api/control-plane/events"* ]] || fail_phase 1 "API destination endpoint '${INVOCATION_ENDPOINT}' does not contain /api/control-plane/events"

CONNECTION_JSON=""
if ! CONNECTION_JSON="$(aws events describe-connection --name "${CONNECTION_NAME}" --region "${REGION}" --output json 2>&1)"; then
  fail_phase 1 "Unable to describe connection '${CONNECTION_NAME}' - ${CONNECTION_JSON}"
fi
AUTH_TYPE="$(jq -r '.AuthorizationType // empty' <<<"${CONNECTION_JSON}")"
[[ "${AUTH_TYPE}" == "API_KEY" ]] || fail_phase 1 "Connection '${CONNECTION_NAME}' AuthorizationType is '${AUTH_TYPE:-unknown}', expected API_KEY"
CONNECTION_STATE="$(jq -r '.ConnectionState // empty' <<<"${CONNECTION_JSON}")"
[[ "${CONNECTION_STATE}" == "AUTHORIZED" ]] || fail_phase 1 "Connection '${CONNECTION_NAME}' state is '${CONNECTION_STATE:-unknown}', expected AUTHORIZED"
CONNECTION_SECRET_ARN="$(jq -r '.SecretArn // empty' <<<"${CONNECTION_JSON}")"
[[ -n "${CONNECTION_SECRET_ARN}" ]] || fail_phase 1 "Connection '${CONNECTION_NAME}' SecretArn is missing"

AUTH_ME_RESULT=""
if ! AUTH_ME_RESULT="$(
  curl -sS --max-time 20 \
    -H "Authorization: Bearer ${SAAS_TOKEN}" \
    -H "Accept: application/json" \
    -w $'\n%{http_code}' \
    "${SAAS_API_URL%/}/api/auth/me" 2>&1
)"; then
  fail_phase 1 "Unable to call /api/auth/me - ${AUTH_ME_RESULT}"
fi

AUTH_ME_HTTP_CODE="${AUTH_ME_RESULT##*$'\n'}"
AUTH_ME_BODY="${AUTH_ME_RESULT%$'\n'*}"
[[ "${AUTH_ME_HTTP_CODE}" == "200" ]] || fail_phase 1 "/api/auth/me returned HTTP ${AUTH_ME_HTTP_CODE}"

CURRENT_TOKEN_FINGERPRINT="$(jq -r '.control_plane_token_fingerprint // empty' <<<"${AUTH_ME_BODY}")"
[[ -n "${CURRENT_TOKEN_FINGERPRINT}" ]] || fail_phase 1 "/api/auth/me did not return control_plane_token_fingerprint"

CONNECTION_SECRET_STRING=""
if ! CONNECTION_SECRET_STRING="$(
  aws secretsmanager get-secret-value \
    --secret-id "${CONNECTION_SECRET_ARN}" \
    --region "${REGION}" \
    --query SecretString \
    --output text 2>&1
)"; then
  fail_phase 1 "Unable to read EventBridge connection secret '${CONNECTION_SECRET_ARN}' - ${CONNECTION_SECRET_STRING}"
fi

CONNECTION_SECRET_FINGERPRINT=""
if ! CONNECTION_SECRET_FINGERPRINT="$(
  PYTHONPATH="${REPO_ROOT}" python3 - "${CONNECTION_SECRET_STRING}" <<'PY'
import sys

from scripts.lib.control_plane_forwarder_audit import extract_connection_api_key_fingerprint

print(extract_connection_api_key_fingerprint(sys.argv[1]))
PY
)"; then
  fail_phase 1 "Unable to parse EventBridge connection secret for '${CONNECTION_NAME}'"
fi

[[ "${CONNECTION_SECRET_FINGERPRINT}" == "${CURRENT_TOKEN_FINGERPRINT}" ]] || fail_phase 1 \
  "Connection '${CONNECTION_NAME}' token fingerprint '${CONNECTION_SECRET_FINGERPRINT}' does not match current SaaS tenant fingerprint '${CURRENT_TOKEN_FINGERPRINT}'"

TARGET_DLQ_URL="$(resolve_dlq_url "${STACK_JSON}" "${RULE_NAME}" "${REGION}" || true)"
[[ -n "${TARGET_DLQ_URL}" ]] || fail_phase 1 "Unable to resolve target DLQ URL from stack outputs or rule target"

DLQ_ATTR_JSON=""
if ! DLQ_ATTR_JSON="$(
  aws sqs get-queue-attributes \
    --queue-url "${TARGET_DLQ_URL}" \
    --attribute-names ApproximateNumberOfMessages \
    --region "${REGION}" \
    --output json 2>&1
)"; then
  fail_phase 1 "Unable to read DLQ attributes for '${TARGET_DLQ_URL}' - ${DLQ_ATTR_JSON}"
fi
DLQ_MESSAGES="$(jq -r '.Attributes.ApproximateNumberOfMessages // empty' <<<"${DLQ_ATTR_JSON}")"
is_nonnegative_int "${DLQ_MESSAGES}" || fail_phase 1 "DLQ ApproximateNumberOfMessages is not numeric ('${DLQ_MESSAGES:-empty}')"
[[ "${DLQ_MESSAGES}" == "0" ]] || fail_phase 1 "DLQ ApproximateNumberOfMessages=${DLQ_MESSAGES}, expected 0"

echo "[PASS Phase 1] Wiring verified"

# Phase 2 - Synthetic event injection
ALLOWLISTED_EVENT_NAME="$(extract_first_allowlisted_event_name || true)"
if [[ -z "${ALLOWLISTED_EVENT_NAME}" ]]; then
  fail_phase 2 "Could not determine allowlisted eventName from backend/services/control_plane_intake.py allowlist import"
fi

DETAIL_JSON="$(
  jq -cn \
    --arg eventName "${ALLOWLISTED_EVENT_NAME}" \
    --arg awsRegion "${REGION}" \
    --arg accountId "${ACCOUNT_ID}" \
    '{
      eventName: $eventName,
      eventCategory: "Management",
      awsRegion: $awsRegion,
      userIdentity: { accountId: $accountId }
    }'
)"

ENTRIES_JSON="$(
  jq -cn \
    --arg source "security.autopilot.synthetic" \
    --arg detailType "AWS API Call via CloudTrail" \
    --arg detail "${DETAIL_JSON}" \
    '[
      {
        Source: $source,
        DetailType: $detailType,
        Detail: $detail,
        EventBusName: "default"
      }
    ]'
)"

INJECTION_TIMESTAMP_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

PUT_EVENTS_JSON=""
if ! PUT_EVENTS_JSON="$(aws events put-events --entries "${ENTRIES_JSON}" --region "${REGION}" --output json 2>&1)"; then
  fail_phase 2 "put-events rejected - ${PUT_EVENTS_JSON}"
fi

FAILED_ENTRY_COUNT="$(jq -r '.FailedEntryCount // empty' <<<"${PUT_EVENTS_JSON}" 2>/dev/null || true)"
is_nonnegative_int "${FAILED_ENTRY_COUNT}" || fail_phase 2 "put-events response missing FailedEntryCount - ${PUT_EVENTS_JSON}"
if [[ "${FAILED_ENTRY_COUNT}" != "0" ]]; then
  PUT_EVENTS_ERROR="$(jq -r '(.Entries[0].ErrorCode // "UnknownError") + ": " + (.Entries[0].ErrorMessage // "unknown")' <<<"${PUT_EVENTS_JSON}" 2>/dev/null || true)"
  fail_phase 2 "put-events rejected - ${PUT_EVENTS_ERROR:-${PUT_EVENTS_JSON}}"
fi

echo "[PASS Phase 2] Synthetic event injected"

# Phase 3 - SaaS receipt poll
READINESS_URL="${SAAS_API_URL%/}/api/aws/accounts/${ACCOUNT_ID}/control-plane-readiness?stale_after_minutes=5"
PHASE3_DEADLINE_EPOCH=$(( $(date +%s) + 180 ))
PHASE3_LAST_REASON="Timed out waiting for readiness"

while true; do
  CURL_RESULT=""
  if ! CURL_RESULT="$(
    curl -sS --max-time 20 \
      -H "Authorization: Bearer ${SAAS_TOKEN}" \
      -H "Accept: application/json" \
      -w $'\n%{http_code}' \
      "${READINESS_URL}" 2>&1
  )"; then
    PHASE3_LAST_REASON="Readiness request failed - ${CURL_RESULT}"
  else
    HTTP_CODE="${CURL_RESULT##*$'\n'}"
    RESPONSE_BODY="${CURL_RESULT%$'\n'*}"

    if [[ "${HTTP_CODE}" == "200" ]]; then
      OVERALL_READY="$(jq -r '.overall_ready // false' <<<"${RESPONSE_BODY}" 2>/dev/null || echo "false")"
      REGION_IS_RECENT="$(
        jq -r --arg region "${REGION}" '
          [.regions[]? | select(.region == $region) | .is_recent][0] // false
        ' <<<"${RESPONSE_BODY}" 2>/dev/null || echo "false"
      )"
      if [[ "${OVERALL_READY}" == "true" && "${REGION_IS_RECENT}" == "true" ]]; then
        echo "[PASS Phase 3] SaaS received event — forwarder fully connected"
        exit 0
      fi
      PHASE3_LAST_REASON="Readiness not yet true (overall_ready=${OVERALL_READY}, ${REGION}.is_recent=${REGION_IS_RECENT})"
    else
      RESPONSE_DETAIL="$(jq -r '.detail // empty' <<<"${RESPONSE_BODY}" 2>/dev/null || true)"
      if [[ -n "${RESPONSE_DETAIL}" ]]; then
        PHASE3_LAST_REASON="Readiness endpoint HTTP ${HTTP_CODE} - ${RESPONSE_DETAIL}"
      else
        PHASE3_LAST_REASON="Readiness endpoint HTTP ${HTTP_CODE}"
      fi
    fi
  fi

  if [[ "$(date +%s)" -ge "${PHASE3_DEADLINE_EPOCH}" ]]; then
    break
  fi
  sleep 10
done

echo "[FAIL Phase 3: ${PHASE3_LAST_REASON}; proceeding to Phase 4 diagnosis]"

# Phase 4 - Timeout diagnosis
METRIC_END_TIME_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

MATCHED_RAW="$(get_rule_metric_sum "MatchedEvents" "${INJECTION_TIMESTAMP_UTC}" "${METRIC_END_TIME_UTC}" "${REGION}" "${RULE_NAME}")"
INVOCATIONS_RAW="$(get_rule_metric_sum "Invocations" "${INJECTION_TIMESTAMP_UTC}" "${METRIC_END_TIME_UTC}" "${REGION}" "${RULE_NAME}")"
FAILED_INVOCATIONS_RAW="$(get_rule_metric_sum "FailedInvocations" "${INJECTION_TIMESTAMP_UTC}" "${METRIC_END_TIME_UTC}" "${REGION}" "${RULE_NAME}")"

if [[ "${MATCHED_RAW}" == __ERROR__* ]]; then
  fail_phase 4 "Unable to read MatchedEvents metric - ${MATCHED_RAW#__ERROR__}"
fi
if [[ "${INVOCATIONS_RAW}" == __ERROR__* ]]; then
  fail_phase 4 "Unable to read Invocations metric - ${INVOCATIONS_RAW#__ERROR__}"
fi
if [[ "${FAILED_INVOCATIONS_RAW}" == __ERROR__* ]]; then
  fail_phase 4 "Unable to read FailedInvocations metric - ${FAILED_INVOCATIONS_RAW#__ERROR__}"
fi

MATCHED_EVENTS="$(to_int "${MATCHED_RAW}")"
INVOCATIONS="$(to_int "${INVOCATIONS_RAW}")"
FAILED_INVOCATIONS="$(to_int "${FAILED_INVOCATIONS_RAW}")"

DLQ_ATTR_JSON_PHASE4=""
if ! DLQ_ATTR_JSON_PHASE4="$(
  aws sqs get-queue-attributes \
    --queue-url "${TARGET_DLQ_URL}" \
    --attribute-names ApproximateNumberOfMessages \
    --region "${REGION}" \
    --output json 2>&1
)"; then
  fail_phase 4 "Unable to read DLQ attributes for '${TARGET_DLQ_URL}' - ${DLQ_ATTR_JSON_PHASE4}"
fi
DLQ_MESSAGES_PHASE4="$(jq -r '.Attributes.ApproximateNumberOfMessages // empty' <<<"${DLQ_ATTR_JSON_PHASE4}")"
is_nonnegative_int "${DLQ_MESSAGES_PHASE4}" || fail_phase 4 "DLQ ApproximateNumberOfMessages is not numeric ('${DLQ_MESSAGES_PHASE4:-empty}')"

if (( MATCHED_EVENTS == 0 )); then
  fail_phase 4 "Event did not match EventBridge rule pattern — check detail-type and eventName"
fi

if (( MATCHED_EVENTS > 0 && INVOCATIONS == 0 )); then
  fail_phase 4 "Rule matched but API destination was not invoked — check target configuration"
fi

if (( FAILED_INVOCATIONS > 0 )); then
  fail_phase 4 "API destination invocation failed — check connection auth token and SaaS endpoint reachability"
fi

if (( DLQ_MESSAGES_PHASE4 > 0 )); then
  fail_phase 4 "Events stuck in DLQ — delivery failed after retries"
fi

fail_phase 4 "SaaS intake received event but dropped it — account may not be registered or token is wrong. Check drop_reason in intake logs"
