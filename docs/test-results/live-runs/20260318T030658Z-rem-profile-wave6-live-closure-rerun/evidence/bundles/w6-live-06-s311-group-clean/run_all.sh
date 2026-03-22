#!/usr/bin/env bash
set +e

REPORT_URL=http://127.0.0.1:18022/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiI5ZjkxMWEzOS1kZjdkLTQ2YzEtYjExYS0yYjU4YjYyMThmZTgiLCJncm91cF9pZCI6ImU5OTQxMDcyLWIxY2UtNDM1NS1iNzEwLWM4NDEyNDg1ZDNiOCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJhMTA1YmY2YS1iZmQ1LTQxM2UtOTczMC1lOWRmNGRjNzQyODUiLCJhNjJjZGZlYi05MTc3LTQyNmYtYTYxNS0yMjJjMDg5YjM0N2UiLCJkM2JlMWM3NS0yNGVjLTQ0NjItYjg2MC1jNWIyNjI4ZWExOGIiLCJlNzU1YjJjZS1iZWE2LTRlNDgtOGExMy1kNTk3OGUwMWNkMWQiLCJhYmExNjk0ZC0xYzJhLTQyZTgtOTJiNy02ZmJlMzRiN2QzMTAiXSwianRpIjoiZDBmYWQ0MDctNGMzNC00NGUwLTlmODctOTU3YjE4NmRiZTgyIiwiaWF0IjoxNzczODU5MTA4LCJleHAiOjE3NzM5NDU1MDh9.kVx5LSspkSjAIbVbqaTF-hCMUBeqX5pCXEis5xi8RBo
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiI5ZjkxMWEzOS1kZjdkLTQ2YzEtYjExYS0yYjU4YjYyMThmZTgiLCJncm91cF9pZCI6ImU5OTQxMDcyLWIxY2UtNDM1NS1iNzEwLWM4NDEyNDg1ZDNiOCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJhMTA1YmY2YS1iZmQ1LTQxM2UtOTczMC1lOWRmNGRjNzQyODUiLCJhNjJjZGZlYi05MTc3LTQyNmYtYTYxNS0yMjJjMDg5YjM0N2UiLCJkM2JlMWM3NS0yNGVjLTQ0NjItYjg2MC1jNWIyNjI4ZWExOGIiLCJlNzU1YjJjZS1iZWE2LTRlNDgtOGExMy1kNTk3OGUwMWNkMWQiLCJhYmExNjk0ZC0xYzJhLTQyZTgtOTJiNy02ZmJlMzRiN2QzMTAiXSwianRpIjoiZDBmYWQ0MDctNGMzNC00NGUwLTlmODctOTU3YjE4NmRiZTgyIiwiaWF0IjoxNzczODU5MTA4LCJleHAiOjE3NzM5NDU1MDh9.kVx5LSspkSjAIbVbqaTF-hCMUBeqX5pCXEis5xi8RBo","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiI5ZjkxMWEzOS1kZjdkLTQ2YzEtYjExYS0yYjU4YjYyMThmZTgiLCJncm91cF9pZCI6ImU5OTQxMDcyLWIxY2UtNDM1NS1iNzEwLWM4NDEyNDg1ZDNiOCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJhMTA1YmY2YS1iZmQ1LTQxM2UtOTczMC1lOWRmNGRjNzQyODUiLCJhNjJjZGZlYi05MTc3LTQyNmYtYTYxNS0yMjJjMDg5YjM0N2UiLCJkM2JlMWM3NS0yNGVjLTQ0NjItYjg2MC1jNWIyNjI4ZWExOGIiLCJlNzU1YjJjZS1iZWE2LTRlNDgtOGExMy1kNTk3OGUwMWNkMWQiLCJhYmExNjk0ZC0xYzJhLTQyZTgtOTJiNy02ZmJlMzRiN2QzMTAiXSwianRpIjoiZDBmYWQ0MDctNGMzNC00NGUwLTlmODctOTU3YjE4NmRiZTgyIiwiaWF0IjoxNzczODU5MTA4LCJleHAiOjE3NzM5NDU1MDh9.kVx5LSspkSjAIbVbqaTF-hCMUBeqX5pCXEis5xi8RBo","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"d3be1c75-24ec-4462-b860-c5b2628ea18b","execution_status":"success"}],"non_executable_results":[{"action_id":"a105bf6a-bfd5-413e-9730-e9df4dc74285","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["AccessDenied","Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"a62cdfeb-9177-426f-a615-222c089b347e","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["AccessDenied","Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"e755b2ce-bea6-4e48-8a13-d5978e01cd1d","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["AccessDenied","Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"aba1694d-1c2a-42e8-92b7-6fbe34b7d310","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["Lifecycle preservation evidence is missing for additive merge review."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiI5ZjkxMWEzOS1kZjdkLTQ2YzEtYjExYS0yYjU4YjYyMThmZTgiLCJncm91cF9pZCI6ImU5OTQxMDcyLWIxY2UtNDM1NS1iNzEwLWM4NDEyNDg1ZDNiOCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJhMTA1YmY2YS1iZmQ1LTQxM2UtOTczMC1lOWRmNGRjNzQyODUiLCJhNjJjZGZlYi05MTc3LTQyNmYtYTYxNS0yMjJjMDg5YjM0N2UiLCJkM2JlMWM3NS0yNGVjLTQ0NjItYjg2MC1jNWIyNjI4ZWExOGIiLCJlNzU1YjJjZS1iZWE2LTRlNDgtOGExMy1kNTk3OGUwMWNkMWQiLCJhYmExNjk0ZC0xYzJhLTQyZTgtOTJiNy02ZmJlMzRiN2QzMTAiXSwianRpIjoiZDBmYWQ0MDctNGMzNC00NGUwLTlmODctOTU3YjE4NmRiZTgyIiwiaWF0IjoxNzczODU5MTA4LCJleHAiOjE3NzM5NDU1MDh9.kVx5LSspkSjAIbVbqaTF-hCMUBeqX5pCXEis5xi8RBo","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"d3be1c75-24ec-4462-b860-c5b2628ea18b","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"a105bf6a-bfd5-413e-9730-e9df4dc74285","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["AccessDenied","Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"a62cdfeb-9177-426f-a615-222c089b347e","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["AccessDenied","Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"e755b2ce-bea6-4e48-8a13-d5978e01cd1d","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["AccessDenied","Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"aba1694d-1c2a-42e8-92b7-6fbe34b7d310","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["Lifecycle preservation evidence is missing for additive merge review."]}]}'
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
