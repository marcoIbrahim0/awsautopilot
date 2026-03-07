#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ID="${LIVE_E2E_RUN_ID:-20260228T220436Z}"
PREFIX_TIMESTAMP_INPUT="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
if [[ "${PREFIX_TIMESTAMP_INPUT}" != *Z ]]; then
  PREFIX_TIMESTAMP_INPUT="${PREFIX_TIMESTAMP_INPUT}Z"
fi
PREFIX="test-26-closure-${PREFIX_TIMESTAMP_INPUT}"

API_EVIDENCE_DIR="${ROOT_DIR}/docs/test-results/live-runs/${RUN_ID}/evidence/api"
AWS_EVIDENCE_DIR="${ROOT_DIR}/docs/test-results/live-runs/${RUN_ID}/evidence/aws"
UI_EVIDENCE_DIR="${ROOT_DIR}/docs/test-results/live-runs/${RUN_ID}/evidence/ui"
mkdir -p "${API_EVIDENCE_DIR}" "${AWS_EVIDENCE_DIR}" "${UI_EVIDENCE_DIR}"

API_BASE_URL="${API_BASE_URL:-https://api.ocypheris.com}"
UI_BASE_URL="${UI_BASE_URL:-https://dev.ocypheris.com}"
ADMIN_EMAIL="${TEST_ADMIN_EMAIL:-maromaher54@gmail.com}"
ADMIN_PASSWORD="${TEST_ADMIN_PASSWORD:-Maher730}"
AWS_PROFILE_NAME="${AWS_PROFILE:-default}"
ACCOUNT_ID="${TEST26_ACCOUNT_ID:-029037611564}"
AWS_REGION_NAME="${TEST26_REGION:-eu-north-1}"
TARGET_BUCKET="${TEST26_BUCKET:-arch1-bucket-evidence-b1-029037611564-eu-north-1}"
TARGET_RESOURCE_ID="arn:aws:s3:::${TARGET_BUCKET}"
TARGET_FINDING_HINT="${TEST26_FINDING_ID_HINT:-280fd5e2-6075-490f-913d-0ef52315a518}"
TARGET_ACTION_HINT="${TEST26_ACTION_ID_HINT:-26403d52-eff4-47ce-ab52-49bd237e72f5}"
STRATEGY_HINT="${TEST26_STRATEGY_ID:-s3_migrate_cloudfront_oac_private}"
VISIBILITY_SLA_SECONDS="${TEST26_VISIBILITY_SLA_SECONDS:-180}"
VISIBILITY_POLL_INTERVAL_SECONDS="${TEST26_VISIBILITY_POLL_INTERVAL_SECONDS:-15}"
VISIBILITY_MAX_POLLS="${TEST26_VISIBILITY_MAX_POLLS:-12}"
FINAL_STATUS_MAX_POLLS="${TEST26_FINAL_STATUS_MAX_POLLS:-30}"
FINAL_STATUS_POLL_INTERVAL_SECONDS="${TEST26_FINAL_STATUS_POLL_INTERVAL_SECONDS:-30}"
RUN_POLL_INTERVAL_SECONDS="${TEST26_RUN_POLL_INTERVAL_SECONDS:-5}"
RUN_MAX_POLLS="${TEST26_RUN_MAX_POLLS:-60}"

timestamp_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

write_file() {
  local path="$1"
  local content="$2"
  printf '%s\n' "${content}" > "${path}"
}

record_aws_json_allow_fail() {
  local step="$1"
  local label="$2"
  shift 2
  local base="${API_EVIDENCE_DIR}/${PREFIX}-${step}-${label}"
  write_file "${base}.request.txt" "AWS_PROFILE=${AWS_PROFILE_NAME} aws $*"
  local status=0
  if AWS_PROFILE="${AWS_PROFILE_NAME}" aws "$@" > "${base}.json" 2> "${base}.stderr"; then
    status=0
  else
    status=$?
  fi
  write_file "${base}.status" "${status}"
  timestamp_utc > "${base}.timestamp.txt"
  return "${status}"
}

record_aws_json_require_success() {
  local step="$1"
  local label="$2"
  shift 2
  if ! record_aws_json_allow_fail "${step}" "${label}" "$@"; then
    echo "AWS command failed for ${step}-${label}" >&2
    exit 1
  fi
}

record_http_json() {
  local step="$1"
  local label="$2"
  local method="$3"
  local url="$4"
  local token="${5:-}"
  local body="${6:-}"
  local base="${API_EVIDENCE_DIR}/${PREFIX}-${step}-${label}"
  local auth_line=""
  if [[ -n "${token}" ]]; then
    auth_line=$'\n'"Authorization: Bearer <valens_admin_token>"
  fi
  if [[ -n "${body}" ]]; then
    write_file "${base}.request.txt" "${method} ${url}${auth_line}"$'\n'"Body: ${body}"
    write_file "${base}.body.json" "${body}"
  else
    write_file "${base}.request.txt" "${method} ${url}${auth_line}"
  fi

  local curl_cmd=(
    curl
    -sS
    -X "${method}"
    "${url}"
    -H "accept: application/json"
    -o "${base}.json"
    -D "${base}.headers"
    -w "%{http_code}"
  )
  if [[ -n "${token}" ]]; then
    curl_cmd+=(-H "Authorization: Bearer ${token}")
  fi
  if [[ -n "${body}" ]]; then
    curl_cmd+=(-H "Content-Type: application/json" --data "${body}")
  fi

  local http_code
  http_code="$("${curl_cmd[@]}" 2> "${base}.curl.stderr" || true)"
  write_file "${base}.status" "${http_code}"
  timestamp_utc > "${base}.timestamp.txt"
}

