#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJmZTY2NzIzNS02MTQ5LTQ4MTMtODk1OS04YTFjOGFlMDc3ZGEiLCJncm91cF9pZCI6IjU5NWNiN2UzLTVmNGYtNDlhNC05YzQ4LTkzODhmMTM5ZjAxMiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI5NTY5YWE5OC1hZjkzLTQwOTUtYThmNi02OTU4NjdjMWI4MzkiLCI0YTFlNTZmZS1iYTY1LTQwODItYTcyYi1iMzlhMjhkNzA5NDUiLCI1OGEyMjYwNy02NjZlLTQwMTYtOGZlMy00Y2U2MmEyMzVhNmUiLCJkNTYzNjVmZS0xNmJlLTQyMzktOWIyZi1kNmNhN2UyNDZkMzUiLCI2NDcwYTk5YS1lYTczLTQ4YTAtYmExZC03NWMxZWJkOGJhNTkiLCI0Njk0ZTBjYy05OWE2LTQ1MzMtODUwNi0xOWE3YTQ3MTBkOTUiLCJkZmEwYTUyNi04N2I4LTQ2NzAtOTJkNy00MDFhNjExZjU4ZjUiXSwianRpIjoiMWE4MWFmNWQtMDM1NC00OTM0LWFlNmYtM2ZlMGU3NDJhMDc1IiwiaWF0IjoxNzc1MDA0MjE4LCJleHAiOjE3NzUwOTA2MTh9.qfqqjLa32D8qngsRADN8_BFeT8LKyJ2pa4D3oMvXQDk
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJmZTY2NzIzNS02MTQ5LTQ4MTMtODk1OS04YTFjOGFlMDc3ZGEiLCJncm91cF9pZCI6IjU5NWNiN2UzLTVmNGYtNDlhNC05YzQ4LTkzODhmMTM5ZjAxMiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI5NTY5YWE5OC1hZjkzLTQwOTUtYThmNi02OTU4NjdjMWI4MzkiLCI0YTFlNTZmZS1iYTY1LTQwODItYTcyYi1iMzlhMjhkNzA5NDUiLCI1OGEyMjYwNy02NjZlLTQwMTYtOGZlMy00Y2U2MmEyMzVhNmUiLCJkNTYzNjVmZS0xNmJlLTQyMzktOWIyZi1kNmNhN2UyNDZkMzUiLCI2NDcwYTk5YS1lYTczLTQ4YTAtYmExZC03NWMxZWJkOGJhNTkiLCI0Njk0ZTBjYy05OWE2LTQ1MzMtODUwNi0xOWE3YTQ3MTBkOTUiLCJkZmEwYTUyNi04N2I4LTQ2NzAtOTJkNy00MDFhNjExZjU4ZjUiXSwianRpIjoiMWE4MWFmNWQtMDM1NC00OTM0LWFlNmYtM2ZlMGU3NDJhMDc1IiwiaWF0IjoxNzc1MDA0MjE4LCJleHAiOjE3NzUwOTA2MTh9.qfqqjLa32D8qngsRADN8_BFeT8LKyJ2pa4D3oMvXQDk","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJmZTY2NzIzNS02MTQ5LTQ4MTMtODk1OS04YTFjOGFlMDc3ZGEiLCJncm91cF9pZCI6IjU5NWNiN2UzLTVmNGYtNDlhNC05YzQ4LTkzODhmMTM5ZjAxMiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI5NTY5YWE5OC1hZjkzLTQwOTUtYThmNi02OTU4NjdjMWI4MzkiLCI0YTFlNTZmZS1iYTY1LTQwODItYTcyYi1iMzlhMjhkNzA5NDUiLCI1OGEyMjYwNy02NjZlLTQwMTYtOGZlMy00Y2U2MmEyMzVhNmUiLCJkNTYzNjVmZS0xNmJlLTQyMzktOWIyZi1kNmNhN2UyNDZkMzUiLCI2NDcwYTk5YS1lYTczLTQ4YTAtYmExZC03NWMxZWJkOGJhNTkiLCI0Njk0ZTBjYy05OWE2LTQ1MzMtODUwNi0xOWE3YTQ3MTBkOTUiLCJkZmEwYTUyNi04N2I4LTQ2NzAtOTJkNy00MDFhNjExZjU4ZjUiXSwianRpIjoiMWE4MWFmNWQtMDM1NC00OTM0LWFlNmYtM2ZlMGU3NDJhMDc1IiwiaWF0IjoxNzc1MDA0MjE4LCJleHAiOjE3NzUwOTA2MTh9.qfqqjLa32D8qngsRADN8_BFeT8LKyJ2pa4D3oMvXQDk","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"9569aa98-af93-4095-a8f6-695867c1b839","execution_status":"success"},{"action_id":"4a1e56fe-ba65-4082-a72b-b39a28d70945","execution_status":"success"},{"action_id":"58a22607-666e-4016-8fe3-4ce62a235a6e","execution_status":"success"},{"action_id":"d56365fe-16be-4239-9b2f-d6ca7e246d35","execution_status":"success"},{"action_id":"4694e0cc-99a6-4533-8506-19a7a4710d95","execution_status":"success"},{"action_id":"6470a99a-ea73-48a0-ba1d-75c1ebd8ba59","execution_status":"success"},{"action_id":"dfa0a526-87b8-4670-92d7-401a611f58f5","execution_status":"success"}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJmZTY2NzIzNS02MTQ5LTQ4MTMtODk1OS04YTFjOGFlMDc3ZGEiLCJncm91cF9pZCI6IjU5NWNiN2UzLTVmNGYtNDlhNC05YzQ4LTkzODhmMTM5ZjAxMiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI5NTY5YWE5OC1hZjkzLTQwOTUtYThmNi02OTU4NjdjMWI4MzkiLCI0YTFlNTZmZS1iYTY1LTQwODItYTcyYi1iMzlhMjhkNzA5NDUiLCI1OGEyMjYwNy02NjZlLTQwMTYtOGZlMy00Y2U2MmEyMzVhNmUiLCJkNTYzNjVmZS0xNmJlLTQyMzktOWIyZi1kNmNhN2UyNDZkMzUiLCI2NDcwYTk5YS1lYTczLTQ4YTAtYmExZC03NWMxZWJkOGJhNTkiLCI0Njk0ZTBjYy05OWE2LTQ1MzMtODUwNi0xOWE3YTQ3MTBkOTUiLCJkZmEwYTUyNi04N2I4LTQ2NzAtOTJkNy00MDFhNjExZjU4ZjUiXSwianRpIjoiMWE4MWFmNWQtMDM1NC00OTM0LWFlNmYtM2ZlMGU3NDJhMDc1IiwiaWF0IjoxNzc1MDA0MjE4LCJleHAiOjE3NzUwOTA2MTh9.qfqqjLa32D8qngsRADN8_BFeT8LKyJ2pa4D3oMvXQDk","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"9569aa98-af93-4095-a8f6-695867c1b839","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4a1e56fe-ba65-4082-a72b-b39a28d70945","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"58a22607-666e-4016-8fe3-4ce62a235a6e","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"d56365fe-16be-4239-9b2f-d6ca7e246d35","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4694e0cc-99a6-4533-8506-19a7a4710d95","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"6470a99a-ea73-48a0-ba1d-75c1ebd8ba59","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"dfa0a526-87b8-4670-92d7-401a611f58f5","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}]}'
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
