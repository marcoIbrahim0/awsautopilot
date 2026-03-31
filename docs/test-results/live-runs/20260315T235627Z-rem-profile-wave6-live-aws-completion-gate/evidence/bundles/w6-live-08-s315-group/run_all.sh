#!/usr/bin/env bash
set +e

REPORT_URL="http://127.0.0.1:18020/api/internal/group-runs/report"
REPORT_TOKEN="<REDACTED_TOKEN>"
STARTED_TEMPLATE={"token": "<REDACTED_TOKEN>", "event": "started", "reporting_source": "bundle_callback"}
FINISHED_SUCCESS_TEMPLATE={"token": "<REDACTED_TOKEN>", "event": "finished", "reporting_source": "bundle_callback", "action_results": [{"action_id": "023e8b64-4ff6-4f0a-a074-d8ed4e6a31ff", "execution_status": "success"}, {"action_id": "080ad0ec-b379-4cb5-9f7a-aecdd997ab11", "execution_status": "success"}, {"action_id": "216bc880-fda0-40ec-bf75-caf45d820645", "execution_status": "success"}, {"action_id": "2e5d6e74-73e1-47e6-9c00-32c290f1d198", "execution_status": "success"}, {"action_id": "31381d3c-04f9-4613-a897-ba95ddbdc0bd", "execution_status": "success"}, {"action_id": "3cea24eb-54ca-412e-aa04-f0d0da1d9d9b", "execution_status": "success"}, {"action_id": "44196b82-644c-4451-8539-519a81796192", "execution_status": "success"}, {"action_id": "6ed02911-7dfc-46f8-96dc-320c25f5793a", "execution_status": "success"}, {"action_id": "777749c0-1137-475b-a102-b128b791beaa", "execution_status": "success"}, {"action_id": "94253f6e-4bd3-40f5-97e3-7bdc9530fbbf", "execution_status": "success"}, {"action_id": "be206765-a453-475d-a722-95adea63dd53", "execution_status": "success"}]}
FINISHED_FAILED_TEMPLATE={"token": "<REDACTED_TOKEN>", "event": "finished", "reporting_source": "bundle_callback", "action_results": [{"action_id": "023e8b64-4ff6-4f0a-a074-d8ed4e6a31ff", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "080ad0ec-b379-4cb5-9f7a-aecdd997ab11", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "216bc880-fda0-40ec-bf75-caf45d820645", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "2e5d6e74-73e1-47e6-9c00-32c290f1d198", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "31381d3c-04f9-4613-a897-ba95ddbdc0bd", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "3cea24eb-54ca-412e-aa04-f0d0da1d9d9b", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "44196b82-644c-4451-8539-519a81796192", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "6ed02911-7dfc-46f8-96dc-320c25f5793a", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "777749c0-1137-475b-a102-b128b791beaa", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "94253f6e-4bd3-40f5-97e3-7bdc9530fbbf", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "be206765-a453-475d-a722-95adea63dd53", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}]}
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
    curl -sS -X POST "$REPORT_URL" -H "Content-Type: application/json" -d "$payload" >/dev/null 2>&1
    return $?
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