record_http_binary() {
  local step="$1"
  local label="$2"
  local method="$3"
  local url="$4"
  local output_path="$5"
  local token="${6:-}"
  local base="${API_EVIDENCE_DIR}/${PREFIX}-${step}-${label}"
  local auth_line=""
  if [[ -n "${token}" ]]; then
    auth_line=$'\n'"Authorization: Bearer <valens_admin_token>"
  fi
  write_file "${base}.request.txt" "${method} ${url}${auth_line}"

  local curl_cmd=(
    curl
    -sS
    -X "${method}"
    "${url}"
    -o "${output_path}"
    -D "${base}.headers"
    -w "%{http_code}"
  )
  if [[ -n "${token}" ]]; then
    curl_cmd+=(-H "Authorization: Bearer ${token}")
  fi

  local http_code
  http_code="$("${curl_cmd[@]}" 2> "${base}.curl.stderr" || true)"
  write_file "${base}.status" "${http_code}"
  timestamp_utc > "${base}.timestamp.txt"
}

record_ui_page() {
  local label="$1"
  local url="$2"
  local base="${UI_EVIDENCE_DIR}/${PREFIX}-ui-${label}"
  write_file "${base}.request.txt" "GET ${url}"
  local http_code
  http_code="$(curl -sS "${url}" -o "${base}.html" -D "${base}.headers" -w "%{http_code}" 2> "${base}.curl.stderr" || true)"
  write_file "${base}.status" "${http_code}"
  timestamp_utc > "${base}.timestamp.txt"
}

run_terraform_step() {
  local step="$1"
  local label="$2"
  local workdir="$3"
  shift 3
  local out="${AWS_EVIDENCE_DIR}/${PREFIX}-${step}-${label}.out"
  local err="${AWS_EVIDENCE_DIR}/${PREFIX}-${step}-${label}.err"
  local status_file="${AWS_EVIDENCE_DIR}/${PREFIX}-${step}-${label}.status"
  set +e
  (
    cd "${workdir}"
    "$@"
  ) > "${out}" 2> "${err}"
  local status=$?
  set -e
  write_file "${status_file}" "${status}"
  return 0
}

echo "Using evidence prefix: ${PREFIX}"

record_aws_json_require_success "00" "aws-sts-caller-identity" sts get-caller-identity
record_aws_json_require_success "01" "aws-b1-bucket-tagging-pre" s3api get-bucket-tagging --bucket "${TARGET_BUCKET}"
record_aws_json_require_success "02" "aws-b1-bucket-policy-pre" s3api get-bucket-policy --bucket "${TARGET_BUCKET}"
record_aws_json_require_success "03" "aws-b1-policy-status-pre" s3api get-bucket-policy-status --bucket "${TARGET_BUCKET}"
record_aws_json_require_success "04" "aws-b1-public-access-block-pre" s3api get-public-access-block --bucket "${TARGET_BUCKET}"
record_aws_json_allow_fail "05" "aws-b1-website-config-pre-expected-error" s3api get-bucket-website --bucket "${TARGET_BUCKET}" || true

record_aws_json_require_success "06" "aws-b1-put-public-access-block-open" s3api put-public-access-block \
  --bucket "${TARGET_BUCKET}" \
  --public-access-block-configuration BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false
record_aws_json_require_success "07" "aws-b1-delete-website-config" s3api delete-bucket-website --bucket "${TARGET_BUCKET}"
record_aws_json_require_success "08" "aws-b1-public-access-block-confirm" s3api get-public-access-block --bucket "${TARGET_BUCKET}"
record_aws_json_require_success "09" "aws-b1-policy-status-confirm" s3api get-bucket-policy-status --bucket "${TARGET_BUCKET}"
record_aws_json_require_success "10" "aws-b1-bucket-policy-confirm" s3api get-bucket-policy --bucket "${TARGET_BUCKET}"
record_aws_json_allow_fail "11" "aws-b1-website-config-confirm-expected-error" s3api get-bucket-website --bucket "${TARGET_BUCKET}" || true
RESET_STATE_AT="$(timestamp_utc)"
RESET_STATE_EPOCH="$(date +%s)"
write_file "${API_EVIDENCE_DIR}/${PREFIX}-11b-reset-state-at.txt" "${RESET_STATE_AT}"

python3 - <<PY > "${API_EVIDENCE_DIR}/${PREFIX}-12-adversarial-state-summary.json"
import json
from backend.services.test26_assertions import build_precondition_risk_state

policy = json.loads(open("${API_EVIDENCE_DIR}/${PREFIX}-10-aws-b1-bucket-policy-confirm.json", "r", encoding="utf-8").read())
pab = json.loads(open("${API_EVIDENCE_DIR}/${PREFIX}-08-aws-b1-public-access-block-confirm.json", "r", encoding="utf-8").read())
policy_document_raw = policy.get("Policy")
policy_document = json.loads(policy_document_raw) if isinstance(policy_document_raw, str) else (policy_document_raw or {})
summary = build_precondition_risk_state(policy_document, pab)
summary.update(
    {
        "bucket": "${TARGET_BUCKET}",
        "tag_context_test": "existing-complex-policy",
        "pab_confirm": pab.get("PublicAccessBlockConfiguration", {}),
        "has_root_principal_statement": "arn:aws:iam::${ACCOUNT_ID}:root" in json.dumps(policy_document),
    }
)
print(json.dumps(summary, indent=2))
PY

if ! jq -e '.adversarial_state_confirmed == true' "${API_EVIDENCE_DIR}/${PREFIX}-12-adversarial-state-summary.json" >/dev/null; then
  echo "Deterministic adversarial precondition failed before open-visibility checks." >&2
  exit 1
fi

LOGIN_BODY="$(jq -n --arg email "${ADMIN_EMAIL}" --arg password "${ADMIN_PASSWORD}" '{email:$email,password:$password}')"
record_http_json "30" "login-admin" "POST" "${API_BASE_URL}/api/auth/login" "" "${LOGIN_BODY}"
if [[ "$(cat "${API_EVIDENCE_DIR}/${PREFIX}-30-login-admin.status")" != "200" ]]; then
  echo "Admin login failed for Test 26 run." >&2
  exit 1
