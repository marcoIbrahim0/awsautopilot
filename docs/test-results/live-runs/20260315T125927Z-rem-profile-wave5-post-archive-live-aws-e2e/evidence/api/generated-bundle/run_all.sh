#!/usr/bin/env bash
set +e

REPORT_URL="http://127.0.0.1:18008/api/internal/group-runs/report"
REPORT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiIzZjM5MmU5Mi0wNjlhLTQ3ZjctODg0ZS05ODVkNWU1ZWQwMzUiLCJncm91cF9ydW5faWQiOiI2ZGUwZjAzYy01OGMyLTRjNWYtODczOS1kZmRkOWVlNTFlZmYiLCJncm91cF9pZCI6Ijc1Y2Q0ZjUwLTk3YzktNGFhMC05MTFiLWViM2IxN2ZmZDgwNCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJiYjQ4N2NmZC0yZDI4LTQxYTYtOGVjMy01ZjY4NWU0ZWFhMjYiLCI0N2MwMjNhZS05NDVjLTQyYmYtOWI0NC0wMThkMjc2MDQ2ZmEiXSwianRpIjoiZTAxYWVhY2EtNWVjYS00NjAxLTgyNDMtYmE0M2I3Mzg0YjlmIiwiaWF0IjoxNzczNTc5ODY1LCJleHAiOjE3NzM2NjYyNjV9.u43iXzmDcCCosp5vnif8OAj3ErEvvjGpWf6no5teR7M"
STARTED_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiIzZjM5MmU5Mi0wNjlhLTQ3ZjctODg0ZS05ODVkNWU1ZWQwMzUiLCJncm91cF9ydW5faWQiOiI2ZGUwZjAzYy01OGMyLTRjNWYtODczOS1kZmRkOWVlNTFlZmYiLCJncm91cF9pZCI6Ijc1Y2Q0ZjUwLTk3YzktNGFhMC05MTFiLWViM2IxN2ZmZDgwNCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJiYjQ4N2NmZC0yZDI4LTQxYTYtOGVjMy01ZjY4NWU0ZWFhMjYiLCI0N2MwMjNhZS05NDVjLTQyYmYtOWI0NC0wMThkMjc2MDQ2ZmEiXSwianRpIjoiZTAxYWVhY2EtNWVjYS00NjAxLTgyNDMtYmE0M2I3Mzg0YjlmIiwiaWF0IjoxNzczNTc5ODY1LCJleHAiOjE3NzM2NjYyNjV9.u43iXzmDcCCosp5vnif8OAj3ErEvvjGpWf6no5teR7M", "event": "started", "reporting_source": "bundle_callback"}
FINISHED_SUCCESS_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiIzZjM5MmU5Mi0wNjlhLTQ3ZjctODg0ZS05ODVkNWU1ZWQwMzUiLCJncm91cF9ydW5faWQiOiI2ZGUwZjAzYy01OGMyLTRjNWYtODczOS1kZmRkOWVlNTFlZmYiLCJncm91cF9pZCI6Ijc1Y2Q0ZjUwLTk3YzktNGFhMC05MTFiLWViM2IxN2ZmZDgwNCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJiYjQ4N2NmZC0yZDI4LTQxYTYtOGVjMy01ZjY4NWU0ZWFhMjYiLCI0N2MwMjNhZS05NDVjLTQyYmYtOWI0NC0wMThkMjc2MDQ2ZmEiXSwianRpIjoiZTAxYWVhY2EtNWVjYS00NjAxLTgyNDMtYmE0M2I3Mzg0YjlmIiwiaWF0IjoxNzczNTc5ODY1LCJleHAiOjE3NzM2NjYyNjV9.u43iXzmDcCCosp5vnif8OAj3ErEvvjGpWf6no5teR7M", "event": "finished", "reporting_source": "bundle_callback", "action_results": [{"action_id": "bb487cfd-2d28-41a6-8ec3-5f685e4eaa26", "execution_status": "success"}], "non_executable_results": [{"action_id": "47c023ae-945c-42bf-9b44-018d276046fa", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_guided", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}]}
FINISHED_FAILED_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiIzZjM5MmU5Mi0wNjlhLTQ3ZjctODg0ZS05ODVkNWU1ZWQwMzUiLCJncm91cF9ydW5faWQiOiI2ZGUwZjAzYy01OGMyLTRjNWYtODczOS1kZmRkOWVlNTFlZmYiLCJncm91cF9pZCI6Ijc1Y2Q0ZjUwLTk3YzktNGFhMC05MTFiLWViM2IxN2ZmZDgwNCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJiYjQ4N2NmZC0yZDI4LTQxYTYtOGVjMy01ZjY4NWU0ZWFhMjYiLCI0N2MwMjNhZS05NDVjLTQyYmYtOWI0NC0wMThkMjc2MDQ2ZmEiXSwianRpIjoiZTAxYWVhY2EtNWVjYS00NjAxLTgyNDMtYmE0M2I3Mzg0YjlmIiwiaWF0IjoxNzczNTc5ODY1LCJleHAiOjE3NzM2NjYyNjV9.u43iXzmDcCCosp5vnif8OAj3ErEvvjGpWf6no5teR7M", "event": "finished", "reporting_source": "bundle_callback", "action_results": [{"action_id": "bb487cfd-2d28-41a6-8ec3-5f685e4eaa26", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}], "non_executable_results": [{"action_id": "47c023ae-945c-42bf-9b44-018d276046fa", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_guided", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}]}
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
