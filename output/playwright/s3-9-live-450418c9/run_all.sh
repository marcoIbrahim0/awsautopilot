#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=<REDACTED_TOKEN>
STARTED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"9482c713-7184-4e01-8452-9a55e9c82b73","execution_status":"success"},{"action_id":"5f5d8617-4da8-4830-a1dc-6b4e98f6b0b0","execution_status":"success"},{"action_id":"01557e04-8980-4554-8c32-5a7e78d3cbf3","execution_status":"success"},{"action_id":"0b75c532-0a94-407b-8174-0ae8c85f23f5","execution_status":"success"},{"action_id":"1dc612d8-1930-4920-bb11-6ad8ba4fe26b","execution_status":"success"},{"action_id":"4d6a1520-3ed5-4f47-857e-e6bb8ce61606","execution_status":"success"},{"action_id":"4d81e63b-04e6-4909-978a-e779d63ae721","execution_status":"success"},{"action_id":"501021f0-ee39-4692-95c1-1d7c07134c71","execution_status":"success"},{"action_id":"dcd9aac0-3205-4c1f-a360-8be492ac384f","execution_status":"success"},{"action_id":"e03f9f63-e895-46a3-93b3-76c16a0a6ee5","execution_status":"success"},{"action_id":"e7eb463d-7108-4dff-ba5a-7ba8f2266142","execution_status":"success"},{"action_id":"e8ae2a41-9a3f-43c0-8d89-e574311bf148","execution_status":"success"},{"action_id":"e9ca4a12-90e8-4312-82ec-fadfea82a7ce","execution_status":"success"},{"action_id":"3dd66962-2bef-4caa-9627-2f056ebabbd7","execution_status":"success"},{"action_id":"6069ec49-a8b1-47df-ace8-153c110cd984","execution_status":"success"}],"non_executable_results":[{"action_id":"0c490240-f3b5-42b2-94ce-010ae67bd79f","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_create_destination_bucket","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372-r222018'"'"' could not be verified from this account context (403)."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"9482c713-7184-4e01-8452-9a55e9c82b73","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"5f5d8617-4da8-4830-a1dc-6b4e98f6b0b0","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"01557e04-8980-4554-8c32-5a7e78d3cbf3","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"0b75c532-0a94-407b-8174-0ae8c85f23f5","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"1dc612d8-1930-4920-bb11-6ad8ba4fe26b","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4d6a1520-3ed5-4f47-857e-e6bb8ce61606","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4d81e63b-04e6-4909-978a-e779d63ae721","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"501021f0-ee39-4692-95c1-1d7c07134c71","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"dcd9aac0-3205-4c1f-a360-8be492ac384f","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e03f9f63-e895-46a3-93b3-76c16a0a6ee5","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e7eb463d-7108-4dff-ba5a-7ba8f2266142","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e8ae2a41-9a3f-43c0-8d89-e574311bf148","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e9ca4a12-90e8-4312-82ec-fadfea82a7ce","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"3dd66962-2bef-4caa-9627-2f056ebabbd7","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"6069ec49-a8b1-47df-ace8-153c110cd984","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"0c490240-f3b5-42b2-94ce-010ae67bd79f","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_create_destination_bucket","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372-r222018'"'"' could not be verified from this account context (403)."]}]}'
SUMMARY_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[],"shared_execution_results":[],"non_executable_results":[{"action_id":"0c490240-f3b5-42b2-94ce-010ae67bd79f","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_create_destination_bucket","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372-r222018'"'"' could not be verified from this account context (403)."]}]}'
REPLAY_DIR="./.bundle-callback-replay"
RUNNER="./run_actions.sh"
SUMMARY_FILE="./.bundle-execution-summary.json"
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

build_finished_payload() {
  local exit_code="$1"
  local finished_at="$2"
  python3 - "$SUMMARY_TEMPLATE" "$SUMMARY_FILE" "$finished_at" "$FINISHED_SUCCESS_TEMPLATE" "$FINISHED_FAILED_TEMPLATE" "$exit_code" <<'PY'
import json
import sys
from pathlib import Path

summary_template = json.loads(sys.argv[1])
summary_path = Path(sys.argv[2])
finished_at = sys.argv[3]
success_fallback = json.loads(sys.argv[4])
failed_fallback = json.loads(sys.argv[5])
exit_code = int(sys.argv[6])

payload = dict(summary_template)
payload["finished_at"] = finished_at
if summary_path.is_file():
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        summary = None
    if isinstance(summary, dict):
        action_results = summary.get("action_results")
        shared_execution_results = summary.get("shared_execution_results")
        if isinstance(action_results, list):
            payload["action_results"] = action_results
        if isinstance(shared_execution_results, list) and shared_execution_results:
            payload["shared_execution_results"] = shared_execution_results
        print(json.dumps(payload, separators=(",", ":")))
        sys.exit(0)

fallback = success_fallback if exit_code == 0 else failed_fallback
fallback["finished_at"] = finished_at
print(json.dumps(fallback, separators=(",", ":")))
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
  payload="$(build_finished_payload "$exit_code" "$finished_at")"
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