fi
ADMIN_TOKEN="$(jq -r '.access_token // empty' "${API_EVIDENCE_DIR}/${PREFIX}-30-login-admin.json")"
if [[ -z "${ADMIN_TOKEN}" ]]; then
  echo "Missing access token after login." >&2
  exit 1
fi

record_http_json "31" "auth-me-admin" "GET" "${API_BASE_URL}/api/auth/me" "${ADMIN_TOKEN}"
record_http_json "32" "accounts-list" "GET" "${API_BASE_URL}/api/aws/accounts" "${ADMIN_TOKEN}"

PRE_REFRESH_STARTED_AFTER="$(timestamp_utc)"
write_file "${API_EVIDENCE_DIR}/${PREFIX}-33-pre-refresh-started-after.txt" "${PRE_REFRESH_STARTED_AFTER}"

record_http_json "34" "trigger-ingest-pre" "POST" "${API_BASE_URL}/api/aws/accounts/${ACCOUNT_ID}/ingest" "${ADMIN_TOKEN}" "{\"regions\":[\"${AWS_REGION_NAME}\"]}"
record_http_json "35" "trigger-actions-compute-pre" "POST" "${API_BASE_URL}/api/actions/compute" "${ADMIN_TOKEN}" "{\"account_id\":\"${ACCOUNT_ID}\",\"region\":\"${AWS_REGION_NAME}\"}"
record_http_json "35b" "trigger-actions-reconcile-pre" "POST" "${API_BASE_URL}/api/actions/reconcile" "${ADMIN_TOKEN}" "{\"account_id\":\"${ACCOUNT_ID}\",\"region\":\"${AWS_REGION_NAME}\"}"

OPEN_QUERY_URL="${API_BASE_URL}/api/actions?action_type=s3_bucket_block_public_access&control_id=S3.2&status=open&account_id=${ACCOUNT_ID}&region=${AWS_REGION_NAME}&limit=200"
RESOLVED_QUERY_URL="${API_BASE_URL}/api/actions?action_type=s3_bucket_block_public_access&control_id=S3.2&status=resolved&account_id=${ACCOUNT_ID}&region=${AWS_REGION_NAME}&limit=200"
TARGET_ACTION_ID=""
TARGET_VISIBLE_IN_OPEN=false
VISIBILITY_STARTED_EPOCH="$(date +%s)"
TARGET_ACTION_FIRST_OPEN_AT=""
TARGET_ACTION_FIRST_OPEN_ELAPSED_SECONDS=""
TARGET_FINDING_EFFECTIVE_OPEN=false
TARGET_FINDING_EFFECTIVE_OPEN_AT=""
TARGET_FINDING_EFFECTIVE_OPEN_ELAPSED_SECONDS=""
TARGET_FINDING_LAST_EFFECTIVE_STATUS=""
TARGET_FINDING_LAST_CANONICAL_STATUS=""
TARGET_FINDING_LAST_SHADOW_STATUS=""
TARGET_OPEN_ACTION_IDS_FOR_TARGET=""
TARGET_RESOLVED_ACTION_IDS_FOR_TARGET=""
for poll in $(seq 1 "${VISIBILITY_MAX_POLLS}"); do
  record_http_json "36" "actions-open-s3-2-poll-${poll}" "GET" "${OPEN_QUERY_URL}" "${ADMIN_TOKEN}"
  if [[ -n "${TARGET_FINDING_HINT}" ]]; then
    record_http_json "36f" "target-finding-detail-pre-poll-${poll}" "GET" "${API_BASE_URL}/api/findings/${TARGET_FINDING_HINT}" "${ADMIN_TOKEN}"
    TARGET_FINDING_LAST_EFFECTIVE_STATUS="$(jq -r '(.effective_status // .status // "") | ascii_upcase' "${API_EVIDENCE_DIR}/${PREFIX}-36f-target-finding-detail-pre-poll-${poll}.json")"
    TARGET_FINDING_LAST_CANONICAL_STATUS="$(jq -r '(.canonical_status // "") | ascii_upcase' "${API_EVIDENCE_DIR}/${PREFIX}-36f-target-finding-detail-pre-poll-${poll}.json")"
    TARGET_FINDING_LAST_SHADOW_STATUS="$(jq -r '((.shadow // {}) | .status_normalized // "") | ascii_upcase' "${API_EVIDENCE_DIR}/${PREFIX}-36f-target-finding-detail-pre-poll-${poll}.json")"
    if [[ "${TARGET_FINDING_EFFECTIVE_OPEN}" == "false" && "${TARGET_FINDING_LAST_EFFECTIVE_STATUS}" != "RESOLVED" ]]; then
      TARGET_FINDING_EFFECTIVE_OPEN=true
      TARGET_FINDING_EFFECTIVE_OPEN_AT="$(timestamp_utc)"
      TARGET_FINDING_EFFECTIVE_OPEN_ELAPSED_SECONDS="$(( $(date +%s) - RESET_STATE_EPOCH ))"
    fi
  fi
  TARGET_OPEN_ACTION_IDS_FOR_TARGET="$(jq -r --arg resource_id "${TARGET_RESOURCE_ID}" '.items[]? | select(.resource_id == $resource_id) | .id' "${API_EVIDENCE_DIR}/${PREFIX}-36-actions-open-s3-2-poll-${poll}.json" | paste -sd ',' -)"
  TARGET_ACTION_ID="$(jq -r --arg resource_id "${TARGET_RESOURCE_ID}" '.items[]? | select(.resource_id == $resource_id) | .id' "${API_EVIDENCE_DIR}/${PREFIX}-36-actions-open-s3-2-poll-${poll}.json" | head -n 1)"
  if [[ -n "${TARGET_ACTION_ID}" ]]; then
    TARGET_VISIBLE_IN_OPEN=true
    TARGET_ACTION_FIRST_OPEN_AT="$(timestamp_utc)"
    TARGET_ACTION_FIRST_OPEN_ELAPSED_SECONDS="$(( $(date +%s) - RESET_STATE_EPOCH ))"
    break
  fi
  sleep "${VISIBILITY_POLL_INTERVAL_SECONDS}"
