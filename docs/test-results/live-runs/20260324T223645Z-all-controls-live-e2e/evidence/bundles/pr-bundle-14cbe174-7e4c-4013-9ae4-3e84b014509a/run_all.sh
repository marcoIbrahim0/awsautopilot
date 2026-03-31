#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=<REDACTED_TOKEN>
STARTED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"53cda243-1815-4864-8cc3-f3e1535a4ff1","execution_status":"success"},{"action_id":"a57bd4fc-c54f-4965-baa9-a675d386a043","execution_status":"success"},{"action_id":"0361bcde-869c-4b55-913d-ed8bea424a7e","execution_status":"success"},{"action_id":"42eef23b-f9ba-4381-b8af-028529231a84","execution_status":"success"},{"action_id":"4e5dc9e9-0763-45f4-a601-1bfd54c83038","execution_status":"success"},{"action_id":"50b7681f-6f96-45f7-bb75-06cb8bb9074d","execution_status":"success"},{"action_id":"6a75c127-7fcb-4320-b54b-dbe856f727c6","execution_status":"success"},{"action_id":"88c01f62-9a6b-4bd6-9e1f-eb7592845ce2","execution_status":"success"},{"action_id":"c81bf06a-bf7a-42d6-b154-8c1a97739781","execution_status":"success"},{"action_id":"cbb438f0-4e9a-489e-b7cf-2ef5dd95edf3","execution_status":"success"},{"action_id":"d42826b3-0611-4b29-a27a-726c53c00a50","execution_status":"success"},{"action_id":"d5f1fd68-4ae6-46b1-8ddf-33f168eeed8c","execution_status":"success"}],"non_executable_results":[{"action_id":"7be937c3-8b96-413e-881b-94118a699913","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["Lifecycle preservation evidence is missing for additive merge review."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"53cda243-1815-4864-8cc3-f3e1535a4ff1","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"a57bd4fc-c54f-4965-baa9-a675d386a043","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"0361bcde-869c-4b55-913d-ed8bea424a7e","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"42eef23b-f9ba-4381-b8af-028529231a84","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4e5dc9e9-0763-45f4-a601-1bfd54c83038","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"50b7681f-6f96-45f7-bb75-06cb8bb9074d","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"6a75c127-7fcb-4320-b54b-dbe856f727c6","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"88c01f62-9a6b-4bd6-9e1f-eb7592845ce2","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"c81bf06a-bf7a-42d6-b154-8c1a97739781","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"cbb438f0-4e9a-489e-b7cf-2ef5dd95edf3","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"d42826b3-0611-4b29-a27a-726c53c00a50","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"d5f1fd68-4ae6-46b1-8ddf-33f168eeed8c","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"7be937c3-8b96-413e-881b-94118a699913","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["Lifecycle preservation evidence is missing for additive merge review."]}]}'
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
