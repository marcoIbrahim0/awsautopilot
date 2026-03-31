#!/usr/bin/env bash
set +e

REPORT_URL=http://127.0.0.1:18031/api/internal/group-runs/report
REPORT_TOKEN=<REDACTED_TOKEN>
STARTED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"29f0d788-90f3-48e4-96d7-8ed0657924a6","execution_status":"success"},{"action_id":"424d65bb-5bd8-4ba3-a5ca-9785fbb41bb9","execution_status":"success"},{"action_id":"7a438b0e-37e8-444e-a211-04a906891a69","execution_status":"success"}],"non_executable_results":[{"action_id":"251b980d-17a9-4fae-8e5f-e2ca38d389ed","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["Bucket policy preservation evidence is missing for merge-safe SSL enforcement."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"29f0d788-90f3-48e4-96d7-8ed0657924a6","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"424d65bb-5bd8-4ba3-a5ca-9785fbb41bb9","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"7a438b0e-37e8-444e-a211-04a906891a69","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"251b980d-17a9-4fae-8e5f-e2ca38d389ed","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["Bucket policy preservation evidence is missing for merge-safe SSL enforcement."]}]}'
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