done
VISIBILITY_ELAPSED_SECONDS="$(( $(date +%s) - VISIBILITY_STARTED_EPOCH ))"

if [[ -z "${TARGET_ACTION_ID}" ]]; then
  record_http_json "36" "actions-resolved-s3-2-fallback" "GET" "${RESOLVED_QUERY_URL}" "${ADMIN_TOKEN}"
  TARGET_RESOLVED_ACTION_IDS_FOR_TARGET="$(jq -r --arg resource_id "${TARGET_RESOURCE_ID}" '.items[]? | select(.resource_id == $resource_id) | .id' "${API_EVIDENCE_DIR}/${PREFIX}-36-actions-resolved-s3-2-fallback.json" | paste -sd ',' -)"
  TARGET_ACTION_ID="$(jq -r --arg resource_id "${TARGET_RESOURCE_ID}" '.items[]? | select(.resource_id == $resource_id) | .id' "${API_EVIDENCE_DIR}/${PREFIX}-36-actions-resolved-s3-2-fallback.json" | head -n 1)"
fi
if [[ -z "${TARGET_ACTION_ID}" ]]; then
  TARGET_ACTION_ID="${TARGET_ACTION_HINT}"
fi
write_file "${API_EVIDENCE_DIR}/${PREFIX}-37-target-action-id.txt" "${TARGET_ACTION_ID}"

record_http_json "39" "findings-new-s3-2-pre" "GET" "${API_BASE_URL}/api/findings?control_id=S3.2&status=NEW&account_id=${ACCOUNT_ID}&region=${AWS_REGION_NAME}&limit=200" "${ADMIN_TOKEN}"
TARGET_FINDING_ID_PRIMARY="${TARGET_FINDING_HINT}"
if [[ -z "${TARGET_FINDING_ID_PRIMARY}" ]]; then
  TARGET_FINDING_ID_PRIMARY="$(jq -r '.items[0].id // empty' "${API_EVIDENCE_DIR}/${PREFIX}-39-findings-new-s3-2-pre.json")"
fi
write_file "${API_EVIDENCE_DIR}/${PREFIX}-40-target-finding-id-primary.txt" "${TARGET_FINDING_ID_PRIMARY}"

record_http_json "42" "remediation-options-target" "GET" "${API_BASE_URL}/api/actions/${TARGET_ACTION_ID}/remediation-options" "${ADMIN_TOKEN}"
record_http_json "43" "remediation-options-target-noauth" "GET" "${API_BASE_URL}/api/actions/${TARGET_ACTION_ID}/remediation-options" ""
TARGET_STRATEGY_ID="$(jq -r --arg strategy "${STRATEGY_HINT}" '.strategies[]? | select(.strategy_id == $strategy) | .strategy_id' "${API_EVIDENCE_DIR}/${PREFIX}-42-remediation-options-target.json" | head -n 1)"
if [[ -z "${TARGET_STRATEGY_ID}" ]]; then
  TARGET_STRATEGY_ID="$(jq -r '.strategies[]? | select(.recommended == true) | .strategy_id' "${API_EVIDENCE_DIR}/${PREFIX}-42-remediation-options-target.json" | head -n 1)"
fi
if [[ -z "${TARGET_STRATEGY_ID}" ]]; then
  TARGET_STRATEGY_ID="${STRATEGY_HINT}"
fi
write_file "${API_EVIDENCE_DIR}/${PREFIX}-44-target-strategy-id.txt" "${TARGET_STRATEGY_ID}"

RUN_CREATE_BODY="$(jq -n --arg action_id "${TARGET_ACTION_ID}" --arg strategy_id "${TARGET_STRATEGY_ID}" '{action_id:$action_id,mode:"pr_only",strategy_id:$strategy_id}')"
record_http_json "45" "create-run-target-pr-noauth" "POST" "${API_BASE_URL}/api/remediation-runs" "" "${RUN_CREATE_BODY}"
record_http_json "46" "create-run-target-pr-noack" "POST" "${API_BASE_URL}/api/remediation-runs" "${ADMIN_TOKEN}" "${RUN_CREATE_BODY}"
if [[ "$(cat "${API_EVIDENCE_DIR}/${PREFIX}-46-create-run-target-pr-noack.status")" != "201" ]]; then
  echo "Failed to create remediation run for Test 26." >&2
  exit 1
fi
REMEDIATION_RUN_ID="$(jq -r '.id // empty' "${API_EVIDENCE_DIR}/${PREFIX}-46-create-run-target-pr-noack.json")"
if [[ -z "${REMEDIATION_RUN_ID}" ]]; then
  echo "Could not extract remediation run ID." >&2
  exit 1
fi
write_file "${API_EVIDENCE_DIR}/${PREFIX}-48-remediation-run-id.txt" "${REMEDIATION_RUN_ID}"

RUN_FINAL_STATUS=""
LAST_RUN_POLL=1
for poll in $(seq 1 "${RUN_MAX_POLLS}"); do
  LAST_RUN_POLL="${poll}"
  record_http_json "49" "run-detail-poll-${poll}" "GET" "${API_BASE_URL}/api/remediation-runs/${REMEDIATION_RUN_ID}" "${ADMIN_TOKEN}"
  record_http_json "50" "run-execution-poll-${poll}" "GET" "${API_BASE_URL}/api/remediation-runs/${REMEDIATION_RUN_ID}/execution" "${ADMIN_TOKEN}"
  RUN_FINAL_STATUS="$(jq -r '.status // empty' "${API_EVIDENCE_DIR}/${PREFIX}-49-run-detail-poll-${poll}.json")"
  if [[ "${RUN_FINAL_STATUS}" == "success" || "${RUN_FINAL_STATUS}" == "failed" || "${RUN_FINAL_STATUS}" == "cancelled" ]]; then
    break
  fi
  sleep "${RUN_POLL_INTERVAL_SECONDS}"
