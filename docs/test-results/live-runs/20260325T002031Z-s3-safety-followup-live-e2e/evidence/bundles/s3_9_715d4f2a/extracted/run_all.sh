#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJjMzM1MWEwMi0wYmMyLTQ0NDktYmVlZC1kNTlkN2FjOTM3ZDAiLCJncm91cF9ydW5faWQiOiI2N2E2YjcyNy04MDhmLTRmODItYTdjNC1lZTcxMTIwM2NmNzIiLCJncm91cF9pZCI6IjhkMGI4MzFkLThjMzctNDhlYi1iMWYyLTA5OWQ2MjcxZmFhYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJlOWNhNGExMi05MGU4LTQzMTItODJlYy1mYWRmZWE4MmE3Y2UiLCIwYjc1YzUzMi0wYTk0LTQwN2ItODE3NC0wYWU4Yzg1ZjIzZjUiLCIwMTU1N2UwNC04OTgwLTQ1NTQtOGMzMi01YTdlNzhkM2NiZjMiLCIxZGM2MTJkOC0xOTMwLTQ5MjAtYmIxMS02YWQ4YmE0ZmUyNmIiLCIzZGQ2Njk2Mi0yYmVmLTRjYWEtOTYyNy0yZjA1NmViYWJiZDciLCI0ZDZhMTUyMC0zZWQ1LTRmNDctODU3ZS1lNmJiOGNlNjE2MDYiLCI0ZDgxZTYzYi0wNGU2LTQ5MDktOTc4YS1lNzc5ZDYzYWU3MjEiLCI1MDEwMjFmMC1lZTM5LTQ2OTItOTVjMS0xZDdjMDcxMzRjNzEiLCI2MDY5ZWM0OS1hOGIxLTQ3ZGYtYWNlOC0xNTNjMTEwY2Q5ODQiLCJkY2Q5YWFjMC0zMjA1LTRjMWYtYTM2MC04YmU0OTJhYzM4NGYiLCJlMDNmOWY2My1lODk1LTQ2YTMtOTNiMy03NmMxNmEwYTZlZTUiLCJlN2ViNDYzZC03MTA4LTRkZmYtYmE1YS03YmE4ZjIyNjYxNDIiLCJlOGFlMmE0MS05YTNmLTQzYzAtOGQ4OS1lNTc0MzExYmYxNDgiLCIwYzQ5MDI0MC1mM2I1LTQyYjItOTRjZS0wMTBhZTY3YmQ3OWYiXSwianRpIjoiM2Y3MDU2ODYtNTAwNy00ZmU3LWFiOTAtM2ZlOTc2ODhiMTdhIiwiaWF0IjoxNzc0NDAzMTc4LCJleHAiOjE3NzQ0ODk1Nzh9.oNCRZoWU0a5oQceM8ubdShKn8Ws5LerFjkgdRKVuMMc
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJjMzM1MWEwMi0wYmMyLTQ0NDktYmVlZC1kNTlkN2FjOTM3ZDAiLCJncm91cF9ydW5faWQiOiI2N2E2YjcyNy04MDhmLTRmODItYTdjNC1lZTcxMTIwM2NmNzIiLCJncm91cF9pZCI6IjhkMGI4MzFkLThjMzctNDhlYi1iMWYyLTA5OWQ2MjcxZmFhYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJlOWNhNGExMi05MGU4LTQzMTItODJlYy1mYWRmZWE4MmE3Y2UiLCIwYjc1YzUzMi0wYTk0LTQwN2ItODE3NC0wYWU4Yzg1ZjIzZjUiLCIwMTU1N2UwNC04OTgwLTQ1NTQtOGMzMi01YTdlNzhkM2NiZjMiLCIxZGM2MTJkOC0xOTMwLTQ5MjAtYmIxMS02YWQ4YmE0ZmUyNmIiLCIzZGQ2Njk2Mi0yYmVmLTRjYWEtOTYyNy0yZjA1NmViYWJiZDciLCI0ZDZhMTUyMC0zZWQ1LTRmNDctODU3ZS1lNmJiOGNlNjE2MDYiLCI0ZDgxZTYzYi0wNGU2LTQ5MDktOTc4YS1lNzc5ZDYzYWU3MjEiLCI1MDEwMjFmMC1lZTM5LTQ2OTItOTVjMS0xZDdjMDcxMzRjNzEiLCI2MDY5ZWM0OS1hOGIxLTQ3ZGYtYWNlOC0xNTNjMTEwY2Q5ODQiLCJkY2Q5YWFjMC0zMjA1LTRjMWYtYTM2MC04YmU0OTJhYzM4NGYiLCJlMDNmOWY2My1lODk1LTQ2YTMtOTNiMy03NmMxNmEwYTZlZTUiLCJlN2ViNDYzZC03MTA4LTRkZmYtYmE1YS03YmE4ZjIyNjYxNDIiLCJlOGFlMmE0MS05YTNmLTQzYzAtOGQ4OS1lNTc0MzExYmYxNDgiLCIwYzQ5MDI0MC1mM2I1LTQyYjItOTRjZS0wMTBhZTY3YmQ3OWYiXSwianRpIjoiM2Y3MDU2ODYtNTAwNy00ZmU3LWFiOTAtM2ZlOTc2ODhiMTdhIiwiaWF0IjoxNzc0NDAzMTc4LCJleHAiOjE3NzQ0ODk1Nzh9.oNCRZoWU0a5oQceM8ubdShKn8Ws5LerFjkgdRKVuMMc","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJjMzM1MWEwMi0wYmMyLTQ0NDktYmVlZC1kNTlkN2FjOTM3ZDAiLCJncm91cF9ydW5faWQiOiI2N2E2YjcyNy04MDhmLTRmODItYTdjNC1lZTcxMTIwM2NmNzIiLCJncm91cF9pZCI6IjhkMGI4MzFkLThjMzctNDhlYi1iMWYyLTA5OWQ2MjcxZmFhYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJlOWNhNGExMi05MGU4LTQzMTItODJlYy1mYWRmZWE4MmE3Y2UiLCIwYjc1YzUzMi0wYTk0LTQwN2ItODE3NC0wYWU4Yzg1ZjIzZjUiLCIwMTU1N2UwNC04OTgwLTQ1NTQtOGMzMi01YTdlNzhkM2NiZjMiLCIxZGM2MTJkOC0xOTMwLTQ5MjAtYmIxMS02YWQ4YmE0ZmUyNmIiLCIzZGQ2Njk2Mi0yYmVmLTRjYWEtOTYyNy0yZjA1NmViYWJiZDciLCI0ZDZhMTUyMC0zZWQ1LTRmNDctODU3ZS1lNmJiOGNlNjE2MDYiLCI0ZDgxZTYzYi0wNGU2LTQ5MDktOTc4YS1lNzc5ZDYzYWU3MjEiLCI1MDEwMjFmMC1lZTM5LTQ2OTItOTVjMS0xZDdjMDcxMzRjNzEiLCI2MDY5ZWM0OS1hOGIxLTQ3ZGYtYWNlOC0xNTNjMTEwY2Q5ODQiLCJkY2Q5YWFjMC0zMjA1LTRjMWYtYTM2MC04YmU0OTJhYzM4NGYiLCJlMDNmOWY2My1lODk1LTQ2YTMtOTNiMy03NmMxNmEwYTZlZTUiLCJlN2ViNDYzZC03MTA4LTRkZmYtYmE1YS03YmE4ZjIyNjYxNDIiLCJlOGFlMmE0MS05YTNmLTQzYzAtOGQ4OS1lNTc0MzExYmYxNDgiLCIwYzQ5MDI0MC1mM2I1LTQyYjItOTRjZS0wMTBhZTY3YmQ3OWYiXSwianRpIjoiM2Y3MDU2ODYtNTAwNy00ZmU3LWFiOTAtM2ZlOTc2ODhiMTdhIiwiaWF0IjoxNzc0NDAzMTc4LCJleHAiOjE3NzQ0ODk1Nzh9.oNCRZoWU0a5oQceM8ubdShKn8Ws5LerFjkgdRKVuMMc","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"01557e04-8980-4554-8c32-5a7e78d3cbf3","execution_status":"success"},{"action_id":"0b75c532-0a94-407b-8174-0ae8c85f23f5","execution_status":"success"},{"action_id":"1dc612d8-1930-4920-bb11-6ad8ba4fe26b","execution_status":"success"},{"action_id":"3dd66962-2bef-4caa-9627-2f056ebabbd7","execution_status":"success"},{"action_id":"4d6a1520-3ed5-4f47-857e-e6bb8ce61606","execution_status":"success"},{"action_id":"4d81e63b-04e6-4909-978a-e779d63ae721","execution_status":"success"},{"action_id":"501021f0-ee39-4692-95c1-1d7c07134c71","execution_status":"success"},{"action_id":"6069ec49-a8b1-47df-ace8-153c110cd984","execution_status":"success"},{"action_id":"dcd9aac0-3205-4c1f-a360-8be492ac384f","execution_status":"success"},{"action_id":"e03f9f63-e895-46a3-93b3-76c16a0a6ee5","execution_status":"success"},{"action_id":"e7eb463d-7108-4dff-ba5a-7ba8f2266142","execution_status":"success"},{"action_id":"e8ae2a41-9a3f-43c0-8d89-e574311bf148","execution_status":"success"},{"action_id":"e9ca4a12-90e8-4312-82ec-fadfea82a7ce","execution_status":"success"}],"non_executable_results":[{"action_id":"0c490240-f3b5-42b2-94ce-010ae67bd79f","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_create_destination_bucket","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJjMzM1MWEwMi0wYmMyLTQ0NDktYmVlZC1kNTlkN2FjOTM3ZDAiLCJncm91cF9ydW5faWQiOiI2N2E2YjcyNy04MDhmLTRmODItYTdjNC1lZTcxMTIwM2NmNzIiLCJncm91cF9pZCI6IjhkMGI4MzFkLThjMzctNDhlYi1iMWYyLTA5OWQ2MjcxZmFhYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJlOWNhNGExMi05MGU4LTQzMTItODJlYy1mYWRmZWE4MmE3Y2UiLCIwYjc1YzUzMi0wYTk0LTQwN2ItODE3NC0wYWU4Yzg1ZjIzZjUiLCIwMTU1N2UwNC04OTgwLTQ1NTQtOGMzMi01YTdlNzhkM2NiZjMiLCIxZGM2MTJkOC0xOTMwLTQ5MjAtYmIxMS02YWQ4YmE0ZmUyNmIiLCIzZGQ2Njk2Mi0yYmVmLTRjYWEtOTYyNy0yZjA1NmViYWJiZDciLCI0ZDZhMTUyMC0zZWQ1LTRmNDctODU3ZS1lNmJiOGNlNjE2MDYiLCI0ZDgxZTYzYi0wNGU2LTQ5MDktOTc4YS1lNzc5ZDYzYWU3MjEiLCI1MDEwMjFmMC1lZTM5LTQ2OTItOTVjMS0xZDdjMDcxMzRjNzEiLCI2MDY5ZWM0OS1hOGIxLTQ3ZGYtYWNlOC0xNTNjMTEwY2Q5ODQiLCJkY2Q5YWFjMC0zMjA1LTRjMWYtYTM2MC04YmU0OTJhYzM4NGYiLCJlMDNmOWY2My1lODk1LTQ2YTMtOTNiMy03NmMxNmEwYTZlZTUiLCJlN2ViNDYzZC03MTA4LTRkZmYtYmE1YS03YmE4ZjIyNjYxNDIiLCJlOGFlMmE0MS05YTNmLTQzYzAtOGQ4OS1lNTc0MzExYmYxNDgiLCIwYzQ5MDI0MC1mM2I1LTQyYjItOTRjZS0wMTBhZTY3YmQ3OWYiXSwianRpIjoiM2Y3MDU2ODYtNTAwNy00ZmU3LWFiOTAtM2ZlOTc2ODhiMTdhIiwiaWF0IjoxNzc0NDAzMTc4LCJleHAiOjE3NzQ0ODk1Nzh9.oNCRZoWU0a5oQceM8ubdShKn8Ws5LerFjkgdRKVuMMc","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"01557e04-8980-4554-8c32-5a7e78d3cbf3","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"0b75c532-0a94-407b-8174-0ae8c85f23f5","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"1dc612d8-1930-4920-bb11-6ad8ba4fe26b","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"3dd66962-2bef-4caa-9627-2f056ebabbd7","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4d6a1520-3ed5-4f47-857e-e6bb8ce61606","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4d81e63b-04e6-4909-978a-e779d63ae721","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"501021f0-ee39-4692-95c1-1d7c07134c71","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"6069ec49-a8b1-47df-ace8-153c110cd984","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"dcd9aac0-3205-4c1f-a360-8be492ac384f","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e03f9f63-e895-46a3-93b3-76c16a0a6ee5","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e7eb463d-7108-4dff-ba5a-7ba8f2266142","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e8ae2a41-9a3f-43c0-8d89-e574311bf148","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e9ca4a12-90e8-4312-82ec-fadfea82a7ce","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"0c490240-f3b5-42b2-94ce-010ae67bd79f","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_create_destination_bucket","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]}]}'
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
