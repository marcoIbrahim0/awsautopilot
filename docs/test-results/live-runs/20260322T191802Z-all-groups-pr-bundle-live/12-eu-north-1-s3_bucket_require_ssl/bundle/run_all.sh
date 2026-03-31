#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=<REDACTED_TOKEN>
STARTED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"0ca99079-34e6-4c17-b121-b1f1727494eb","execution_status":"success"},{"action_id":"129fa65e-11e1-4eb0-bf8f-dff5fec13487","execution_status":"success"},{"action_id":"23bf691b-8ec2-4920-80a8-09bca2b8e218","execution_status":"success"},{"action_id":"4da3d806-4084-4075-8f3c-221d08ef5c2c","execution_status":"success"},{"action_id":"61552073-d604-4ba5-8430-b04485f90a5c","execution_status":"success"},{"action_id":"967d71a9-8027-4223-b6c6-aa5578d1d2d5","execution_status":"success"},{"action_id":"9e4562df-9922-4f75-b4e4-2d17c2c615f8","execution_status":"success"},{"action_id":"b84115cb-a701-48d7-832c-4fbcf80b8724","execution_status":"success"},{"action_id":"b8a67bbf-1255-40f1-ab21-569689459a36","execution_status":"success"},{"action_id":"c1c2ed6d-408b-4743-86d9-0fedeff97ce6","execution_status":"success"},{"action_id":"830944d9-30ad-432f-a84e-e09c0dde3d5d","execution_status":"success"}],"non_executable_results":[{"action_id":"2ac461ec-b4c1-4fcd-8ae1-a6d18f53c8d4","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["Bucket policy preservation evidence is missing for merge-safe SSL enforcement."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"0ca99079-34e6-4c17-b121-b1f1727494eb","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"129fa65e-11e1-4eb0-bf8f-dff5fec13487","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"23bf691b-8ec2-4920-80a8-09bca2b8e218","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4da3d806-4084-4075-8f3c-221d08ef5c2c","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"61552073-d604-4ba5-8430-b04485f90a5c","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"967d71a9-8027-4223-b6c6-aa5578d1d2d5","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"9e4562df-9922-4f75-b4e4-2d17c2c615f8","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"b84115cb-a701-48d7-832c-4fbcf80b8724","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"b8a67bbf-1255-40f1-ab21-569689459a36","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"c1c2ed6d-408b-4743-86d9-0fedeff97ce6","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"830944d9-30ad-432f-a84e-e09c0dde3d5d","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"2ac461ec-b4c1-4fcd-8ae1-a6d18f53c8d4","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["Bucket policy preservation evidence is missing for merge-safe SSL enforcement."]}]}'
REPLAY_DIR="./.bundle-callback-replay"
RUNNER="./run_actions.sh"

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
    curl -sS -X POST "$REPORT_URL" -H "Content-Type: application/json" -d "$payload" >/dev/null 2>&1
    return $?
  fi
  return 1
}

persist_replay() {
  local suffix="$1"
  local payload="$2"
  local file="$REPLAY_DIR/${suffix}-$(date +%s).json"
  printf '%s\n' "$payload" > "$file"
}

STARTED_AT="$(iso_now)"
START_PAYLOAD="$(inject_timestamp "$STARTED_TEMPLATE" "started_at" "$STARTED_AT")"
if ! post_payload "$START_PAYLOAD"; then
  persist_replay "started" "$START_PAYLOAD"
fi

chmod +x "$RUNNER"
"$RUNNER"
RUN_RC=$?

FINISHED_AT="$(iso_now)"
if [ "$RUN_RC" -eq 0 ]; then
  FINISH_PAYLOAD="$(inject_timestamp "$FINISHED_SUCCESS_TEMPLATE" "finished_at" "$FINISHED_AT")"
else
  FINISH_PAYLOAD="$(inject_timestamp "$FINISHED_FAILED_TEMPLATE" "finished_at" "$FINISHED_AT")"
fi

if ! post_payload "$FINISH_PAYLOAD"; then
  persist_replay "finished" "$FINISH_PAYLOAD"
fi

exit "$RUN_RC"
