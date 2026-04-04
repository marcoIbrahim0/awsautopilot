#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJiZTM2N2I2MS1hZjY0LTRiMTctYWUwYS03OWZhODFmMWYzZGUiLCJncm91cF9pZCI6Ijk3ZTUyMjA0LWY3ZjYtNDBjMS1iMmFjLWFjYjk5MzA4ZTI0MSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmNDdhMTFjZC04MDU1LTRiNTItODFjMy0yODM4ZTk2OTZmODAiLCI0NWQ3OTcwMi05OGY3LTRkZGMtOTY0Yy00YjhkOTFlMGUwNmIiLCIzOTczMmI5YS05NTZhLTRkZWItOTEzZC1kNjUyY2FkMjI1MjYiLCI4MTMwNjIxZi05YzdjLTRiN2MtODNjYi05Mzk3ZmIxNGM3Y2QiLCI5OThiOTY2My1jYzZmLTRiYWYtYTc5Ni05OWFlMjYxZjQ4MmMiLCI5MGE5NTA3YS03YTc0LTRlNmYtYTJmZi1iNzg3MTI3MTkzODgiLCJiYTA3ZGE5OS02MDBjLTRmZDItODA5MS0zZjFiN2Q1ZWNjMDIiLCI0NWQ3ZGQ4My1iYzMyLTQ3ODktYTVjZS1hNzFjZDRhMjE1Y2QiLCIxNTg5MWQwNi1jNjM5LTQ2OTItODgxZC0wNWZkY2NhNWQ1ODEiLCI0ZmU1ZDExZi04MWYxLTQ4ZjYtYjFlYi0yZmNhNTVjZWU5ZDkiLCJjNWM4Y2I3OS02ZTA4LTQzNDEtOTMwMS00ZTlmMjI3MmNiMGUiLCI3MjQ5NjE1YS1kMjk4LTQyNzgtOWY5Zi1lNDFhMDRjYjI4MTEiLCJiNzRiMTc0OC0yMjJhLTQ0ZjUtYmQwMi05M2QxZTNlYTVkMzQiLCJhN2Y5MjEwNi0yZGY4LTQ3NjgtYWFjMC0zNTgyNTBhYmRiN2IiLCIzOThhMTNjNy1kMWZjLTQ0ZjYtODYyMS1lYTdjNGJmOWRhODgiXSwianRpIjoiMjI1ZjQyNDItYTU0MS00NjFmLWE5MTAtMTdjM2EyNmU5ZWY1IiwiaWF0IjoxNzc1MDA0MTQ4LCJleHAiOjE3NzUwOTA1NDh9.DsfGFuJANSywX00mPGONkx5eTKOLuqX-CpGL8cbBZxw
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJiZTM2N2I2MS1hZjY0LTRiMTctYWUwYS03OWZhODFmMWYzZGUiLCJncm91cF9pZCI6Ijk3ZTUyMjA0LWY3ZjYtNDBjMS1iMmFjLWFjYjk5MzA4ZTI0MSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmNDdhMTFjZC04MDU1LTRiNTItODFjMy0yODM4ZTk2OTZmODAiLCI0NWQ3OTcwMi05OGY3LTRkZGMtOTY0Yy00YjhkOTFlMGUwNmIiLCIzOTczMmI5YS05NTZhLTRkZWItOTEzZC1kNjUyY2FkMjI1MjYiLCI4MTMwNjIxZi05YzdjLTRiN2MtODNjYi05Mzk3ZmIxNGM3Y2QiLCI5OThiOTY2My1jYzZmLTRiYWYtYTc5Ni05OWFlMjYxZjQ4MmMiLCI5MGE5NTA3YS03YTc0LTRlNmYtYTJmZi1iNzg3MTI3MTkzODgiLCJiYTA3ZGE5OS02MDBjLTRmZDItODA5MS0zZjFiN2Q1ZWNjMDIiLCI0NWQ3ZGQ4My1iYzMyLTQ3ODktYTVjZS1hNzFjZDRhMjE1Y2QiLCIxNTg5MWQwNi1jNjM5LTQ2OTItODgxZC0wNWZkY2NhNWQ1ODEiLCI0ZmU1ZDExZi04MWYxLTQ4ZjYtYjFlYi0yZmNhNTVjZWU5ZDkiLCJjNWM4Y2I3OS02ZTA4LTQzNDEtOTMwMS00ZTlmMjI3MmNiMGUiLCI3MjQ5NjE1YS1kMjk4LTQyNzgtOWY5Zi1lNDFhMDRjYjI4MTEiLCJiNzRiMTc0OC0yMjJhLTQ0ZjUtYmQwMi05M2QxZTNlYTVkMzQiLCJhN2Y5MjEwNi0yZGY4LTQ3NjgtYWFjMC0zNTgyNTBhYmRiN2IiLCIzOThhMTNjNy1kMWZjLTQ0ZjYtODYyMS1lYTdjNGJmOWRhODgiXSwianRpIjoiMjI1ZjQyNDItYTU0MS00NjFmLWE5MTAtMTdjM2EyNmU5ZWY1IiwiaWF0IjoxNzc1MDA0MTQ4LCJleHAiOjE3NzUwOTA1NDh9.DsfGFuJANSywX00mPGONkx5eTKOLuqX-CpGL8cbBZxw","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJiZTM2N2I2MS1hZjY0LTRiMTctYWUwYS03OWZhODFmMWYzZGUiLCJncm91cF9pZCI6Ijk3ZTUyMjA0LWY3ZjYtNDBjMS1iMmFjLWFjYjk5MzA4ZTI0MSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmNDdhMTFjZC04MDU1LTRiNTItODFjMy0yODM4ZTk2OTZmODAiLCI0NWQ3OTcwMi05OGY3LTRkZGMtOTY0Yy00YjhkOTFlMGUwNmIiLCIzOTczMmI5YS05NTZhLTRkZWItOTEzZC1kNjUyY2FkMjI1MjYiLCI4MTMwNjIxZi05YzdjLTRiN2MtODNjYi05Mzk3ZmIxNGM3Y2QiLCI5OThiOTY2My1jYzZmLTRiYWYtYTc5Ni05OWFlMjYxZjQ4MmMiLCI5MGE5NTA3YS03YTc0LTRlNmYtYTJmZi1iNzg3MTI3MTkzODgiLCJiYTA3ZGE5OS02MDBjLTRmZDItODA5MS0zZjFiN2Q1ZWNjMDIiLCI0NWQ3ZGQ4My1iYzMyLTQ3ODktYTVjZS1hNzFjZDRhMjE1Y2QiLCIxNTg5MWQwNi1jNjM5LTQ2OTItODgxZC0wNWZkY2NhNWQ1ODEiLCI0ZmU1ZDExZi04MWYxLTQ4ZjYtYjFlYi0yZmNhNTVjZWU5ZDkiLCJjNWM4Y2I3OS02ZTA4LTQzNDEtOTMwMS00ZTlmMjI3MmNiMGUiLCI3MjQ5NjE1YS1kMjk4LTQyNzgtOWY5Zi1lNDFhMDRjYjI4MTEiLCJiNzRiMTc0OC0yMjJhLTQ0ZjUtYmQwMi05M2QxZTNlYTVkMzQiLCJhN2Y5MjEwNi0yZGY4LTQ3NjgtYWFjMC0zNTgyNTBhYmRiN2IiLCIzOThhMTNjNy1kMWZjLTQ0ZjYtODYyMS1lYTdjNGJmOWRhODgiXSwianRpIjoiMjI1ZjQyNDItYTU0MS00NjFmLWE5MTAtMTdjM2EyNmU5ZWY1IiwiaWF0IjoxNzc1MDA0MTQ4LCJleHAiOjE3NzUwOTA1NDh9.DsfGFuJANSywX00mPGONkx5eTKOLuqX-CpGL8cbBZxw","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"f47a11cd-8055-4b52-81c3-2838e9696f80","execution_status":"success"},{"action_id":"45d79702-98f7-4ddc-964c-4b8d91e0e06b","execution_status":"success"},{"action_id":"39732b9a-956a-4deb-913d-d652cad22526","execution_status":"success"},{"action_id":"8130621f-9c7c-4b7c-83cb-9397fb14c7cd","execution_status":"success"},{"action_id":"998b9663-cc6f-4baf-a796-99ae261f482c","execution_status":"success"},{"action_id":"90a9507a-7a74-4e6f-a2ff-b78712719388","execution_status":"success"},{"action_id":"ba07da99-600c-4fd2-8091-3f1b7d5ecc02","execution_status":"success"},{"action_id":"45d7dd83-bc32-4789-a5ce-a71cd4a215cd","execution_status":"success"},{"action_id":"15891d06-c639-4692-881d-05fdcca5d581","execution_status":"success"},{"action_id":"4fe5d11f-81f1-48f6-b1eb-2fca55cee9d9","execution_status":"success"},{"action_id":"c5c8cb79-6e08-4341-9301-4e9f2272cb0e","execution_status":"success"},{"action_id":"7249615a-d298-4278-9f9f-e41a04cb2811","execution_status":"success"},{"action_id":"b74b1748-222a-44f5-bd02-93d1e3ea5d34","execution_status":"success"},{"action_id":"a7f92106-2df8-4768-aac0-358250abdb7b","execution_status":"success"},{"action_id":"398a13c7-d1fc-44f6-8621-ea7c4bf9da88","execution_status":"success"}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJiZTM2N2I2MS1hZjY0LTRiMTctYWUwYS03OWZhODFmMWYzZGUiLCJncm91cF9pZCI6Ijk3ZTUyMjA0LWY3ZjYtNDBjMS1iMmFjLWFjYjk5MzA4ZTI0MSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmNDdhMTFjZC04MDU1LTRiNTItODFjMy0yODM4ZTk2OTZmODAiLCI0NWQ3OTcwMi05OGY3LTRkZGMtOTY0Yy00YjhkOTFlMGUwNmIiLCIzOTczMmI5YS05NTZhLTRkZWItOTEzZC1kNjUyY2FkMjI1MjYiLCI4MTMwNjIxZi05YzdjLTRiN2MtODNjYi05Mzk3ZmIxNGM3Y2QiLCI5OThiOTY2My1jYzZmLTRiYWYtYTc5Ni05OWFlMjYxZjQ4MmMiLCI5MGE5NTA3YS03YTc0LTRlNmYtYTJmZi1iNzg3MTI3MTkzODgiLCJiYTA3ZGE5OS02MDBjLTRmZDItODA5MS0zZjFiN2Q1ZWNjMDIiLCI0NWQ3ZGQ4My1iYzMyLTQ3ODktYTVjZS1hNzFjZDRhMjE1Y2QiLCIxNTg5MWQwNi1jNjM5LTQ2OTItODgxZC0wNWZkY2NhNWQ1ODEiLCI0ZmU1ZDExZi04MWYxLTQ4ZjYtYjFlYi0yZmNhNTVjZWU5ZDkiLCJjNWM4Y2I3OS02ZTA4LTQzNDEtOTMwMS00ZTlmMjI3MmNiMGUiLCI3MjQ5NjE1YS1kMjk4LTQyNzgtOWY5Zi1lNDFhMDRjYjI4MTEiLCJiNzRiMTc0OC0yMjJhLTQ0ZjUtYmQwMi05M2QxZTNlYTVkMzQiLCJhN2Y5MjEwNi0yZGY4LTQ3NjgtYWFjMC0zNTgyNTBhYmRiN2IiLCIzOThhMTNjNy1kMWZjLTQ0ZjYtODYyMS1lYTdjNGJmOWRhODgiXSwianRpIjoiMjI1ZjQyNDItYTU0MS00NjFmLWE5MTAtMTdjM2EyNmU5ZWY1IiwiaWF0IjoxNzc1MDA0MTQ4LCJleHAiOjE3NzUwOTA1NDh9.DsfGFuJANSywX00mPGONkx5eTKOLuqX-CpGL8cbBZxw","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"f47a11cd-8055-4b52-81c3-2838e9696f80","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"45d79702-98f7-4ddc-964c-4b8d91e0e06b","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"39732b9a-956a-4deb-913d-d652cad22526","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"8130621f-9c7c-4b7c-83cb-9397fb14c7cd","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"998b9663-cc6f-4baf-a796-99ae261f482c","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"90a9507a-7a74-4e6f-a2ff-b78712719388","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"ba07da99-600c-4fd2-8091-3f1b7d5ecc02","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"45d7dd83-bc32-4789-a5ce-a71cd4a215cd","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"15891d06-c639-4692-881d-05fdcca5d581","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4fe5d11f-81f1-48f6-b1eb-2fca55cee9d9","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"c5c8cb79-6e08-4341-9301-4e9f2272cb0e","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"7249615a-d298-4278-9f9f-e41a04cb2811","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"b74b1748-222a-44f5-bd02-93d1e3ea5d34","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"a7f92106-2df8-4768-aac0-358250abdb7b","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"398a13c7-d1fc-44f6-8621-ea7c4bf9da88","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}]}'
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