done
cp "${API_EVIDENCE_DIR}/${PREFIX}-49-run-detail-poll-${LAST_RUN_POLL}.json" "${API_EVIDENCE_DIR}/${PREFIX}-51-run-detail-final.json"
cp "${API_EVIDENCE_DIR}/${PREFIX}-50-run-execution-poll-${LAST_RUN_POLL}.json" "${API_EVIDENCE_DIR}/${PREFIX}-52-run-execution-final.json"
write_file "${API_EVIDENCE_DIR}/${PREFIX}-53-run-final-status.txt" "${RUN_FINAL_STATUS}"

BUNDLE_ZIP="${AWS_EVIDENCE_DIR}/${PREFIX}-54-pr-bundle.zip"
record_http_binary "54" "pr-bundle-download-authorized" "GET" "${API_BASE_URL}/api/remediation-runs/${REMEDIATION_RUN_ID}/pr-bundle.zip" "${BUNDLE_ZIP}" "${ADMIN_TOKEN}"
record_http_json "55" "pr-bundle-download-noauth" "GET" "${API_BASE_URL}/api/remediation-runs/${REMEDIATION_RUN_ID}/pr-bundle.zip" ""

BUNDLE_DIR="${AWS_EVIDENCE_DIR}/${PREFIX}-bundle"
rm -rf "${BUNDLE_DIR}"
mkdir -p "${BUNDLE_DIR}"
write_file "${AWS_EVIDENCE_DIR}/${PREFIX}-56-unzip-pr-bundle.request.txt" "unzip -o ${BUNDLE_ZIP} -d ${BUNDLE_DIR}"
set +e
unzip -o "${BUNDLE_ZIP}" -d "${BUNDLE_DIR}" > "${AWS_EVIDENCE_DIR}/${PREFIX}-56-unzip-pr-bundle.out" 2> "${AWS_EVIDENCE_DIR}/${PREFIX}-56-unzip-pr-bundle.stderr"
UNZIP_STATUS=$?
set -e
write_file "${AWS_EVIDENCE_DIR}/${PREFIX}-56-unzip-pr-bundle.status" "${UNZIP_STATUS}"
timestamp_utc > "${AWS_EVIDENCE_DIR}/${PREFIX}-56-unzip-pr-bundle.timestamp.txt"

write_file "${AWS_EVIDENCE_DIR}/${PREFIX}-57-bundle-file-tree.request.txt" "find ${BUNDLE_DIR} -maxdepth 3 -type f | sort"
set +e
find "${BUNDLE_DIR}" -maxdepth 3 -type f | sort > "${AWS_EVIDENCE_DIR}/${PREFIX}-57-bundle-file-tree.out" 2> "${AWS_EVIDENCE_DIR}/${PREFIX}-57-bundle-file-tree.stderr"
TREE_STATUS=$?
set -e
write_file "${AWS_EVIDENCE_DIR}/${PREFIX}-57-bundle-file-tree.status" "${TREE_STATUS}"
timestamp_utc > "${AWS_EVIDENCE_DIR}/${PREFIX}-57-bundle-file-tree.timestamp.txt"
write_file "${AWS_EVIDENCE_DIR}/${PREFIX}-58-terraform-root.txt" "${BUNDLE_DIR}"

record_aws_json_require_success "59" "aws-b1-bucket-policy-pre-apply" s3api get-bucket-policy --bucket "${TARGET_BUCKET}"
record_aws_json_require_success "60" "aws-b1-policy-status-pre-apply" s3api get-bucket-policy-status --bucket "${TARGET_BUCKET}"
record_aws_json_require_success "61" "aws-b1-public-access-block-pre-apply" s3api get-public-access-block --bucket "${TARGET_BUCKET}"

run_terraform_step "70" "terraform-init" "${BUNDLE_DIR}" terraform init -no-color
run_terraform_step "71" "terraform-plan" "${BUNDLE_DIR}" terraform plan -no-color -out tfplan
run_terraform_step "72" "terraform-show" "${BUNDLE_DIR}" terraform show -no-color tfplan
run_terraform_step "73" "terraform-apply" "${BUNDLE_DIR}" terraform apply -no-color -auto-approve tfplan

record_aws_json_require_success "74" "aws-b1-bucket-policy-post-apply" s3api get-bucket-policy --bucket "${TARGET_BUCKET}"
record_aws_json_require_success "75" "aws-b1-policy-status-post-apply" s3api get-bucket-policy-status --bucket "${TARGET_BUCKET}"
record_aws_json_require_success "76" "aws-b1-public-access-block-post-apply" s3api get-public-access-block --bucket "${TARGET_BUCKET}"

python3 - <<PY > "${AWS_EVIDENCE_DIR}/${PREFIX}-77-policy-preservation-summary.json"
import json
pre_policy = json.loads(open("${API_EVIDENCE_DIR}/${PREFIX}-59-aws-b1-bucket-policy-pre-apply.json", "r", encoding="utf-8").read())
post_policy = json.loads(open("${API_EVIDENCE_DIR}/${PREFIX}-74-aws-b1-bucket-policy-post-apply.json", "r", encoding="utf-8").read())
post_pab = json.loads(open("${API_EVIDENCE_DIR}/${PREFIX}-76-aws-b1-public-access-block-post-apply.json", "r", encoding="utf-8").read())
pre_policy_doc = json.loads(pre_policy.get("Policy")) if isinstance(pre_policy.get("Policy"), str) else (pre_policy.get("Policy") or {})
post_policy_doc = json.loads(post_policy.get("Policy")) if isinstance(post_policy.get("Policy"), str) else (post_policy.get("Policy") or {})
pab_cfg = (post_pab or {}).get("PublicAccessBlockConfiguration") or {}
summary = {
    "policy_preservation_pass": pre_policy_doc == post_policy_doc,
    "statements_unchanged": pre_policy_doc == post_policy_doc,
    "pre_statement_count": len(pre_policy_doc.get("Statement") or []),
    "post_statement_count": len(post_policy_doc.get("Statement") or []),
    "pab_hardened_post_apply": all(
        pab_cfg.get(k) is True for k in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")
    ),
}
print(json.dumps(summary, indent=2))
PY

