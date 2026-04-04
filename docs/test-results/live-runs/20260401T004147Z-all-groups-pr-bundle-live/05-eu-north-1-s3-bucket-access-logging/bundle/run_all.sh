#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI0NmE3ZjlkMC1hMGEwLTQzN2EtYTMwNS0yOTIzMTEwZjZiOGIiLCJncm91cF9pZCI6Ijk4NGU2ZjVlLWQxZTYtNDRhYS05MGU2LTFhM2RkYzE1MmEyYyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI2MGE0OTY0OS0zY2ZjLTQ1NjUtOWI5My0wYWE1ODU5MGEzMDgiLCJhN2FkMzUzYi0yOTI1LTQzY2MtYTVmZS1hMjRjYTM3N2I4MjUiLCI2Y2Y4YzVhMC1kMDMxLTQwZTUtYjI1NC0yZjRlYjA4YTlmNWQiLCJhZGMzMTgxOS0zMjAwLTRhMTUtYTI5OS05NzdhODA1OWNjOGIiLCI1YWIwYmExZS1kNmJhLTRmOGQtYjQ3OC1mYWIxODVkYzg0NGQiLCI5Y2U0YzNiZC02MzhiLTRjNTctYTYyOS1iM2NjZTk5MGQ5MmUiLCIxOWE5YjBmMC1kZTQ3LTRhNWItOTgyZi04ZDNjODc2YzIwNjQiLCJjYzNiYTM4Ny1mZWIwLTQyYTYtYTZiNi02ZTE4ZjJhMWRjNjUiLCI1MTAzODMxNS04NTViLTQxMTMtYTBkMC0wZGI4MzkxYWVlY2UiLCIwZmQ0MmY5MS1kMDE5LTRiOGItYTlhZS1jZGY5M2I5OWNkZWIiLCJmNzA0MDg1ZS02NDgxLTQzMDQtYWY2Ny1kNzM1OGFhNmRlMzAiLCIxZjNhZGI4OS01MzI1LTQzOWItODY3NS1mZWNlOWFmZWYwZWYiLCI2ZWZlYTM1OS04YzJhLTRiMjgtODE2NS1lZTYxNjkwYjVhOGUiLCJiZWQzNDQ3OC1mYzhhLTQ3MTQtYmI0MC1lNTJjZmJjOGJmOWIiLCIwMTk3ZGVhYy00OTY0LTQxYzUtOTJhMS1mMWVlM2MyMjRkYmIiLCJkMzIxNzJhMS00MjlhLTQyYzItYTE0NC0zMTA3NmJiYTMxNTAiXSwianRpIjoiYTBhNzYxYTctNjNmZC00OWEyLTgyZjQtNjMyYTRkMGQ2MzNiIiwiaWF0IjoxNzc1MDA0MTM5LCJleHAiOjE3NzUwOTA1Mzl9.C04Xpot44xwLt8b_t8bJWLf8caGxvLZBAa0vFuHIX-g
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI0NmE3ZjlkMC1hMGEwLTQzN2EtYTMwNS0yOTIzMTEwZjZiOGIiLCJncm91cF9pZCI6Ijk4NGU2ZjVlLWQxZTYtNDRhYS05MGU2LTFhM2RkYzE1MmEyYyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI2MGE0OTY0OS0zY2ZjLTQ1NjUtOWI5My0wYWE1ODU5MGEzMDgiLCJhN2FkMzUzYi0yOTI1LTQzY2MtYTVmZS1hMjRjYTM3N2I4MjUiLCI2Y2Y4YzVhMC1kMDMxLTQwZTUtYjI1NC0yZjRlYjA4YTlmNWQiLCJhZGMzMTgxOS0zMjAwLTRhMTUtYTI5OS05NzdhODA1OWNjOGIiLCI1YWIwYmExZS1kNmJhLTRmOGQtYjQ3OC1mYWIxODVkYzg0NGQiLCI5Y2U0YzNiZC02MzhiLTRjNTctYTYyOS1iM2NjZTk5MGQ5MmUiLCIxOWE5YjBmMC1kZTQ3LTRhNWItOTgyZi04ZDNjODc2YzIwNjQiLCJjYzNiYTM4Ny1mZWIwLTQyYTYtYTZiNi02ZTE4ZjJhMWRjNjUiLCI1MTAzODMxNS04NTViLTQxMTMtYTBkMC0wZGI4MzkxYWVlY2UiLCIwZmQ0MmY5MS1kMDE5LTRiOGItYTlhZS1jZGY5M2I5OWNkZWIiLCJmNzA0MDg1ZS02NDgxLTQzMDQtYWY2Ny1kNzM1OGFhNmRlMzAiLCIxZjNhZGI4OS01MzI1LTQzOWItODY3NS1mZWNlOWFmZWYwZWYiLCI2ZWZlYTM1OS04YzJhLTRiMjgtODE2NS1lZTYxNjkwYjVhOGUiLCJiZWQzNDQ3OC1mYzhhLTQ3MTQtYmI0MC1lNTJjZmJjOGJmOWIiLCIwMTk3ZGVhYy00OTY0LTQxYzUtOTJhMS1mMWVlM2MyMjRkYmIiLCJkMzIxNzJhMS00MjlhLTQyYzItYTE0NC0zMTA3NmJiYTMxNTAiXSwianRpIjoiYTBhNzYxYTctNjNmZC00OWEyLTgyZjQtNjMyYTRkMGQ2MzNiIiwiaWF0IjoxNzc1MDA0MTM5LCJleHAiOjE3NzUwOTA1Mzl9.C04Xpot44xwLt8b_t8bJWLf8caGxvLZBAa0vFuHIX-g","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI0NmE3ZjlkMC1hMGEwLTQzN2EtYTMwNS0yOTIzMTEwZjZiOGIiLCJncm91cF9pZCI6Ijk4NGU2ZjVlLWQxZTYtNDRhYS05MGU2LTFhM2RkYzE1MmEyYyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI2MGE0OTY0OS0zY2ZjLTQ1NjUtOWI5My0wYWE1ODU5MGEzMDgiLCJhN2FkMzUzYi0yOTI1LTQzY2MtYTVmZS1hMjRjYTM3N2I4MjUiLCI2Y2Y4YzVhMC1kMDMxLTQwZTUtYjI1NC0yZjRlYjA4YTlmNWQiLCJhZGMzMTgxOS0zMjAwLTRhMTUtYTI5OS05NzdhODA1OWNjOGIiLCI1YWIwYmExZS1kNmJhLTRmOGQtYjQ3OC1mYWIxODVkYzg0NGQiLCI5Y2U0YzNiZC02MzhiLTRjNTctYTYyOS1iM2NjZTk5MGQ5MmUiLCIxOWE5YjBmMC1kZTQ3LTRhNWItOTgyZi04ZDNjODc2YzIwNjQiLCJjYzNiYTM4Ny1mZWIwLTQyYTYtYTZiNi02ZTE4ZjJhMWRjNjUiLCI1MTAzODMxNS04NTViLTQxMTMtYTBkMC0wZGI4MzkxYWVlY2UiLCIwZmQ0MmY5MS1kMDE5LTRiOGItYTlhZS1jZGY5M2I5OWNkZWIiLCJmNzA0MDg1ZS02NDgxLTQzMDQtYWY2Ny1kNzM1OGFhNmRlMzAiLCIxZjNhZGI4OS01MzI1LTQzOWItODY3NS1mZWNlOWFmZWYwZWYiLCI2ZWZlYTM1OS04YzJhLTRiMjgtODE2NS1lZTYxNjkwYjVhOGUiLCJiZWQzNDQ3OC1mYzhhLTQ3MTQtYmI0MC1lNTJjZmJjOGJmOWIiLCIwMTk3ZGVhYy00OTY0LTQxYzUtOTJhMS1mMWVlM2MyMjRkYmIiLCJkMzIxNzJhMS00MjlhLTQyYzItYTE0NC0zMTA3NmJiYTMxNTAiXSwianRpIjoiYTBhNzYxYTctNjNmZC00OWEyLTgyZjQtNjMyYTRkMGQ2MzNiIiwiaWF0IjoxNzc1MDA0MTM5LCJleHAiOjE3NzUwOTA1Mzl9.C04Xpot44xwLt8b_t8bJWLf8caGxvLZBAa0vFuHIX-g","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"60a49649-3cfc-4565-9b93-0aa58590a308","execution_status":"success"},{"action_id":"a7ad353b-2925-43cc-a5fe-a24ca377b825","execution_status":"success"},{"action_id":"6cf8c5a0-d031-40e5-b254-2f4eb08a9f5d","execution_status":"success"},{"action_id":"adc31819-3200-4a15-a299-977a8059cc8b","execution_status":"success"},{"action_id":"5ab0ba1e-d6ba-4f8d-b478-fab185dc844d","execution_status":"success"},{"action_id":"9ce4c3bd-638b-4c57-a629-b3cce990d92e","execution_status":"success"},{"action_id":"19a9b0f0-de47-4a5b-982f-8d3c876c2064","execution_status":"success"},{"action_id":"51038315-855b-4113-a0d0-0db8391aeece","execution_status":"success"},{"action_id":"cc3ba387-feb0-42a6-a6b6-6e18f2a1dc65","execution_status":"success"},{"action_id":"f704085e-6481-4304-af67-d7358aa6de30","execution_status":"success"},{"action_id":"1f3adb89-5325-439b-8675-fece9afef0ef","execution_status":"success"},{"action_id":"6efea359-8c2a-4b28-8165-ee61690b5a8e","execution_status":"success"},{"action_id":"0197deac-4964-41c5-92a1-f1ee3c224dbb","execution_status":"success"},{"action_id":"d32172a1-429a-42c2-a144-31076bba3150","execution_status":"success"}],"non_executable_results":[{"action_id":"0fd42f91-d019-4b8b-a9ae-cdf93b99cdeb","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Source bucket scope could not be proven for S3 access logging; review the affected bucket relationship manually."]},{"action_id":"bed34478-fc8a-4714-bb40-e52cfbc8bf9b","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Log destination must be a dedicated bucket and cannot match the source bucket."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI0NmE3ZjlkMC1hMGEwLTQzN2EtYTMwNS0yOTIzMTEwZjZiOGIiLCJncm91cF9pZCI6Ijk4NGU2ZjVlLWQxZTYtNDRhYS05MGU2LTFhM2RkYzE1MmEyYyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI2MGE0OTY0OS0zY2ZjLTQ1NjUtOWI5My0wYWE1ODU5MGEzMDgiLCJhN2FkMzUzYi0yOTI1LTQzY2MtYTVmZS1hMjRjYTM3N2I4MjUiLCI2Y2Y4YzVhMC1kMDMxLTQwZTUtYjI1NC0yZjRlYjA4YTlmNWQiLCJhZGMzMTgxOS0zMjAwLTRhMTUtYTI5OS05NzdhODA1OWNjOGIiLCI1YWIwYmExZS1kNmJhLTRmOGQtYjQ3OC1mYWIxODVkYzg0NGQiLCI5Y2U0YzNiZC02MzhiLTRjNTctYTYyOS1iM2NjZTk5MGQ5MmUiLCIxOWE5YjBmMC1kZTQ3LTRhNWItOTgyZi04ZDNjODc2YzIwNjQiLCJjYzNiYTM4Ny1mZWIwLTQyYTYtYTZiNi02ZTE4ZjJhMWRjNjUiLCI1MTAzODMxNS04NTViLTQxMTMtYTBkMC0wZGI4MzkxYWVlY2UiLCIwZmQ0MmY5MS1kMDE5LTRiOGItYTlhZS1jZGY5M2I5OWNkZWIiLCJmNzA0MDg1ZS02NDgxLTQzMDQtYWY2Ny1kNzM1OGFhNmRlMzAiLCIxZjNhZGI4OS01MzI1LTQzOWItODY3NS1mZWNlOWFmZWYwZWYiLCI2ZWZlYTM1OS04YzJhLTRiMjgtODE2NS1lZTYxNjkwYjVhOGUiLCJiZWQzNDQ3OC1mYzhhLTQ3MTQtYmI0MC1lNTJjZmJjOGJmOWIiLCIwMTk3ZGVhYy00OTY0LTQxYzUtOTJhMS1mMWVlM2MyMjRkYmIiLCJkMzIxNzJhMS00MjlhLTQyYzItYTE0NC0zMTA3NmJiYTMxNTAiXSwianRpIjoiYTBhNzYxYTctNjNmZC00OWEyLTgyZjQtNjMyYTRkMGQ2MzNiIiwiaWF0IjoxNzc1MDA0MTM5LCJleHAiOjE3NzUwOTA1Mzl9.C04Xpot44xwLt8b_t8bJWLf8caGxvLZBAa0vFuHIX-g","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"60a49649-3cfc-4565-9b93-0aa58590a308","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"a7ad353b-2925-43cc-a5fe-a24ca377b825","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"6cf8c5a0-d031-40e5-b254-2f4eb08a9f5d","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"adc31819-3200-4a15-a299-977a8059cc8b","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"5ab0ba1e-d6ba-4f8d-b478-fab185dc844d","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"9ce4c3bd-638b-4c57-a629-b3cce990d92e","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"19a9b0f0-de47-4a5b-982f-8d3c876c2064","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"51038315-855b-4113-a0d0-0db8391aeece","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"cc3ba387-feb0-42a6-a6b6-6e18f2a1dc65","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"f704085e-6481-4304-af67-d7358aa6de30","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"1f3adb89-5325-439b-8675-fece9afef0ef","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"6efea359-8c2a-4b28-8165-ee61690b5a8e","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"0197deac-4964-41c5-92a1-f1ee3c224dbb","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"d32172a1-429a-42c2-a144-31076bba3150","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"0fd42f91-d019-4b8b-a9ae-cdf93b99cdeb","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Source bucket scope could not be proven for S3 access logging; review the affected bucket relationship manually."]},{"action_id":"bed34478-fc8a-4714-bb40-e52cfbc8bf9b","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Log destination must be a dedicated bucket and cannot match the source bucket."]}]}'
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
