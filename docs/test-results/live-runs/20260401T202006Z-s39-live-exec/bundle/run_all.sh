#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiIzYjU5ZTQ5OC0yNmE5LTQxOWQtYWMwMS03N2E5ZGNjODdkZmQiLCJncm91cF9pZCI6ImZjNTViZWE2LWM4NWMtNGM5NC1hNjk0LTY0MzY4ZWE0MmQ0ZiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI0YzhjOTA0YS0xNjgzLTRiMjktYWI5Ny0zYjZlYjFiNTAyNjAiLCJlNTdkMTQ1Mi01MDljLTQyY2ItOTk2ZC0xNzUyYzk2N2NlZmUiLCJlOTdmZmVmOC1mNmY5LTQ0MTctYWM5OS0wZTgzMzA1ZGY3MTgiLCJmNjdhOTA2NC0yYTVmLTQ3ZmQtODIwYy0xNTc5N2YzNTRjN2MiLCI3NzBhNGYxOC0zODU4LTRlZmQtODk3My1hMzlkMTU0ZmE5MTkiLCI4MjA3MmJmYS03NzA3LTQxMWItYWI1YS00YjhhNzViZWYxMDQiLCI2YmE2NTIyYy1hMWQ5LTQ4YmQtYWI5Ni1iNjEyOWY0MzYzYjgiLCI4ZjY0ZGQ4NC03NjNjLTQwODEtYWQxZS05YTM2NzU3YjVjODciLCI4NDk5ZTIyNi1kM2U4LTQwMzEtYjIyNS05ZjkwNTE2MGVmNWYiLCJlY2U4YTk2ZS04ZTljLTQ0ZGUtYTcxNS1kMGI3Y2FhMDYxYzEiLCJmOTUzNTE3My0zZGUxLTQ0ZDAtODU4My1lZTkzN2UxYWQ4MTEiLCJhOGEwNmFkZS02N2I5LTRiNWItODlkZi0xZjRmNDMwMDM2YTUiLCIzMThjOGIxZC0wYTkzLTQzZjAtOWIzMi0yNDAxNGI2ZGJmMTUiLCIyNTdiYzExZS1jNTIyLTQ0MTktOGFmNS1iZTI0YWU0MDY2OTEiXSwianRpIjoiNDA0OWNmYzUtMTdiNS00YzE3LThmYTQtMDhmODM1OGI3YTRlIiwiaWF0IjoxNzc1MDc0ODExLCJleHAiOjE3NzUxNjEyMTF9.LZ0_Sia2_pRhqIfAkP21IesjyRUAsfgmcrzlNLg9UkA
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiIzYjU5ZTQ5OC0yNmE5LTQxOWQtYWMwMS03N2E5ZGNjODdkZmQiLCJncm91cF9pZCI6ImZjNTViZWE2LWM4NWMtNGM5NC1hNjk0LTY0MzY4ZWE0MmQ0ZiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI0YzhjOTA0YS0xNjgzLTRiMjktYWI5Ny0zYjZlYjFiNTAyNjAiLCJlNTdkMTQ1Mi01MDljLTQyY2ItOTk2ZC0xNzUyYzk2N2NlZmUiLCJlOTdmZmVmOC1mNmY5LTQ0MTctYWM5OS0wZTgzMzA1ZGY3MTgiLCJmNjdhOTA2NC0yYTVmLTQ3ZmQtODIwYy0xNTc5N2YzNTRjN2MiLCI3NzBhNGYxOC0zODU4LTRlZmQtODk3My1hMzlkMTU0ZmE5MTkiLCI4MjA3MmJmYS03NzA3LTQxMWItYWI1YS00YjhhNzViZWYxMDQiLCI2YmE2NTIyYy1hMWQ5LTQ4YmQtYWI5Ni1iNjEyOWY0MzYzYjgiLCI4ZjY0ZGQ4NC03NjNjLTQwODEtYWQxZS05YTM2NzU3YjVjODciLCI4NDk5ZTIyNi1kM2U4LTQwMzEtYjIyNS05ZjkwNTE2MGVmNWYiLCJlY2U4YTk2ZS04ZTljLTQ0ZGUtYTcxNS1kMGI3Y2FhMDYxYzEiLCJmOTUzNTE3My0zZGUxLTQ0ZDAtODU4My1lZTkzN2UxYWQ4MTEiLCJhOGEwNmFkZS02N2I5LTRiNWItODlkZi0xZjRmNDMwMDM2YTUiLCIzMThjOGIxZC0wYTkzLTQzZjAtOWIzMi0yNDAxNGI2ZGJmMTUiLCIyNTdiYzExZS1jNTIyLTQ0MTktOGFmNS1iZTI0YWU0MDY2OTEiXSwianRpIjoiNDA0OWNmYzUtMTdiNS00YzE3LThmYTQtMDhmODM1OGI3YTRlIiwiaWF0IjoxNzc1MDc0ODExLCJleHAiOjE3NzUxNjEyMTF9.LZ0_Sia2_pRhqIfAkP21IesjyRUAsfgmcrzlNLg9UkA","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiIzYjU5ZTQ5OC0yNmE5LTQxOWQtYWMwMS03N2E5ZGNjODdkZmQiLCJncm91cF9pZCI6ImZjNTViZWE2LWM4NWMtNGM5NC1hNjk0LTY0MzY4ZWE0MmQ0ZiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI0YzhjOTA0YS0xNjgzLTRiMjktYWI5Ny0zYjZlYjFiNTAyNjAiLCJlNTdkMTQ1Mi01MDljLTQyY2ItOTk2ZC0xNzUyYzk2N2NlZmUiLCJlOTdmZmVmOC1mNmY5LTQ0MTctYWM5OS0wZTgzMzA1ZGY3MTgiLCJmNjdhOTA2NC0yYTVmLTQ3ZmQtODIwYy0xNTc5N2YzNTRjN2MiLCI3NzBhNGYxOC0zODU4LTRlZmQtODk3My1hMzlkMTU0ZmE5MTkiLCI4MjA3MmJmYS03NzA3LTQxMWItYWI1YS00YjhhNzViZWYxMDQiLCI2YmE2NTIyYy1hMWQ5LTQ4YmQtYWI5Ni1iNjEyOWY0MzYzYjgiLCI4ZjY0ZGQ4NC03NjNjLTQwODEtYWQxZS05YTM2NzU3YjVjODciLCI4NDk5ZTIyNi1kM2U4LTQwMzEtYjIyNS05ZjkwNTE2MGVmNWYiLCJlY2U4YTk2ZS04ZTljLTQ0ZGUtYTcxNS1kMGI3Y2FhMDYxYzEiLCJmOTUzNTE3My0zZGUxLTQ0ZDAtODU4My1lZTkzN2UxYWQ4MTEiLCJhOGEwNmFkZS02N2I5LTRiNWItODlkZi0xZjRmNDMwMDM2YTUiLCIzMThjOGIxZC0wYTkzLTQzZjAtOWIzMi0yNDAxNGI2ZGJmMTUiLCIyNTdiYzExZS1jNTIyLTQ0MTktOGFmNS1iZTI0YWU0MDY2OTEiXSwianRpIjoiNDA0OWNmYzUtMTdiNS00YzE3LThmYTQtMDhmODM1OGI3YTRlIiwiaWF0IjoxNzc1MDc0ODExLCJleHAiOjE3NzUxNjEyMTF9.LZ0_Sia2_pRhqIfAkP21IesjyRUAsfgmcrzlNLg9UkA","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"4c8c904a-1683-4b29-ab97-3b6eb1b50260","execution_status":"success"},{"action_id":"e57d1452-509c-42cb-996d-1752c967cefe","execution_status":"success"},{"action_id":"6ba6522c-a1d9-48bd-ab96-b6129f4363b8","execution_status":"success"},{"action_id":"770a4f18-3858-4efd-8973-a39d154fa919","execution_status":"success"},{"action_id":"82072bfa-7707-411b-ab5a-4b8a75bef104","execution_status":"success"},{"action_id":"e97ffef8-f6f9-4417-ac99-0e83305df718","execution_status":"success"},{"action_id":"f67a9064-2a5f-47fd-820c-15797f354c7c","execution_status":"success"},{"action_id":"8f64dd84-763c-4081-ad1e-9a36757b5c87","execution_status":"success"},{"action_id":"318c8b1d-0a93-43f0-9b32-24014b6dbf15","execution_status":"success"},{"action_id":"8499e226-d3e8-4031-b225-9f905160ef5f","execution_status":"success"},{"action_id":"a8a06ade-67b9-4b5b-89df-1f4f430036a5","execution_status":"success"},{"action_id":"ece8a96e-8e9c-44de-a715-d0b7caa061c1","execution_status":"success"},{"action_id":"f9535173-3de1-44d0-8583-ee937e1ad811","execution_status":"success"}],"non_executable_results":[{"action_id":"257bc11e-c522-4419-8af5-be24ae406691","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Source bucket scope could not be proven for S3 access logging; review the affected bucket relationship manually."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiIzYjU5ZTQ5OC0yNmE5LTQxOWQtYWMwMS03N2E5ZGNjODdkZmQiLCJncm91cF9pZCI6ImZjNTViZWE2LWM4NWMtNGM5NC1hNjk0LTY0MzY4ZWE0MmQ0ZiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI0YzhjOTA0YS0xNjgzLTRiMjktYWI5Ny0zYjZlYjFiNTAyNjAiLCJlNTdkMTQ1Mi01MDljLTQyY2ItOTk2ZC0xNzUyYzk2N2NlZmUiLCJlOTdmZmVmOC1mNmY5LTQ0MTctYWM5OS0wZTgzMzA1ZGY3MTgiLCJmNjdhOTA2NC0yYTVmLTQ3ZmQtODIwYy0xNTc5N2YzNTRjN2MiLCI3NzBhNGYxOC0zODU4LTRlZmQtODk3My1hMzlkMTU0ZmE5MTkiLCI4MjA3MmJmYS03NzA3LTQxMWItYWI1YS00YjhhNzViZWYxMDQiLCI2YmE2NTIyYy1hMWQ5LTQ4YmQtYWI5Ni1iNjEyOWY0MzYzYjgiLCI4ZjY0ZGQ4NC03NjNjLTQwODEtYWQxZS05YTM2NzU3YjVjODciLCI4NDk5ZTIyNi1kM2U4LTQwMzEtYjIyNS05ZjkwNTE2MGVmNWYiLCJlY2U4YTk2ZS04ZTljLTQ0ZGUtYTcxNS1kMGI3Y2FhMDYxYzEiLCJmOTUzNTE3My0zZGUxLTQ0ZDAtODU4My1lZTkzN2UxYWQ4MTEiLCJhOGEwNmFkZS02N2I5LTRiNWItODlkZi0xZjRmNDMwMDM2YTUiLCIzMThjOGIxZC0wYTkzLTQzZjAtOWIzMi0yNDAxNGI2ZGJmMTUiLCIyNTdiYzExZS1jNTIyLTQ0MTktOGFmNS1iZTI0YWU0MDY2OTEiXSwianRpIjoiNDA0OWNmYzUtMTdiNS00YzE3LThmYTQtMDhmODM1OGI3YTRlIiwiaWF0IjoxNzc1MDc0ODExLCJleHAiOjE3NzUxNjEyMTF9.LZ0_Sia2_pRhqIfAkP21IesjyRUAsfgmcrzlNLg9UkA","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"4c8c904a-1683-4b29-ab97-3b6eb1b50260","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e57d1452-509c-42cb-996d-1752c967cefe","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"6ba6522c-a1d9-48bd-ab96-b6129f4363b8","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"770a4f18-3858-4efd-8973-a39d154fa919","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"82072bfa-7707-411b-ab5a-4b8a75bef104","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e97ffef8-f6f9-4417-ac99-0e83305df718","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"f67a9064-2a5f-47fd-820c-15797f354c7c","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"8f64dd84-763c-4081-ad1e-9a36757b5c87","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"318c8b1d-0a93-43f0-9b32-24014b6dbf15","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"8499e226-d3e8-4031-b225-9f905160ef5f","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"a8a06ade-67b9-4b5b-89df-1f4f430036a5","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"ece8a96e-8e9c-44de-a715-d0b7caa061c1","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"f9535173-3de1-44d0-8583-ee937e1ad811","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"257bc11e-c522-4419-8af5-be24ae406691","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Source bucket scope could not be proven for S3 access logging; review the affected bucket relationship manually."]}]}'
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