write_file "${AWS_EVIDENCE_DIR}/${PREFIX}-78-policy-preservation-delta-summary.request.txt" "python3: summarize_policy_preservation(pre_policy, post_policy, post_pab)"
python3 - <<PY > "${AWS_EVIDENCE_DIR}/${PREFIX}-78-policy-preservation-delta-summary.json"
import json
from backend.services.test26_assertions import summarize_policy_preservation

pre_policy = json.loads(open("${API_EVIDENCE_DIR}/${PREFIX}-59-aws-b1-bucket-policy-pre-apply.json", "r", encoding="utf-8").read())
post_policy = json.loads(open("${API_EVIDENCE_DIR}/${PREFIX}-74-aws-b1-bucket-policy-post-apply.json", "r", encoding="utf-8").read())
post_pab = json.loads(open("${API_EVIDENCE_DIR}/${PREFIX}-76-aws-b1-public-access-block-post-apply.json", "r", encoding="utf-8").read())
pre_policy_doc = json.loads(pre_policy.get("Policy")) if isinstance(pre_policy.get("Policy"), str) else (pre_policy.get("Policy") or {})
post_policy_doc = json.loads(post_policy.get("Policy")) if isinstance(post_policy.get("Policy"), str) else (post_policy.get("Policy") or {})
summary = summarize_policy_preservation(pre_policy_doc, post_policy_doc, post_pab)
summary.update(
    {
        "pre_statement_count": len(pre_policy_doc.get("Statement") or []),
        "post_statement_count": len(post_policy_doc.get("Statement") or []),
    }
)
print(json.dumps(summary, indent=2))
PY
write_file "${AWS_EVIDENCE_DIR}/${PREFIX}-78-policy-preservation-delta-summary.status" "0"
timestamp_utc > "${AWS_EVIDENCE_DIR}/${PREFIX}-78-policy-preservation-delta-summary.timestamp.txt"

POST_REFRESH_STARTED_AFTER="$(timestamp_utc)"
write_file "${API_EVIDENCE_DIR}/${PREFIX}-90-post-refresh-started-after.txt" "${POST_REFRESH_STARTED_AFTER}"
record_http_json "91" "trigger-ingest-post-apply" "POST" "${API_BASE_URL}/api/aws/accounts/${ACCOUNT_ID}/ingest" "${ADMIN_TOKEN}" "{\"regions\":[\"${AWS_REGION_NAME}\"]}"
record_http_json "92" "trigger-actions-compute-post-apply" "POST" "${API_BASE_URL}/api/actions/compute" "${ADMIN_TOKEN}" "{\"account_id\":\"${ACCOUNT_ID}\",\"region\":\"${AWS_REGION_NAME}\"}"
record_http_json "93" "trigger-actions-reconcile-post-apply" "POST" "${API_BASE_URL}/api/actions/reconcile" "${ADMIN_TOKEN}" "{\"account_id\":\"${ACCOUNT_ID}\",\"region\":\"${AWS_REGION_NAME}\"}"

REFRESH_DONE=false
for poll in $(seq 1 30); do
  record_http_json "94" "ingest-progress-poll-${poll}" "GET" "${API_BASE_URL}/api/aws/accounts/${ACCOUNT_ID}/ingest-progress?started_after=${POST_REFRESH_STARTED_AFTER}" "${ADMIN_TOKEN}"
  refresh_status="$(jq -r '.status // empty' "${API_EVIDENCE_DIR}/${PREFIX}-94-ingest-progress-poll-${poll}.json")"
  if [[ "${refresh_status}" == "completed" ]]; then
    REFRESH_DONE=true
    break
  fi
  sleep 10
done

TARGET_ACTION_FINAL_STATUS=""
TARGET_IN_OPEN_LIST=false
TARGET_IN_RESOLVED_LIST=false
TARGET_FINDING_IN_NEW=false
TARGET_FINDING_IN_RESOLVED=false
LAST_FINAL_POLL=1
for poll in $(seq 1 "${FINAL_STATUS_MAX_POLLS}"); do
  LAST_FINAL_POLL="${poll}"
  record_http_json "95" "target-action-detail-poll-${poll}" "GET" "${API_BASE_URL}/api/actions/${TARGET_ACTION_ID}" "${ADMIN_TOKEN}"
  record_http_json "96" "actions-open-s3-2-poll-${poll}" "GET" "${OPEN_QUERY_URL}" "${ADMIN_TOKEN}"
  record_http_json "97" "actions-resolved-s3-2-poll-${poll}" "GET" "${RESOLVED_QUERY_URL}" "${ADMIN_TOKEN}"
  record_http_json "98" "findings-new-s3-2-poll-${poll}" "GET" "${API_BASE_URL}/api/findings?control_id=S3.2&status=NEW&account_id=${ACCOUNT_ID}&region=${AWS_REGION_NAME}&limit=200" "${ADMIN_TOKEN}"
  record_http_json "99" "findings-resolved-s3-2-poll-${poll}" "GET" "${API_BASE_URL}/api/findings?control_id=S3.2&status=RESOLVED&account_id=${ACCOUNT_ID}&region=${AWS_REGION_NAME}&limit=200" "${ADMIN_TOKEN}"

  TARGET_ACTION_FINAL_STATUS="$(jq -r '.status // empty' "${API_EVIDENCE_DIR}/${PREFIX}-95-target-action-detail-poll-${poll}.json")"
  TARGET_IN_OPEN_LIST="$(jq -e --arg action_id "${TARGET_ACTION_ID}" '.items[]? | select(.id == $action_id)' "${API_EVIDENCE_DIR}/${PREFIX}-96-actions-open-s3-2-poll-${poll}.json" >/dev/null && echo true || echo false)"
  TARGET_IN_RESOLVED_LIST="$(jq -e --arg action_id "${TARGET_ACTION_ID}" '.items[]? | select(.id == $action_id)' "${API_EVIDENCE_DIR}/${PREFIX}-97-actions-resolved-s3-2-poll-${poll}.json" >/dev/null && echo true || echo false)"
  TARGET_FINDING_IN_NEW="$(jq -e --arg finding_id "${TARGET_FINDING_ID_PRIMARY}" '.items[]? | select(.id == $finding_id)' "${API_EVIDENCE_DIR}/${PREFIX}-98-findings-new-s3-2-poll-${poll}.json" >/dev/null && echo true || echo false)"
  TARGET_FINDING_IN_RESOLVED="$(jq -e --arg finding_id "${TARGET_FINDING_ID_PRIMARY}" '.items[]? | select(.id == $finding_id)' "${API_EVIDENCE_DIR}/${PREFIX}-99-findings-resolved-s3-2-poll-${poll}.json" >/dev/null && echo true || echo false)"

  if [[ "${TARGET_ACTION_FINAL_STATUS}" == "resolved" && "${TARGET_FINDING_IN_RESOLVED}" == "true" ]]; then
    break
  fi
  sleep "${FINAL_STATUS_POLL_INTERVAL_SECONDS}"
