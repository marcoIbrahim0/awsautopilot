#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI1MGEwMzEzNC0xMTkxLTQyNmYtODQyOC1iZmVlZmQwMGNlZjAiLCJncm91cF9pZCI6IjNjZjI5ZTgxLTdkMWItNDE0YS1hYjc4LWQyZTFjM2FiYWQyNyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI3NDUxYzk5Ny0zZWJjLTQ4Y2MtYTY3ZS1jMzViM2RiYjc2YjEiLCJmNzkxYzk4Yy1lYzExLTRhZjctOWYxOS1hYmY4ZWJjNDRkMjEiLCJkN2E2NDc5YS04YWIzLTQwNzctOGI2YS0xOWMzNzhhZTIwZDEiLCJlNTMyYTRhNy1lODMwLTRiNzUtYTA2Yi0yZTBkMWM1MmI3NWIiLCJlYzJjNTkyNS0wOGQ1LTQzN2MtODAxOS05MGY3MDM0ODQ2NDkiLCJkMzNjMGIyOC0yYTU0LTQ2MjMtOGE1ZC0xZjliZmZjNDg4NGQiLCIzMjliMmI5My0yOTU5LTQzMGUtOGE4My02ZDk2M2RkY2U1MTIiLCI3ODIzN2NjMi1lNDdmLTRmMGYtODBkZS0yMmIwOGQ4NzI1YzciLCI5NmJkMWVmYi05MWVlLTRiMjItOWUxZS0yOTYxM2M4NDkyYWEiLCIyOTA0MTcyZi0wNDkxLTQyNDgtYWZjYS1hZjMwYmU4OTY4ODUiLCI2Yjk5YmIwMy1iYjc1LTQ1MzUtYjllMS00NTUwZmJhZDc2YmUiLCI4ZjE5MmMyOS04Y2ZjLTRlMGUtYTlhNC1iNWE0MjdiYzgwYmEiLCIyY2RhY2UyNC1hNjNkLTQ4MWQtODFmNy1mNWJkYTgyYjhhODAiLCIwODg2OTQ2Yi1jZjMyLTQ5Y2ItOGYwZS01ZGNiMDc0MzM0MjYiLCJiY2Q3ZjY5NS03NzJkLTQxOGItOTIxYi1hMmY5Y2EzZWFhNDciLCI1YmYzNWFkYi1lMWNhLTQwYWEtYWY1Zi02YzBmNDZmYjZjMWMiXSwianRpIjoiMjljMjdiZjEtOWZkOC00NmEyLTk5ODMtZTk3YjA2NDA0NjY1IiwiaWF0IjoxNzc1MDA0MjMxLCJleHAiOjE3NzUwOTA2MzF9.7qrAAkZWOaFyUwg69KfDHlEo4roqdW2WJIyS_vpNKQU
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI1MGEwMzEzNC0xMTkxLTQyNmYtODQyOC1iZmVlZmQwMGNlZjAiLCJncm91cF9pZCI6IjNjZjI5ZTgxLTdkMWItNDE0YS1hYjc4LWQyZTFjM2FiYWQyNyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI3NDUxYzk5Ny0zZWJjLTQ4Y2MtYTY3ZS1jMzViM2RiYjc2YjEiLCJmNzkxYzk4Yy1lYzExLTRhZjctOWYxOS1hYmY4ZWJjNDRkMjEiLCJkN2E2NDc5YS04YWIzLTQwNzctOGI2YS0xOWMzNzhhZTIwZDEiLCJlNTMyYTRhNy1lODMwLTRiNzUtYTA2Yi0yZTBkMWM1MmI3NWIiLCJlYzJjNTkyNS0wOGQ1LTQzN2MtODAxOS05MGY3MDM0ODQ2NDkiLCJkMzNjMGIyOC0yYTU0LTQ2MjMtOGE1ZC0xZjliZmZjNDg4NGQiLCIzMjliMmI5My0yOTU5LTQzMGUtOGE4My02ZDk2M2RkY2U1MTIiLCI3ODIzN2NjMi1lNDdmLTRmMGYtODBkZS0yMmIwOGQ4NzI1YzciLCI5NmJkMWVmYi05MWVlLTRiMjItOWUxZS0yOTYxM2M4NDkyYWEiLCIyOTA0MTcyZi0wNDkxLTQyNDgtYWZjYS1hZjMwYmU4OTY4ODUiLCI2Yjk5YmIwMy1iYjc1LTQ1MzUtYjllMS00NTUwZmJhZDc2YmUiLCI4ZjE5MmMyOS04Y2ZjLTRlMGUtYTlhNC1iNWE0MjdiYzgwYmEiLCIyY2RhY2UyNC1hNjNkLTQ4MWQtODFmNy1mNWJkYTgyYjhhODAiLCIwODg2OTQ2Yi1jZjMyLTQ5Y2ItOGYwZS01ZGNiMDc0MzM0MjYiLCJiY2Q3ZjY5NS03NzJkLTQxOGItOTIxYi1hMmY5Y2EzZWFhNDciLCI1YmYzNWFkYi1lMWNhLTQwYWEtYWY1Zi02YzBmNDZmYjZjMWMiXSwianRpIjoiMjljMjdiZjEtOWZkOC00NmEyLTk5ODMtZTk3YjA2NDA0NjY1IiwiaWF0IjoxNzc1MDA0MjMxLCJleHAiOjE3NzUwOTA2MzF9.7qrAAkZWOaFyUwg69KfDHlEo4roqdW2WJIyS_vpNKQU","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI1MGEwMzEzNC0xMTkxLTQyNmYtODQyOC1iZmVlZmQwMGNlZjAiLCJncm91cF9pZCI6IjNjZjI5ZTgxLTdkMWItNDE0YS1hYjc4LWQyZTFjM2FiYWQyNyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI3NDUxYzk5Ny0zZWJjLTQ4Y2MtYTY3ZS1jMzViM2RiYjc2YjEiLCJmNzkxYzk4Yy1lYzExLTRhZjctOWYxOS1hYmY4ZWJjNDRkMjEiLCJkN2E2NDc5YS04YWIzLTQwNzctOGI2YS0xOWMzNzhhZTIwZDEiLCJlNTMyYTRhNy1lODMwLTRiNzUtYTA2Yi0yZTBkMWM1MmI3NWIiLCJlYzJjNTkyNS0wOGQ1LTQzN2MtODAxOS05MGY3MDM0ODQ2NDkiLCJkMzNjMGIyOC0yYTU0LTQ2MjMtOGE1ZC0xZjliZmZjNDg4NGQiLCIzMjliMmI5My0yOTU5LTQzMGUtOGE4My02ZDk2M2RkY2U1MTIiLCI3ODIzN2NjMi1lNDdmLTRmMGYtODBkZS0yMmIwOGQ4NzI1YzciLCI5NmJkMWVmYi05MWVlLTRiMjItOWUxZS0yOTYxM2M4NDkyYWEiLCIyOTA0MTcyZi0wNDkxLTQyNDgtYWZjYS1hZjMwYmU4OTY4ODUiLCI2Yjk5YmIwMy1iYjc1LTQ1MzUtYjllMS00NTUwZmJhZDc2YmUiLCI4ZjE5MmMyOS04Y2ZjLTRlMGUtYTlhNC1iNWE0MjdiYzgwYmEiLCIyY2RhY2UyNC1hNjNkLTQ4MWQtODFmNy1mNWJkYTgyYjhhODAiLCIwODg2OTQ2Yi1jZjMyLTQ5Y2ItOGYwZS01ZGNiMDc0MzM0MjYiLCJiY2Q3ZjY5NS03NzJkLTQxOGItOTIxYi1hMmY5Y2EzZWFhNDciLCI1YmYzNWFkYi1lMWNhLTQwYWEtYWY1Zi02YzBmNDZmYjZjMWMiXSwianRpIjoiMjljMjdiZjEtOWZkOC00NmEyLTk5ODMtZTk3YjA2NDA0NjY1IiwiaWF0IjoxNzc1MDA0MjMxLCJleHAiOjE3NzUwOTA2MzF9.7qrAAkZWOaFyUwg69KfDHlEo4roqdW2WJIyS_vpNKQU","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"7451c997-3ebc-48cc-a67e-c35b3dbb76b1","execution_status":"success"},{"action_id":"f791c98c-ec11-4af7-9f19-abf8ebc44d21","execution_status":"success"},{"action_id":"d7a6479a-8ab3-4077-8b6a-19c378ae20d1","execution_status":"success"},{"action_id":"e532a4a7-e830-4b75-a06b-2e0d1c52b75b","execution_status":"success"},{"action_id":"ec2c5925-08d5-437c-8019-90f703484649","execution_status":"success"},{"action_id":"d33c0b28-2a54-4623-8a5d-1f9bffc4884d","execution_status":"success"},{"action_id":"329b2b93-2959-430e-8a83-6d963ddce512","execution_status":"success"},{"action_id":"78237cc2-e47f-4f0f-80de-22b08d8725c7","execution_status":"success"},{"action_id":"96bd1efb-91ee-4b22-9e1e-29613c8492aa","execution_status":"success"},{"action_id":"6b99bb03-bb75-4535-b9e1-4550fbad76be","execution_status":"success"},{"action_id":"8f192c29-8cfc-4e0e-a9a4-b5a427bc80ba","execution_status":"success"},{"action_id":"2cdace24-a63d-481d-81f7-f5bda82b8a80","execution_status":"success"},{"action_id":"0886946b-cf32-49cb-8f0e-5dcb07433426","execution_status":"success"},{"action_id":"bcd7f695-772d-418b-921b-a2f9ca3eaa47","execution_status":"success"},{"action_id":"5bf35adb-e1ca-40aa-af5f-6c0f46fb6c1c","execution_status":"success"}],"non_executable_results":[{"action_id":"2904172f-0491-4248-afca-af30be896885","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["Bucket policy preservation evidence is missing for merge-safe SSL enforcement."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI1MGEwMzEzNC0xMTkxLTQyNmYtODQyOC1iZmVlZmQwMGNlZjAiLCJncm91cF9pZCI6IjNjZjI5ZTgxLTdkMWItNDE0YS1hYjc4LWQyZTFjM2FiYWQyNyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI3NDUxYzk5Ny0zZWJjLTQ4Y2MtYTY3ZS1jMzViM2RiYjc2YjEiLCJmNzkxYzk4Yy1lYzExLTRhZjctOWYxOS1hYmY4ZWJjNDRkMjEiLCJkN2E2NDc5YS04YWIzLTQwNzctOGI2YS0xOWMzNzhhZTIwZDEiLCJlNTMyYTRhNy1lODMwLTRiNzUtYTA2Yi0yZTBkMWM1MmI3NWIiLCJlYzJjNTkyNS0wOGQ1LTQzN2MtODAxOS05MGY3MDM0ODQ2NDkiLCJkMzNjMGIyOC0yYTU0LTQ2MjMtOGE1ZC0xZjliZmZjNDg4NGQiLCIzMjliMmI5My0yOTU5LTQzMGUtOGE4My02ZDk2M2RkY2U1MTIiLCI3ODIzN2NjMi1lNDdmLTRmMGYtODBkZS0yMmIwOGQ4NzI1YzciLCI5NmJkMWVmYi05MWVlLTRiMjItOWUxZS0yOTYxM2M4NDkyYWEiLCIyOTA0MTcyZi0wNDkxLTQyNDgtYWZjYS1hZjMwYmU4OTY4ODUiLCI2Yjk5YmIwMy1iYjc1LTQ1MzUtYjllMS00NTUwZmJhZDc2YmUiLCI4ZjE5MmMyOS04Y2ZjLTRlMGUtYTlhNC1iNWE0MjdiYzgwYmEiLCIyY2RhY2UyNC1hNjNkLTQ4MWQtODFmNy1mNWJkYTgyYjhhODAiLCIwODg2OTQ2Yi1jZjMyLTQ5Y2ItOGYwZS01ZGNiMDc0MzM0MjYiLCJiY2Q3ZjY5NS03NzJkLTQxOGItOTIxYi1hMmY5Y2EzZWFhNDciLCI1YmYzNWFkYi1lMWNhLTQwYWEtYWY1Zi02YzBmNDZmYjZjMWMiXSwianRpIjoiMjljMjdiZjEtOWZkOC00NmEyLTk5ODMtZTk3YjA2NDA0NjY1IiwiaWF0IjoxNzc1MDA0MjMxLCJleHAiOjE3NzUwOTA2MzF9.7qrAAkZWOaFyUwg69KfDHlEo4roqdW2WJIyS_vpNKQU","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"7451c997-3ebc-48cc-a67e-c35b3dbb76b1","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"f791c98c-ec11-4af7-9f19-abf8ebc44d21","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"d7a6479a-8ab3-4077-8b6a-19c378ae20d1","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e532a4a7-e830-4b75-a06b-2e0d1c52b75b","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"ec2c5925-08d5-437c-8019-90f703484649","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"d33c0b28-2a54-4623-8a5d-1f9bffc4884d","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"329b2b93-2959-430e-8a83-6d963ddce512","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"78237cc2-e47f-4f0f-80de-22b08d8725c7","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"96bd1efb-91ee-4b22-9e1e-29613c8492aa","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"6b99bb03-bb75-4535-b9e1-4550fbad76be","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"8f192c29-8cfc-4e0e-a9a4-b5a427bc80ba","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"2cdace24-a63d-481d-81f7-f5bda82b8a80","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"0886946b-cf32-49cb-8f0e-5dcb07433426","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"bcd7f695-772d-418b-921b-a2f9ca3eaa47","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"5bf35adb-e1ca-40aa-af5f-6c0f46fb6c1c","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"2904172f-0491-4248-afca-af30be896885","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["Bucket policy preservation evidence is missing for merge-safe SSL enforcement."]}]}'
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
