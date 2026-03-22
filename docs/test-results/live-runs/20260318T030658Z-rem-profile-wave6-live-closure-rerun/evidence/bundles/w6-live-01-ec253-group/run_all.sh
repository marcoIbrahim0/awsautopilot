#!/usr/bin/env bash
set +e

REPORT_URL=http://127.0.0.1:18022/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiI2OGQ0ZjRmNC1jNjUwLTQ1ZWUtOTFkZC1mZjllNzc1MjE0ZmYiLCJncm91cF9pZCI6Ijg0ODY2OGYyLTVmMjQtNDYzNy1hZWFhLTZiN2U1ZjlhMDI3MSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIyYTFjOWQyZi1iMDVkLTQ4YjMtYmNlYy1kNzY0NWM1ZmQwMTciLCJhZDkzMjhlMS1mYWYyLTRmZDQtOTg4NS1jN2Y4YzUwYzdkMTQiXSwianRpIjoiNzU5MTRhZTgtNWMxOS00NjdiLTkwYTUtYjQyZDk4NDM2OGJiIiwiaWF0IjoxNzczODAzNTA4LCJleHAiOjE3NzM4ODk5MDh9.4U3sgDmg-UW-PoCJ-F3hGUST-QaJJpODL0zxqQNk1yc
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiI2OGQ0ZjRmNC1jNjUwLTQ1ZWUtOTFkZC1mZjllNzc1MjE0ZmYiLCJncm91cF9pZCI6Ijg0ODY2OGYyLTVmMjQtNDYzNy1hZWFhLTZiN2U1ZjlhMDI3MSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIyYTFjOWQyZi1iMDVkLTQ4YjMtYmNlYy1kNzY0NWM1ZmQwMTciLCJhZDkzMjhlMS1mYWYyLTRmZDQtOTg4NS1jN2Y4YzUwYzdkMTQiXSwianRpIjoiNzU5MTRhZTgtNWMxOS00NjdiLTkwYTUtYjQyZDk4NDM2OGJiIiwiaWF0IjoxNzczODAzNTA4LCJleHAiOjE3NzM4ODk5MDh9.4U3sgDmg-UW-PoCJ-F3hGUST-QaJJpODL0zxqQNk1yc","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiI2OGQ0ZjRmNC1jNjUwLTQ1ZWUtOTFkZC1mZjllNzc1MjE0ZmYiLCJncm91cF9pZCI6Ijg0ODY2OGYyLTVmMjQtNDYzNy1hZWFhLTZiN2U1ZjlhMDI3MSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIyYTFjOWQyZi1iMDVkLTQ4YjMtYmNlYy1kNzY0NWM1ZmQwMTciLCJhZDkzMjhlMS1mYWYyLTRmZDQtOTg4NS1jN2Y4YzUwYzdkMTQiXSwianRpIjoiNzU5MTRhZTgtNWMxOS00NjdiLTkwYTUtYjQyZDk4NDM2OGJiIiwiaWF0IjoxNzczODAzNTA4LCJleHAiOjE3NzM4ODk5MDh9.4U3sgDmg-UW-PoCJ-F3hGUST-QaJJpODL0zxqQNk1yc","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"ad9328e1-faf2-4fd4-9885-c7f8c50c7d14","execution_status":"success"}],"non_executable_results":[{"action_id":"2a1c9d2f-b05d-48b3-bcec-d7645c5fd017","support_tier":"manual_guidance_only","profile_id":"ssm_only","strategy_id":"sg_restrict_public_ports_guided","reason":"manual_guidance_metadata_only","blocked_reasons":["Wave 6 downgrades '"'"'ssm_only'"'"' because SSM-only execution is not implemented."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiI2OGQ0ZjRmNC1jNjUwLTQ1ZWUtOTFkZC1mZjllNzc1MjE0ZmYiLCJncm91cF9pZCI6Ijg0ODY2OGYyLTVmMjQtNDYzNy1hZWFhLTZiN2U1ZjlhMDI3MSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIyYTFjOWQyZi1iMDVkLTQ4YjMtYmNlYy1kNzY0NWM1ZmQwMTciLCJhZDkzMjhlMS1mYWYyLTRmZDQtOTg4NS1jN2Y4YzUwYzdkMTQiXSwianRpIjoiNzU5MTRhZTgtNWMxOS00NjdiLTkwYTUtYjQyZDk4NDM2OGJiIiwiaWF0IjoxNzczODAzNTA4LCJleHAiOjE3NzM4ODk5MDh9.4U3sgDmg-UW-PoCJ-F3hGUST-QaJJpODL0zxqQNk1yc","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"ad9328e1-faf2-4fd4-9885-c7f8c50c7d14","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"2a1c9d2f-b05d-48b3-bcec-d7645c5fd017","support_tier":"manual_guidance_only","profile_id":"ssm_only","strategy_id":"sg_restrict_public_ports_guided","reason":"manual_guidance_metadata_only","blocked_reasons":["Wave 6 downgrades '"'"'ssm_only'"'"' because SSM-only execution is not implemented."]}]}'
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
