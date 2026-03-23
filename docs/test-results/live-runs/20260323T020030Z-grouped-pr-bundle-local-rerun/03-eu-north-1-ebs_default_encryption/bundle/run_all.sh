#!/usr/bin/env bash
set +e

REPORT_URL=http://127.0.0.1:8000/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI2NDA3YjY5Zi1mYmMxLTQ5ZmItYWU2NS0xYWVhMDJlYWFhZGMiLCJncm91cF9pZCI6IjEwMDEzYzY2LWQwM2QtNDhlMi05ZDg1LWQwNmY0ZjkwZTI3NyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJkOGRhMzY5OC0yMzBmLTQ0ZTMtOWMxMS1jYzllNDA5OWI3ZjYiXSwianRpIjoiYWE0OTg4NWItMjU0Zi00NDNiLWE1ZWUtYTJkNTEyMzhmYmM1IiwiaWF0IjoxNzc0MjMxMzE0LCJleHAiOjE3NzQzMTc3MTR9.9GU3DNZX-5dHPoS5AQztrtmsKNosdPfkH9t9ivuogf4
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI2NDA3YjY5Zi1mYmMxLTQ5ZmItYWU2NS0xYWVhMDJlYWFhZGMiLCJncm91cF9pZCI6IjEwMDEzYzY2LWQwM2QtNDhlMi05ZDg1LWQwNmY0ZjkwZTI3NyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJkOGRhMzY5OC0yMzBmLTQ0ZTMtOWMxMS1jYzllNDA5OWI3ZjYiXSwianRpIjoiYWE0OTg4NWItMjU0Zi00NDNiLWE1ZWUtYTJkNTEyMzhmYmM1IiwiaWF0IjoxNzc0MjMxMzE0LCJleHAiOjE3NzQzMTc3MTR9.9GU3DNZX-5dHPoS5AQztrtmsKNosdPfkH9t9ivuogf4","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI2NDA3YjY5Zi1mYmMxLTQ5ZmItYWU2NS0xYWVhMDJlYWFhZGMiLCJncm91cF9pZCI6IjEwMDEzYzY2LWQwM2QtNDhlMi05ZDg1LWQwNmY0ZjkwZTI3NyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJkOGRhMzY5OC0yMzBmLTQ0ZTMtOWMxMS1jYzllNDA5OWI3ZjYiXSwianRpIjoiYWE0OTg4NWItMjU0Zi00NDNiLWE1ZWUtYTJkNTEyMzhmYmM1IiwiaWF0IjoxNzc0MjMxMzE0LCJleHAiOjE3NzQzMTc3MTR9.9GU3DNZX-5dHPoS5AQztrtmsKNosdPfkH9t9ivuogf4","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"d8da3698-230f-44e3-9c11-cc9e4099b7f6","execution_status":"success"}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI2NDA3YjY5Zi1mYmMxLTQ5ZmItYWU2NS0xYWVhMDJlYWFhZGMiLCJncm91cF9pZCI6IjEwMDEzYzY2LWQwM2QtNDhlMi05ZDg1LWQwNmY0ZjkwZTI3NyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJkOGRhMzY5OC0yMzBmLTQ0ZTMtOWMxMS1jYzllNDA5OWI3ZjYiXSwianRpIjoiYWE0OTg4NWItMjU0Zi00NDNiLWE1ZWUtYTJkNTEyMzhmYmM1IiwiaWF0IjoxNzc0MjMxMzE0LCJleHAiOjE3NzQzMTc3MTR9.9GU3DNZX-5dHPoS5AQztrtmsKNosdPfkH9t9ivuogf4","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"d8da3698-230f-44e3-9c11-cc9e4099b7f6","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}]}'
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
