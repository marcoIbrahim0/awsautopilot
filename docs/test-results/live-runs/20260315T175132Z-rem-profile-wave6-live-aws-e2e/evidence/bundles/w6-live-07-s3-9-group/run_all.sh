#!/usr/bin/env bash
set +e

REPORT_URL="http://127.0.0.1:18012/api/internal/group-runs/report"
REPORT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJhMjgwNWM2Ni0zMTE3LTQzMGQtOWFiNS02OTk4MzU0NDFkZGEiLCJncm91cF9ydW5faWQiOiIxOWM1MjJjMC05MjU2LTQxMjQtOGIzOS00MmI3MDdiZGQ4MTIiLCJncm91cF9pZCI6ImEwMmY1ZmE4LTRiMjctNGUyZC04YzRiLTcwNjIxZWE1NTdhMyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJiZWU1ODg4ZS04YzE0LTQzZjItODdmNi03N2I5ZmNkOGM0YWEiLCJkN2Y4NjhjNS05YTY0LTRhY2EtYmZmMC1hYWJiMDZiM2MxMDQiXSwianRpIjoiODBkOGZmMjUtM2IyNi00ODA0LTg1NDUtMjkzMjIyZGM4MmE3IiwiaWF0IjoxNzczNTk4MDc2LCJleHAiOjE3NzM2ODQ0NzZ9.JFsKn9DP0h_blndQuyvCF6LozD86mPH729hgHCZ6m5c"
STARTED_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJhMjgwNWM2Ni0zMTE3LTQzMGQtOWFiNS02OTk4MzU0NDFkZGEiLCJncm91cF9ydW5faWQiOiIxOWM1MjJjMC05MjU2LTQxMjQtOGIzOS00MmI3MDdiZGQ4MTIiLCJncm91cF9pZCI6ImEwMmY1ZmE4LTRiMjctNGUyZC04YzRiLTcwNjIxZWE1NTdhMyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJiZWU1ODg4ZS04YzE0LTQzZjItODdmNi03N2I5ZmNkOGM0YWEiLCJkN2Y4NjhjNS05YTY0LTRhY2EtYmZmMC1hYWJiMDZiM2MxMDQiXSwianRpIjoiODBkOGZmMjUtM2IyNi00ODA0LTg1NDUtMjkzMjIyZGM4MmE3IiwiaWF0IjoxNzczNTk4MDc2LCJleHAiOjE3NzM2ODQ0NzZ9.JFsKn9DP0h_blndQuyvCF6LozD86mPH729hgHCZ6m5c", "event": "started", "reporting_source": "bundle_callback"}
FINISHED_SUCCESS_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJhMjgwNWM2Ni0zMTE3LTQzMGQtOWFiNS02OTk4MzU0NDFkZGEiLCJncm91cF9ydW5faWQiOiIxOWM1MjJjMC05MjU2LTQxMjQtOGIzOS00MmI3MDdiZGQ4MTIiLCJncm91cF9pZCI6ImEwMmY1ZmE4LTRiMjctNGUyZC04YzRiLTcwNjIxZWE1NTdhMyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJiZWU1ODg4ZS04YzE0LTQzZjItODdmNi03N2I5ZmNkOGM0YWEiLCJkN2Y4NjhjNS05YTY0LTRhY2EtYmZmMC1hYWJiMDZiM2MxMDQiXSwianRpIjoiODBkOGZmMjUtM2IyNi00ODA0LTg1NDUtMjkzMjIyZGM4MmE3IiwiaWF0IjoxNzczNTk4MDc2LCJleHAiOjE3NzM2ODQ0NzZ9.JFsKn9DP0h_blndQuyvCF6LozD86mPH729hgHCZ6m5c", "event": "finished", "reporting_source": "bundle_callback", "action_results": [], "non_executable_results": [{"action_id": "bee5888e-8c14-43f2-87f6-77b9fcd8c4aa", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": ["Log destination must be a dedicated bucket and cannot match the source bucket."]}, {"action_id": "d7f868c5-9a64-4aca-bff0-aabb06b3c104", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": ["Destination log bucket 'config-bucket-696505809372' could not be verified from this account context (403)."]}]}
FINISHED_FAILED_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJhMjgwNWM2Ni0zMTE3LTQzMGQtOWFiNS02OTk4MzU0NDFkZGEiLCJncm91cF9ydW5faWQiOiIxOWM1MjJjMC05MjU2LTQxMjQtOGIzOS00MmI3MDdiZGQ4MTIiLCJncm91cF9pZCI6ImEwMmY1ZmE4LTRiMjctNGUyZC04YzRiLTcwNjIxZWE1NTdhMyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJiZWU1ODg4ZS04YzE0LTQzZjItODdmNi03N2I5ZmNkOGM0YWEiLCJkN2Y4NjhjNS05YTY0LTRhY2EtYmZmMC1hYWJiMDZiM2MxMDQiXSwianRpIjoiODBkOGZmMjUtM2IyNi00ODA0LTg1NDUtMjkzMjIyZGM4MmE3IiwiaWF0IjoxNzczNTk4MDc2LCJleHAiOjE3NzM2ODQ0NzZ9.JFsKn9DP0h_blndQuyvCF6LozD86mPH729hgHCZ6m5c", "event": "finished", "reporting_source": "bundle_callback", "action_results": [], "non_executable_results": [{"action_id": "bee5888e-8c14-43f2-87f6-77b9fcd8c4aa", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": ["Log destination must be a dedicated bucket and cannot match the source bucket."]}, {"action_id": "d7f868c5-9a64-4aca-bff0-aabb06b3c104", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": ["Destination log bucket 'config-bucket-696505809372' could not be verified from this account context (403)."]}]}
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