done

cp "${API_EVIDENCE_DIR}/${PREFIX}-95-target-action-detail-poll-${LAST_FINAL_POLL}.json" "${API_EVIDENCE_DIR}/${PREFIX}-110-target-action-detail-final.json"
cp "${API_EVIDENCE_DIR}/${PREFIX}-96-actions-open-s3-2-poll-${LAST_FINAL_POLL}.json" "${API_EVIDENCE_DIR}/${PREFIX}-111-actions-open-s3-2-final.json"
cp "${API_EVIDENCE_DIR}/${PREFIX}-97-actions-resolved-s3-2-poll-${LAST_FINAL_POLL}.json" "${API_EVIDENCE_DIR}/${PREFIX}-112-actions-resolved-s3-2-final.json"
cp "${API_EVIDENCE_DIR}/${PREFIX}-98-findings-new-s3-2-poll-${LAST_FINAL_POLL}.json" "${API_EVIDENCE_DIR}/${PREFIX}-113-findings-new-s3-2-final.json"
cp "${API_EVIDENCE_DIR}/${PREFIX}-99-findings-resolved-s3-2-poll-${LAST_FINAL_POLL}.json" "${API_EVIDENCE_DIR}/${PREFIX}-114-findings-resolved-s3-2-final.json"

record_aws_json_require_success "115" "runtime-stack-version" cloudformation describe-stacks \
  --stack-name security-autopilot-saas-serverless-runtime \
  --region "${AWS_REGION_NAME}" \
  --query 'Stacks[0].{LastUpdatedTime:LastUpdatedTime,ApiImage:(Parameters[?ParameterKey==`ApiImageUri`].ParameterValue|[0]),WorkerImage:(Parameters[?ParameterKey==`WorkerImageUri`].ParameterValue|[0])}' \
  --output json

record_http_json "116" "target-finding-detail-final" "GET" "${API_BASE_URL}/api/findings/${TARGET_FINDING_ID_PRIMARY}" "${ADMIN_TOKEN}"

LINKED_FINDINGS_FILE="${API_EVIDENCE_DIR}/${PREFIX}-117-linked-findings-detail.ndjson"
: > "${LINKED_FINDINGS_FILE}"
for finding_id in $(jq -r '.findings[]?.id' "${API_EVIDENCE_DIR}/${PREFIX}-110-target-action-detail-final.json"); do
  record_http_json "117" "linked-finding-${finding_id}" "GET" "${API_BASE_URL}/api/findings/${finding_id}" "${ADMIN_TOKEN}"
  cat "${API_EVIDENCE_DIR}/${PREFIX}-117-linked-finding-${finding_id}.json" >> "${LINKED_FINDINGS_FILE}"
  printf '\n' >> "${LINKED_FINDINGS_FILE}"
done

write_file "${API_EVIDENCE_DIR}/${PREFIX}-117-linked-findings-shadow-summary.request.txt" "python3: summarize linked finding status/effective/shadow alignment"
python3 - <<PY > "${API_EVIDENCE_DIR}/${PREFIX}-117-linked-findings-shadow-summary.json"
import json
from pathlib import Path

ndjson_path = Path("${LINKED_FINDINGS_FILE}")
rows = []
for line in ndjson_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    rows.append(json.loads(line))

resolved_by_status = 0
resolved_by_effective = 0
resolved_by_shadow = 0
canonical_new = 0
for row in rows:
    status = str(row.get("status") or "").upper()
    effective = str(row.get("effective_status") or "").upper()
    canonical = str(row.get("canonical_status") or "").upper()
    shadow_norm = str((row.get("shadow") or {}).get("status_normalized") or "").upper()
    if status == "RESOLVED":
        resolved_by_status += 1
    if effective == "RESOLVED":
        resolved_by_effective += 1
    if shadow_norm == "RESOLVED":
        resolved_by_shadow += 1
    if canonical == "NEW":
        canonical_new += 1

summary = {
    "linked_finding_count": len(rows),
    "resolved_by_status_count": resolved_by_status,
    "resolved_by_effective_count": resolved_by_effective,
    "resolved_by_shadow_count": resolved_by_shadow,
    "canonical_new_count": canonical_new,
}
print(json.dumps(summary, indent=2))
PY
write_file "${API_EVIDENCE_DIR}/${PREFIX}-117-linked-findings-shadow-summary.status" "0"
timestamp_utc > "${API_EVIDENCE_DIR}/${PREFIX}-117-linked-findings-shadow-summary.timestamp.txt"

record_ui_page "01-actions-route-no-auth" "${UI_BASE_URL}/actions"

