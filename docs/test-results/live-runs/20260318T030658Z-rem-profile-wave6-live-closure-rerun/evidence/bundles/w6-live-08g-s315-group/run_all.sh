#!/usr/bin/env bash
set +e

REPORT_URL=https://g1frb5hhfg.execute-api.eu-north-1.amazonaws.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiIwYTMxNTRkNC0wODcwLTQzOGYtYmNmNS1iOTZlOThiODM5NTgiLCJncm91cF9pZCI6Ijc0M2VjMzZlLTk1OGUtNGI3MC04ZmRmLWQ1ZTFjMjM3NTQzZSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIzM2JkMzI1NS00N2E4LTQyM2ItYjZjNi1jNjM2Mzg5MWM5ZDYiLCIzNTc1ZjQ2Zi1hNWNhLTRjM2QtOTg3ZC1mZjc0ZTEwM2IzOTciLCI0NGY2ZGYwYS02YTJjLTQ0MmItYjMyOC1iOTBjYjE1Mzc5NGQiLCI0NzhlYmMyZi1kMjUzLTQ0NTQtOWU0Ny02Njc0OTNmNzA1N2EiLCI1Mjk0NzU1Ny0wYjM1LTRjMDMtOTlkNi00ZmRmNzdjODZhMjQiLCI2NmE1ZGQ0My1iMDAxLTQ1MTktYjA3Mi00YWNmOGQ3NTE0ZGQiLCI3YTBlMmM1Ny0xZmY0LTQ3YWUtYTRhOC00YjI2ZWZlNmEzZDYiLCI3YjljYThiMS02ZTc4LTQxZWQtOTZiOS0zNGFmNWQ0YTc4MmEiLCI3YmY4YzAzNC01MjJhLTQ5MWEtYTIzYS03MjU1NDYzMmQ0ODUiLCI3Zjg1YTM1My01OTY1LTQ2NjMtYjVlYS05YTIwMTZjZmU0OTUiLCJkNTY0NmM3MS1mNzY1LTRiZWYtOTJkNi1jZmIyNTUwMmFhODUiXSwianRpIjoiMjIxYmQ3YmItMDI3Ny00NDBlLWE1MjItNWVhNzk2NDM1MGI3IiwiaWF0IjoxNzczODY1ODMxLCJleHAiOjE3NzM5NTIyMzF9.wlWCh5MP2t2YlOQpSPkpTbiuslu6vLGfYPoO_2kxptI
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiIwYTMxNTRkNC0wODcwLTQzOGYtYmNmNS1iOTZlOThiODM5NTgiLCJncm91cF9pZCI6Ijc0M2VjMzZlLTk1OGUtNGI3MC04ZmRmLWQ1ZTFjMjM3NTQzZSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIzM2JkMzI1NS00N2E4LTQyM2ItYjZjNi1jNjM2Mzg5MWM5ZDYiLCIzNTc1ZjQ2Zi1hNWNhLTRjM2QtOTg3ZC1mZjc0ZTEwM2IzOTciLCI0NGY2ZGYwYS02YTJjLTQ0MmItYjMyOC1iOTBjYjE1Mzc5NGQiLCI0NzhlYmMyZi1kMjUzLTQ0NTQtOWU0Ny02Njc0OTNmNzA1N2EiLCI1Mjk0NzU1Ny0wYjM1LTRjMDMtOTlkNi00ZmRmNzdjODZhMjQiLCI2NmE1ZGQ0My1iMDAxLTQ1MTktYjA3Mi00YWNmOGQ3NTE0ZGQiLCI3YTBlMmM1Ny0xZmY0LTQ3YWUtYTRhOC00YjI2ZWZlNmEzZDYiLCI3YjljYThiMS02ZTc4LTQxZWQtOTZiOS0zNGFmNWQ0YTc4MmEiLCI3YmY4YzAzNC01MjJhLTQ5MWEtYTIzYS03MjU1NDYzMmQ0ODUiLCI3Zjg1YTM1My01OTY1LTQ2NjMtYjVlYS05YTIwMTZjZmU0OTUiLCJkNTY0NmM3MS1mNzY1LTRiZWYtOTJkNi1jZmIyNTUwMmFhODUiXSwianRpIjoiMjIxYmQ3YmItMDI3Ny00NDBlLWE1MjItNWVhNzk2NDM1MGI3IiwiaWF0IjoxNzczODY1ODMxLCJleHAiOjE3NzM5NTIyMzF9.wlWCh5MP2t2YlOQpSPkpTbiuslu6vLGfYPoO_2kxptI","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiIwYTMxNTRkNC0wODcwLTQzOGYtYmNmNS1iOTZlOThiODM5NTgiLCJncm91cF9pZCI6Ijc0M2VjMzZlLTk1OGUtNGI3MC04ZmRmLWQ1ZTFjMjM3NTQzZSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIzM2JkMzI1NS00N2E4LTQyM2ItYjZjNi1jNjM2Mzg5MWM5ZDYiLCIzNTc1ZjQ2Zi1hNWNhLTRjM2QtOTg3ZC1mZjc0ZTEwM2IzOTciLCI0NGY2ZGYwYS02YTJjLTQ0MmItYjMyOC1iOTBjYjE1Mzc5NGQiLCI0NzhlYmMyZi1kMjUzLTQ0NTQtOWU0Ny02Njc0OTNmNzA1N2EiLCI1Mjk0NzU1Ny0wYjM1LTRjMDMtOTlkNi00ZmRmNzdjODZhMjQiLCI2NmE1ZGQ0My1iMDAxLTQ1MTktYjA3Mi00YWNmOGQ3NTE0ZGQiLCI3YTBlMmM1Ny0xZmY0LTQ3YWUtYTRhOC00YjI2ZWZlNmEzZDYiLCI3YjljYThiMS02ZTc4LTQxZWQtOTZiOS0zNGFmNWQ0YTc4MmEiLCI3YmY4YzAzNC01MjJhLTQ5MWEtYTIzYS03MjU1NDYzMmQ0ODUiLCI3Zjg1YTM1My01OTY1LTQ2NjMtYjVlYS05YTIwMTZjZmU0OTUiLCJkNTY0NmM3MS1mNzY1LTRiZWYtOTJkNi1jZmIyNTUwMmFhODUiXSwianRpIjoiMjIxYmQ3YmItMDI3Ny00NDBlLWE1MjItNWVhNzk2NDM1MGI3IiwiaWF0IjoxNzczODY1ODMxLCJleHAiOjE3NzM5NTIyMzF9.wlWCh5MP2t2YlOQpSPkpTbiuslu6vLGfYPoO_2kxptI","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"33bd3255-47a8-423b-b6c6-c6363891c9d6","execution_status":"success"},{"action_id":"3575f46f-a5ca-4c3d-987d-ff74e103b397","execution_status":"success"},{"action_id":"44f6df0a-6a2c-442b-b328-b90cb153794d","execution_status":"success"},{"action_id":"478ebc2f-d253-4454-9e47-667493f7057a","execution_status":"success"},{"action_id":"66a5dd43-b001-4519-b072-4acf8d7514dd","execution_status":"success"},{"action_id":"7a0e2c57-1ff4-47ae-a4a8-4b26efe6a3d6","execution_status":"success"},{"action_id":"7b9ca8b1-6e78-41ed-96b9-34af5d4a782a","execution_status":"success"},{"action_id":"7bf8c034-522a-491a-a23a-72554632d485","execution_status":"success"},{"action_id":"7f85a353-5965-4663-b5ea-9a2016cfe495","execution_status":"success"},{"action_id":"d5646c71-f765-4bef-92d6-cfb25502aa85","execution_status":"success"}],"non_executable_results":[{"action_id":"52947557-0b35-4c03-99d6-4fdf77c86a24","support_tier":"review_required_bundle","profile_id":"s3_enable_sse_kms_customer_managed","strategy_id":"s3_enable_sse_kms_guided","reason":"review_required_metadata_only","blocked_reasons":["AccessDeniedException"]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiIwYTMxNTRkNC0wODcwLTQzOGYtYmNmNS1iOTZlOThiODM5NTgiLCJncm91cF9pZCI6Ijc0M2VjMzZlLTk1OGUtNGI3MC04ZmRmLWQ1ZTFjMjM3NTQzZSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIzM2JkMzI1NS00N2E4LTQyM2ItYjZjNi1jNjM2Mzg5MWM5ZDYiLCIzNTc1ZjQ2Zi1hNWNhLTRjM2QtOTg3ZC1mZjc0ZTEwM2IzOTciLCI0NGY2ZGYwYS02YTJjLTQ0MmItYjMyOC1iOTBjYjE1Mzc5NGQiLCI0NzhlYmMyZi1kMjUzLTQ0NTQtOWU0Ny02Njc0OTNmNzA1N2EiLCI1Mjk0NzU1Ny0wYjM1LTRjMDMtOTlkNi00ZmRmNzdjODZhMjQiLCI2NmE1ZGQ0My1iMDAxLTQ1MTktYjA3Mi00YWNmOGQ3NTE0ZGQiLCI3YTBlMmM1Ny0xZmY0LTQ3YWUtYTRhOC00YjI2ZWZlNmEzZDYiLCI3YjljYThiMS02ZTc4LTQxZWQtOTZiOS0zNGFmNWQ0YTc4MmEiLCI3YmY4YzAzNC01MjJhLTQ5MWEtYTIzYS03MjU1NDYzMmQ0ODUiLCI3Zjg1YTM1My01OTY1LTQ2NjMtYjVlYS05YTIwMTZjZmU0OTUiLCJkNTY0NmM3MS1mNzY1LTRiZWYtOTJkNi1jZmIyNTUwMmFhODUiXSwianRpIjoiMjIxYmQ3YmItMDI3Ny00NDBlLWE1MjItNWVhNzk2NDM1MGI3IiwiaWF0IjoxNzczODY1ODMxLCJleHAiOjE3NzM5NTIyMzF9.wlWCh5MP2t2YlOQpSPkpTbiuslu6vLGfYPoO_2kxptI","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"33bd3255-47a8-423b-b6c6-c6363891c9d6","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"3575f46f-a5ca-4c3d-987d-ff74e103b397","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"44f6df0a-6a2c-442b-b328-b90cb153794d","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"478ebc2f-d253-4454-9e47-667493f7057a","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"66a5dd43-b001-4519-b072-4acf8d7514dd","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"7a0e2c57-1ff4-47ae-a4a8-4b26efe6a3d6","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"7b9ca8b1-6e78-41ed-96b9-34af5d4a782a","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"7bf8c034-522a-491a-a23a-72554632d485","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"7f85a353-5965-4663-b5ea-9a2016cfe495","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"d5646c71-f765-4bef-92d6-cfb25502aa85","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"52947557-0b35-4c03-99d6-4fdf77c86a24","support_tier":"review_required_bundle","profile_id":"s3_enable_sse_kms_customer_managed","strategy_id":"s3_enable_sse_kms_guided","reason":"review_required_metadata_only","blocked_reasons":["AccessDeniedException"]}]}'
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
