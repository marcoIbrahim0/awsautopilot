#!/usr/bin/env bash
set +e

REPORT_URL=http://127.0.0.1:8000/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI2Y2E1ZjU3NC1jZmIwLTRmY2EtOWI2Ni05OGIwODNkZmJhMGIiLCJncm91cF9pZCI6IjgyNWFjZmQ3LWQwZWMtNGRkMC04MDZkLWIxNjI4YWIzZTM1ZSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIwYWJjNjAzZC1iNzVhLTRiNDktOWE1Zi00MzFhMGFhODJhNGUiLCI2NDc3ODRhNy1mODRiLTRmNjQtYjJmOS05ZTE5OThhODYzNzYiLCI5NzBhMmJmOC1lMDFiLTRhMmMtYTY5OS1jZWM5Njg2NTJhY2IiLCI5YThhMTliMy1iMWM0LTQ0YWYtOWM2Ni1hM2IwMTQzMmExMTYiXSwianRpIjoiZTFkNjdmMjEtMzMwYy00ODkwLWI3NDYtYzc1MTk3NTQwNGJkIiwiaWF0IjoxNzc0MjMyMjY3LCJleHAiOjE3NzQzMTg2Njd9.jkrC3NFO7NkM_ByXtuq6KOXVtZHYgCvTzC5fyp4_ffc
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI2Y2E1ZjU3NC1jZmIwLTRmY2EtOWI2Ni05OGIwODNkZmJhMGIiLCJncm91cF9pZCI6IjgyNWFjZmQ3LWQwZWMtNGRkMC04MDZkLWIxNjI4YWIzZTM1ZSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIwYWJjNjAzZC1iNzVhLTRiNDktOWE1Zi00MzFhMGFhODJhNGUiLCI2NDc3ODRhNy1mODRiLTRmNjQtYjJmOS05ZTE5OThhODYzNzYiLCI5NzBhMmJmOC1lMDFiLTRhMmMtYTY5OS1jZWM5Njg2NTJhY2IiLCI5YThhMTliMy1iMWM0LTQ0YWYtOWM2Ni1hM2IwMTQzMmExMTYiXSwianRpIjoiZTFkNjdmMjEtMzMwYy00ODkwLWI3NDYtYzc1MTk3NTQwNGJkIiwiaWF0IjoxNzc0MjMyMjY3LCJleHAiOjE3NzQzMTg2Njd9.jkrC3NFO7NkM_ByXtuq6KOXVtZHYgCvTzC5fyp4_ffc","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI2Y2E1ZjU3NC1jZmIwLTRmY2EtOWI2Ni05OGIwODNkZmJhMGIiLCJncm91cF9pZCI6IjgyNWFjZmQ3LWQwZWMtNGRkMC04MDZkLWIxNjI4YWIzZTM1ZSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIwYWJjNjAzZC1iNzVhLTRiNDktOWE1Zi00MzFhMGFhODJhNGUiLCI2NDc3ODRhNy1mODRiLTRmNjQtYjJmOS05ZTE5OThhODYzNzYiLCI5NzBhMmJmOC1lMDFiLTRhMmMtYTY5OS1jZWM5Njg2NTJhY2IiLCI5YThhMTliMy1iMWM0LTQ0YWYtOWM2Ni1hM2IwMTQzMmExMTYiXSwianRpIjoiZTFkNjdmMjEtMzMwYy00ODkwLWI3NDYtYzc1MTk3NTQwNGJkIiwiaWF0IjoxNzc0MjMyMjY3LCJleHAiOjE3NzQzMTg2Njd9.jkrC3NFO7NkM_ByXtuq6KOXVtZHYgCvTzC5fyp4_ffc","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"0abc603d-b75a-4b49-9a5f-431a0aa82a4e","execution_status":"success"},{"action_id":"647784a7-f84b-4f64-b2f9-9e1998a86376","execution_status":"success"},{"action_id":"970a2bf8-e01b-4a2c-a699-cec968652acb","execution_status":"success"},{"action_id":"9a8a19b3-b1c4-44af-9c66-a3b01432a116","execution_status":"success"}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI2Y2E1ZjU3NC1jZmIwLTRmY2EtOWI2Ni05OGIwODNkZmJhMGIiLCJncm91cF9pZCI6IjgyNWFjZmQ3LWQwZWMtNGRkMC04MDZkLWIxNjI4YWIzZTM1ZSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIwYWJjNjAzZC1iNzVhLTRiNDktOWE1Zi00MzFhMGFhODJhNGUiLCI2NDc3ODRhNy1mODRiLTRmNjQtYjJmOS05ZTE5OThhODYzNzYiLCI5NzBhMmJmOC1lMDFiLTRhMmMtYTY5OS1jZWM5Njg2NTJhY2IiLCI5YThhMTliMy1iMWM0LTQ0YWYtOWM2Ni1hM2IwMTQzMmExMTYiXSwianRpIjoiZTFkNjdmMjEtMzMwYy00ODkwLWI3NDYtYzc1MTk3NTQwNGJkIiwiaWF0IjoxNzc0MjMyMjY3LCJleHAiOjE3NzQzMTg2Njd9.jkrC3NFO7NkM_ByXtuq6KOXVtZHYgCvTzC5fyp4_ffc","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"0abc603d-b75a-4b49-9a5f-431a0aa82a4e","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"647784a7-f84b-4f64-b2f9-9e1998a86376","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"970a2bf8-e01b-4a2c-a699-cec968652acb","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"9a8a19b3-b1c4-44af-9c66-a3b01432a116","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}]}'
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