TF_INIT_STATUS="$(cat "${AWS_EVIDENCE_DIR}/${PREFIX}-70-terraform-init.status")"
TF_PLAN_STATUS="$(cat "${AWS_EVIDENCE_DIR}/${PREFIX}-71-terraform-plan.status")"
TF_SHOW_STATUS="$(cat "${AWS_EVIDENCE_DIR}/${PREFIX}-72-terraform-show.status")"
TF_APPLY_STATUS="$(cat "${AWS_EVIDENCE_DIR}/${PREFIX}-73-terraform-apply.status")"
NON_RISK_INVARIANCE_PASS="$(jq -r '.non_risk_invariance_pass' "${AWS_EVIDENCE_DIR}/${PREFIX}-78-policy-preservation-delta-summary.json")"
PAB_HARDENED_POST_APPLY="$(jq -r '.pab_hardened_post_apply' "${AWS_EVIDENCE_DIR}/${PREFIX}-78-policy-preservation-delta-summary.json")"

python3 - <<PY > "${API_EVIDENCE_DIR}/${PREFIX}-99-summary.json"
import json
from backend.services.test26_assertions import evaluate_visibility_track

def as_bool(value: str) -> bool:
    return str(value).strip().lower() == "true"

def as_optional_int(value: str):
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except Exception:
        return None

def csv_ids(value: str):
    text = str(value).strip()
    if not text:
        return []
    return [v for v in text.split(",") if v]

track2 = evaluate_visibility_track(
    target_visible_in_open=as_bool("${TARGET_VISIBLE_IN_OPEN}"),
    elapsed_seconds=int("${VISIBILITY_ELAPSED_SECONDS}"),
    sla_seconds=int("${VISIBILITY_SLA_SECONDS}"),
)

track1_checks = {
    "run_success": "${RUN_FINAL_STATUS}" == "success",
    "terraform_success": all(int(v) == 0 for v in ["${TF_INIT_STATUS}", "${TF_PLAN_STATUS}", "${TF_SHOW_STATUS}", "${TF_APPLY_STATUS}"]),
    "action_resolved": "${TARGET_ACTION_FINAL_STATUS}" == "resolved",
    "finding_resolved": as_bool("${TARGET_FINDING_IN_RESOLVED}"),
    "policy_non_risk_invariance": as_bool("${NON_RISK_INVARIANCE_PASS}"),
    "refresh_done_before_timeout": as_bool("${REFRESH_DONE}"),
}
track1_pass = all(track1_checks.values())
track1_reason = "all_blocking_checks_passed" if track1_pass else "blocking_check_failed"

summary = {
    "prefix": "${PREFIX}",
    "bucket": "${TARGET_BUCKET}",
    "reset_state_at": "${RESET_STATE_AT}",
    "target_action_id": "${TARGET_ACTION_ID}",
    "target_finding_id_primary": "${TARGET_FINDING_ID_PRIMARY}",
    "remediation_run_id": "${REMEDIATION_RUN_ID}",
    "remediation_run_final_status": "${RUN_FINAL_STATUS}",
    "final_action_status": "${TARGET_ACTION_FINAL_STATUS}",
    "target_in_open_list": as_bool("${TARGET_IN_OPEN_LIST}"),
    "target_in_resolved_list": as_bool("${TARGET_IN_RESOLVED_LIST}"),
    "target_finding_in_new_final": as_bool("${TARGET_FINDING_IN_NEW}"),
    "target_finding_in_resolved_final": as_bool("${TARGET_FINDING_IN_RESOLVED}"),
    "refresh_done_before_timeout": as_bool("${REFRESH_DONE}"),
    "closure_result": {
        "action_resolved": "${TARGET_ACTION_FINAL_STATUS}" == "resolved",
        "finding_resolved": as_bool("${TARGET_FINDING_IN_RESOLVED}"),
    },
    "policy_preservation_result": {
        "statements_unchanged": as_bool("${NON_RISK_INVARIANCE_PASS}"),
        "pab_hardened_post_apply": as_bool("${PAB_HARDENED_POST_APPLY}"),
    },
    "terraform_exit_codes": {
        "init": int("${TF_INIT_STATUS}"),
        "plan": int("${TF_PLAN_STATUS}"),
        "show": int("${TF_SHOW_STATUS}"),
        "apply": int("${TF_APPLY_STATUS}"),
    },
    "track_1_blocking": {
        "pass": track1_pass,
        "reason": track1_reason,
        "checks": track1_checks,
    },
    "track_2_visibility": track2,
    "pre_run_visibility_diagnostics": {
        "target_open_action_ids_seen_last_poll": csv_ids("${TARGET_OPEN_ACTION_IDS_FOR_TARGET}"),
        "target_resolved_action_ids_fallback": csv_ids("${TARGET_RESOLVED_ACTION_IDS_FOR_TARGET}"),
        "target_action_first_open_at": "${TARGET_ACTION_FIRST_OPEN_AT}" or None,
        "target_action_first_open_elapsed_from_reset_seconds": as_optional_int("${TARGET_ACTION_FIRST_OPEN_ELAPSED_SECONDS}"),
        "target_finding_effective_open_seen": as_bool("${TARGET_FINDING_EFFECTIVE_OPEN}"),
        "target_finding_effective_open_at": "${TARGET_FINDING_EFFECTIVE_OPEN_AT}" or None,
        "target_finding_effective_open_elapsed_from_reset_seconds": as_optional_int("${TARGET_FINDING_EFFECTIVE_OPEN_ELAPSED_SECONDS}"),
        "target_finding_last_effective_status": "${TARGET_FINDING_LAST_EFFECTIVE_STATUS}" or None,
        "target_finding_last_canonical_status": "${TARGET_FINDING_LAST_CANONICAL_STATUS}" or None,
        "target_finding_last_shadow_status": "${TARGET_FINDING_LAST_SHADOW_STATUS}" or None,
    },
}
print(json.dumps(summary, indent=2))
PY

echo "Wave 7 Test 26 run complete."
echo "Prefix: ${PREFIX}"
echo "Summary: ${API_EVIDENCE_DIR}/${PREFIX}-99-summary.json"
