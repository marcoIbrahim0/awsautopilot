#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=<REDACTED_TOKEN>
STARTED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"688f5ed0-9594-4df1-9883-cc17feca62f8","execution_status":"success"},{"action_id":"0b87839b-28f5-4150-af26-74cf2b1af3a3","execution_status":"success"}],"non_executable_results":[{"action_id":"352ac9b2-d343-40ac-b427-4c4f285615ef","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access."]},{"action_id":"08a9f629-3bfa-46a1-bd88-e22027f7e133","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled.","Missing bucket identifier for access-path validation."]},{"action_id":"e88846fa-71d2-4291-ae12-2c13b1b49544","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled."]},{"action_id":"7522bc9f-5cab-4bad-908b-a382045f8d87","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled."]},{"action_id":"4a965fac-c139-46e3-8594-11058b1dfe24","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled."]},{"action_id":"cdb53f5c-8701-497d-a866-4256cddd9d66","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled."]},{"action_id":"5571e909-6491-4077-818e-5441ae0dc95d","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled."]},{"action_id":"bdfa85bc-b3a3-4456-b8d9-9ed1dd895ad3","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"688f5ed0-9594-4df1-9883-cc17feca62f8","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"0b87839b-28f5-4150-af26-74cf2b1af3a3","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"352ac9b2-d343-40ac-b427-4c4f285615ef","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access."]},{"action_id":"08a9f629-3bfa-46a1-bd88-e22027f7e133","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled.","Missing bucket identifier for access-path validation."]},{"action_id":"e88846fa-71d2-4291-ae12-2c13b1b49544","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled."]},{"action_id":"7522bc9f-5cab-4bad-908b-a382045f8d87","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled."]},{"action_id":"4a965fac-c139-46e3-8594-11058b1dfe24","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled."]},{"action_id":"cdb53f5c-8701-497d-a866-4256cddd9d66","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled."]},{"action_id":"5571e909-6491-4077-818e-5441ae0dc95d","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled."]},{"action_id":"bdfa85bc-b3a3-4456-b8d9-9ed1dd895ad3","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled."]}]}'
REPLAY_DIR="./.bundle-callback-replay"
RUNNER="./run_actions.sh"
RUN_RC=1
FINISH_SENT=0

mkdir -p "$REPLAY_DIR"

iso_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

inject_timestamp() {
  local template_json="$1"
  local field_name="$2"
  local field_value="$3"
  python3 - "$template_json" "$field_name" "$field_value" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
payload[str(sys.argv[2])] = str(sys.argv[3])
print(json.dumps(payload, separators=(",", ":")))
PY
}

post_payload() {
  local payload="$1"
  if [ -z "$REPORT_URL" ] || [ -z "$REPORT_TOKEN" ]; then
    return 1
  fi
  if command -v curl >/dev/null 2>&1; then
    local response_file http_code rc
    response_file=$(mktemp)
    http_code=$(curl -sS       --connect-timeout 5       --max-time 20       --retry 4       --retry-delay 2       --retry-all-errors       -o "$response_file"       -w "%{http_code}"       -X POST "$REPORT_URL"       -H "Content-Type: application/json"       -d "$payload")
    rc=$?
    if [ "$rc" -ne 0 ]; then
      rm -f "$response_file"
      return "$rc"
    fi
    rm -f "$response_file"
    case "$http_code" in
      2??)
        return 0
        ;;
    esac
    return 1
  fi
  return 1
}

persist_replay() {
  local suffix="$1"
  local payload="$2"
  local file="$REPLAY_DIR/${suffix}-$(date +%s).json"
  printf '%s\n' "$payload" > "$file"
}

emit_finished_callback() {
  local exit_code="$1"
  local finished_at payload
  if [ "$FINISH_SENT" -eq 1 ]; then
    return 0
  fi
  FINISH_SENT=1
  finished_at="$(iso_now)"
  if [ "$exit_code" -eq 0 ]; then
    payload="$(inject_timestamp "$FINISHED_SUCCESS_TEMPLATE" "finished_at" "$finished_at")"
  else
    payload="$(inject_timestamp "$FINISHED_FAILED_TEMPLATE" "finished_at" "$finished_at")"
  fi
  if ! post_payload "$payload"; then
    persist_replay "finished" "$payload"
  fi
}

handle_exit() {
  local exit_code="$1"
  emit_finished_callback "$exit_code"
  exit "$exit_code"
}

STARTED_AT="$(iso_now)"
START_PAYLOAD="$(inject_timestamp "$STARTED_TEMPLATE" "started_at" "$STARTED_AT")"
if ! post_payload "$START_PAYLOAD"; then
  persist_replay "started" "$START_PAYLOAD"
fi

trap 'handle_exit $?' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

chmod +x "$RUNNER"
"$RUNNER"
RUN_RC=$?
exit "$RUN_RC"
