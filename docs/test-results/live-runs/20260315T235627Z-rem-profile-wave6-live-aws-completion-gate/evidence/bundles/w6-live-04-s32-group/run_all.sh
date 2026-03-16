#!/usr/bin/env bash
set +e

REPORT_URL="http://127.0.0.1:18020/api/internal/group-runs/report"
REPORT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJmYTAzY2NkZi0xZDc4LTQzOGItYjEwYS0wOGE1ODY3YzRiNDMiLCJncm91cF9ydW5faWQiOiJlMGRhNTNjZC05MmQ1LTRmMzUtOTQzNi0yN2YwYjM3YjQzOGMiLCJncm91cF9pZCI6IjQzZDhiN2U1LTZjZDUtNGQzMS05MTVlLWYyMmZjNDllYmQwOCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI0Yjk0NjJlNS0yMzkxLTRkMWQtOWQ4Zi00MjVlMTI0YWM5Y2YiLCI2MzhjNmI0My0zMmFiLTQxMDQtYTFkYS0yOWJlNWNkOWEzNWEiLCIwMmExZjRhOS0yYWU2LTRlNDItYmQwZS03YWM2NTliM2MwZTUiXSwianRpIjoiMDVjZTEwNTgtOWY4ZS00ZWE0LTgwZTMtZjA5NjE3ZGRmZGI1IiwiaWF0IjoxNzczNjIwMDI1LCJleHAiOjE3NzM3MDY0MjV9.Zn94GTjih_UYbzlB7IEVp3-VxsAXSn3LqR0kdv6qli4"
STARTED_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJmYTAzY2NkZi0xZDc4LTQzOGItYjEwYS0wOGE1ODY3YzRiNDMiLCJncm91cF9ydW5faWQiOiJlMGRhNTNjZC05MmQ1LTRmMzUtOTQzNi0yN2YwYjM3YjQzOGMiLCJncm91cF9pZCI6IjQzZDhiN2U1LTZjZDUtNGQzMS05MTVlLWYyMmZjNDllYmQwOCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI0Yjk0NjJlNS0yMzkxLTRkMWQtOWQ4Zi00MjVlMTI0YWM5Y2YiLCI2MzhjNmI0My0zMmFiLTQxMDQtYTFkYS0yOWJlNWNkOWEzNWEiLCIwMmExZjRhOS0yYWU2LTRlNDItYmQwZS03YWM2NTliM2MwZTUiXSwianRpIjoiMDVjZTEwNTgtOWY4ZS00ZWE0LTgwZTMtZjA5NjE3ZGRmZGI1IiwiaWF0IjoxNzczNjIwMDI1LCJleHAiOjE3NzM3MDY0MjV9.Zn94GTjih_UYbzlB7IEVp3-VxsAXSn3LqR0kdv6qli4", "event": "started", "reporting_source": "bundle_callback"}
FINISHED_SUCCESS_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJmYTAzY2NkZi0xZDc4LTQzOGItYjEwYS0wOGE1ODY3YzRiNDMiLCJncm91cF9ydW5faWQiOiJlMGRhNTNjZC05MmQ1LTRmMzUtOTQzNi0yN2YwYjM3YjQzOGMiLCJncm91cF9pZCI6IjQzZDhiN2U1LTZjZDUtNGQzMS05MTVlLWYyMmZjNDllYmQwOCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI0Yjk0NjJlNS0yMzkxLTRkMWQtOWQ4Zi00MjVlMTI0YWM5Y2YiLCI2MzhjNmI0My0zMmFiLTQxMDQtYTFkYS0yOWJlNWNkOWEzNWEiLCIwMmExZjRhOS0yYWU2LTRlNDItYmQwZS03YWM2NTliM2MwZTUiXSwianRpIjoiMDVjZTEwNTgtOWY4ZS00ZWE0LTgwZTMtZjA5NjE3ZGRmZGI1IiwiaWF0IjoxNzczNjIwMDI1LCJleHAiOjE3NzM3MDY0MjV9.Zn94GTjih_UYbzlB7IEVp3-VxsAXSn3LqR0kdv6qli4", "event": "finished", "reporting_source": "bundle_callback", "action_results": [{"action_id": "638c6b43-32ab-4104-a1da-29be5cd9a35a", "execution_status": "success"}], "non_executable_results": [{"action_id": "4b9462e5-2391-4d1d-9d8f-425e124ac9cf", "support_tier": "manual_guidance_only", "profile_id": "s3_bucket_block_public_access_manual_preservation", "strategy_id": "s3_bucket_block_public_access_standard", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access."]}, {"action_id": "02a1f4a9-2ae6-4e42-bd0e-7ac659b3c0e5", "support_tier": "manual_guidance_only", "profile_id": "s3_bucket_block_public_access_manual_preservation", "strategy_id": "s3_bucket_block_public_access_standard", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["Runtime evidence could not prove the bucket is private and website hosting is disabled.", "Missing bucket identifier for access-path validation."]}]}
FINISHED_FAILED_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJmYTAzY2NkZi0xZDc4LTQzOGItYjEwYS0wOGE1ODY3YzRiNDMiLCJncm91cF9ydW5faWQiOiJlMGRhNTNjZC05MmQ1LTRmMzUtOTQzNi0yN2YwYjM3YjQzOGMiLCJncm91cF9pZCI6IjQzZDhiN2U1LTZjZDUtNGQzMS05MTVlLWYyMmZjNDllYmQwOCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI0Yjk0NjJlNS0yMzkxLTRkMWQtOWQ4Zi00MjVlMTI0YWM5Y2YiLCI2MzhjNmI0My0zMmFiLTQxMDQtYTFkYS0yOWJlNWNkOWEzNWEiLCIwMmExZjRhOS0yYWU2LTRlNDItYmQwZS03YWM2NTliM2MwZTUiXSwianRpIjoiMDVjZTEwNTgtOWY4ZS00ZWE0LTgwZTMtZjA5NjE3ZGRmZGI1IiwiaWF0IjoxNzczNjIwMDI1LCJleHAiOjE3NzM3MDY0MjV9.Zn94GTjih_UYbzlB7IEVp3-VxsAXSn3LqR0kdv6qli4", "event": "finished", "reporting_source": "bundle_callback", "action_results": [{"action_id": "638c6b43-32ab-4104-a1da-29be5cd9a35a", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}], "non_executable_results": [{"action_id": "4b9462e5-2391-4d1d-9d8f-425e124ac9cf", "support_tier": "manual_guidance_only", "profile_id": "s3_bucket_block_public_access_manual_preservation", "strategy_id": "s3_bucket_block_public_access_standard", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access."]}, {"action_id": "02a1f4a9-2ae6-4e42-bd0e-7ac659b3c0e5", "support_tier": "manual_guidance_only", "profile_id": "s3_bucket_block_public_access_manual_preservation", "strategy_id": "s3_bucket_block_public_access_standard", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["Runtime evidence could not prove the bucket is private and website hosting is disabled.", "Missing bucket identifier for access-path validation."]}]}
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
