#!/usr/bin/env bash
set +e

REPORT_URL=http://127.0.0.1:18022/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiIyOWQwZWFhMS02YzczLTQyZmEtODg1OC02NzNkNmMwMTQ0YTAiLCJncm91cF9pZCI6IjVjZWUzOWUzLTIwODgtNDNiOS1iYmEwLTI3Yzg0OWI0MGVjYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI5MzljY2UyNy0yZWQwLTQzZGQtYmQ1NC0zZmMzY2IyOTkwYjYiXSwianRpIjoiMTI2MzE4MGUtMmI4MC00YTYyLTlkMTgtMzNjMWNhMWVkZWJjIiwiaWF0IjoxNzczODY5Nzc5LCJleHAiOjE3NzM5NTYxNzl9.tVr2m4dmMgX7koRP9CCZlMvET9hvSJYGmswnhYMHqB4
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiIyOWQwZWFhMS02YzczLTQyZmEtODg1OC02NzNkNmMwMTQ0YTAiLCJncm91cF9pZCI6IjVjZWUzOWUzLTIwODgtNDNiOS1iYmEwLTI3Yzg0OWI0MGVjYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI5MzljY2UyNy0yZWQwLTQzZGQtYmQ1NC0zZmMzY2IyOTkwYjYiXSwianRpIjoiMTI2MzE4MGUtMmI4MC00YTYyLTlkMTgtMzNjMWNhMWVkZWJjIiwiaWF0IjoxNzczODY5Nzc5LCJleHAiOjE3NzM5NTYxNzl9.tVr2m4dmMgX7koRP9CCZlMvET9hvSJYGmswnhYMHqB4","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiIyOWQwZWFhMS02YzczLTQyZmEtODg1OC02NzNkNmMwMTQ0YTAiLCJncm91cF9pZCI6IjVjZWUzOWUzLTIwODgtNDNiOS1iYmEwLTI3Yzg0OWI0MGVjYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI5MzljY2UyNy0yZWQwLTQzZGQtYmQ1NC0zZmMzY2IyOTkwYjYiXSwianRpIjoiMTI2MzE4MGUtMmI4MC00YTYyLTlkMTgtMzNjMWNhMWVkZWJjIiwiaWF0IjoxNzczODY5Nzc5LCJleHAiOjE3NzM5NTYxNzl9.tVr2m4dmMgX7koRP9CCZlMvET9hvSJYGmswnhYMHqB4","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"939cce27-2ed0-43dd-bd54-3fc3cb2990b6","execution_status":"success"}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiIyOWQwZWFhMS02YzczLTQyZmEtODg1OC02NzNkNmMwMTQ0YTAiLCJncm91cF9pZCI6IjVjZWUzOWUzLTIwODgtNDNiOS1iYmEwLTI3Yzg0OWI0MGVjYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI5MzljY2UyNy0yZWQwLTQzZGQtYmQ1NC0zZmMzY2IyOTkwYjYiXSwianRpIjoiMTI2MzE4MGUtMmI4MC00YTYyLTlkMTgtMzNjMWNhMWVkZWJjIiwiaWF0IjoxNzczODY5Nzc5LCJleHAiOjE3NzM5NTYxNzl9.tVr2m4dmMgX7koRP9CCZlMvET9hvSJYGmswnhYMHqB4","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"939cce27-2ed0-43dd-bd54-3fc3cb2990b6","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}]}'
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
