#!/usr/bin/env bash
set +e

REPORT_URL=http://127.0.0.1:18022/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiIxODAyNzNmNy1mYTIwLTRmMGYtYjM5YS02YmEzZDE2MGMzZTciLCJncm91cF9pZCI6ImZjMWJmNjlkLTIyMjEtNGVlYi04ODQyLTAzOWVkZjgyMjNjYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJhNWJiYmE1MS1iNWE4LTQxNzYtOGY5My1lOWQwYzM3NmFkZTUiLCJiMzJiNGExOC00ZGEyLTRmOTQtYWNmMy0wZWM0ZjJlNTU1ZGIiLCIwZDIwNmU1Ny0yYTlhLTRkN2UtYWJkYS1kYTczYTVlOTM2OTUiXSwianRpIjoiZGE2Mjg2OGUtNGYzOS00NWRiLWI1ODMtM2QyNWZmMWE5MWIzIiwiaWF0IjoxNzczODY5NzA4LCJleHAiOjE3NzM5NTYxMDh9.Vu-lq6vG9Fek-dwRWaSSQ7dA8UsuZZ3-u134g5ou0AI
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiIxODAyNzNmNy1mYTIwLTRmMGYtYjM5YS02YmEzZDE2MGMzZTciLCJncm91cF9pZCI6ImZjMWJmNjlkLTIyMjEtNGVlYi04ODQyLTAzOWVkZjgyMjNjYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJhNWJiYmE1MS1iNWE4LTQxNzYtOGY5My1lOWQwYzM3NmFkZTUiLCJiMzJiNGExOC00ZGEyLTRmOTQtYWNmMy0wZWM0ZjJlNTU1ZGIiLCIwZDIwNmU1Ny0yYTlhLTRkN2UtYWJkYS1kYTczYTVlOTM2OTUiXSwianRpIjoiZGE2Mjg2OGUtNGYzOS00NWRiLWI1ODMtM2QyNWZmMWE5MWIzIiwiaWF0IjoxNzczODY5NzA4LCJleHAiOjE3NzM5NTYxMDh9.Vu-lq6vG9Fek-dwRWaSSQ7dA8UsuZZ3-u134g5ou0AI","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiIxODAyNzNmNy1mYTIwLTRmMGYtYjM5YS02YmEzZDE2MGMzZTciLCJncm91cF9pZCI6ImZjMWJmNjlkLTIyMjEtNGVlYi04ODQyLTAzOWVkZjgyMjNjYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJhNWJiYmE1MS1iNWE4LTQxNzYtOGY5My1lOWQwYzM3NmFkZTUiLCJiMzJiNGExOC00ZGEyLTRmOTQtYWNmMy0wZWM0ZjJlNTU1ZGIiLCIwZDIwNmU1Ny0yYTlhLTRkN2UtYWJkYS1kYTczYTVlOTM2OTUiXSwianRpIjoiZGE2Mjg2OGUtNGYzOS00NWRiLWI1ODMtM2QyNWZmMWE5MWIzIiwiaWF0IjoxNzczODY5NzA4LCJleHAiOjE3NzM5NTYxMDh9.Vu-lq6vG9Fek-dwRWaSSQ7dA8UsuZZ3-u134g5ou0AI","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"b32b4a18-4da2-4f94-acf3-0ec4f2e555db","execution_status":"success"}],"non_executable_results":[{"action_id":"a5bbba51-b5a8-4176-8f93-e9d0c376ade5","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access."]},{"action_id":"0d206e57-2a9a-4d7e-abda-da73a5e93695","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled.","Missing bucket identifier for access-path validation."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiIxODAyNzNmNy1mYTIwLTRmMGYtYjM5YS02YmEzZDE2MGMzZTciLCJncm91cF9pZCI6ImZjMWJmNjlkLTIyMjEtNGVlYi04ODQyLTAzOWVkZjgyMjNjYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJhNWJiYmE1MS1iNWE4LTQxNzYtOGY5My1lOWQwYzM3NmFkZTUiLCJiMzJiNGExOC00ZGEyLTRmOTQtYWNmMy0wZWM0ZjJlNTU1ZGIiLCIwZDIwNmU1Ny0yYTlhLTRkN2UtYWJkYS1kYTczYTVlOTM2OTUiXSwianRpIjoiZGE2Mjg2OGUtNGYzOS00NWRiLWI1ODMtM2QyNWZmMWE5MWIzIiwiaWF0IjoxNzczODY5NzA4LCJleHAiOjE3NzM5NTYxMDh9.Vu-lq6vG9Fek-dwRWaSSQ7dA8UsuZZ3-u134g5ou0AI","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"b32b4a18-4da2-4f94-acf3-0ec4f2e555db","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"a5bbba51-b5a8-4176-8f93-e9d0c376ade5","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access."]},{"action_id":"0d206e57-2a9a-4d7e-abda-da73a5e93695","support_tier":"manual_guidance_only","profile_id":"s3_bucket_block_public_access_manual_preservation","strategy_id":"s3_bucket_block_public_access_standard","reason":"manual_guidance_metadata_only","blocked_reasons":["Runtime evidence could not prove the bucket is private and website hosting is disabled.","Missing bucket identifier for access-path validation."]}]}'
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
