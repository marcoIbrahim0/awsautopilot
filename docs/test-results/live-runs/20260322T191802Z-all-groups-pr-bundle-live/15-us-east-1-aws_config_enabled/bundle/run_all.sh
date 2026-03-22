#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI0M2E0NDg0OC04NzBiLTQ0ZTItOWZkOC04NjA1YzJjMDc5NzkiLCJncm91cF9pZCI6IjE4MTc1MDlkLTBmMzMtNDQxNC1iNjA2LTQzOGZmZjhkYTkyNiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIyMDJlMDJjNy1mMmMxLTRjMjQtYjgxYS0xMTE2OGFjYWQwNTQiLCI3MzA5N2MxMS0xNzRjLTQ1OTctODVhMi05YWY3OTM4NDJlOGQiLCI1YWNjN2QwZS1lMzYxLTQ3NGYtOWVmYS1jMjAwYTAzNThmMGQiLCJhM2QxYWQ5Yi04Y2I3LTQ3Y2MtYjI3MS1jYjE1ZjI2ZGZmZDEiLCIxOGRlODAzZC1iN2NkLTRkZjgtYWQzMC0xNjA0ZGNiMDVjZDUiXSwianRpIjoiMmQ2MjUwZTItNzBjZS00MmZkLWIzOGUtZmY5YjYwNGM3NzI2IiwiaWF0IjoxNzc0MjA3OTc0LCJleHAiOjE3NzQyOTQzNzR9.Ij1V33Q6BD7aHcsmJJWhB3dioaC-z75_hIX1VRpxH_c
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI0M2E0NDg0OC04NzBiLTQ0ZTItOWZkOC04NjA1YzJjMDc5NzkiLCJncm91cF9pZCI6IjE4MTc1MDlkLTBmMzMtNDQxNC1iNjA2LTQzOGZmZjhkYTkyNiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIyMDJlMDJjNy1mMmMxLTRjMjQtYjgxYS0xMTE2OGFjYWQwNTQiLCI3MzA5N2MxMS0xNzRjLTQ1OTctODVhMi05YWY3OTM4NDJlOGQiLCI1YWNjN2QwZS1lMzYxLTQ3NGYtOWVmYS1jMjAwYTAzNThmMGQiLCJhM2QxYWQ5Yi04Y2I3LTQ3Y2MtYjI3MS1jYjE1ZjI2ZGZmZDEiLCIxOGRlODAzZC1iN2NkLTRkZjgtYWQzMC0xNjA0ZGNiMDVjZDUiXSwianRpIjoiMmQ2MjUwZTItNzBjZS00MmZkLWIzOGUtZmY5YjYwNGM3NzI2IiwiaWF0IjoxNzc0MjA3OTc0LCJleHAiOjE3NzQyOTQzNzR9.Ij1V33Q6BD7aHcsmJJWhB3dioaC-z75_hIX1VRpxH_c","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI0M2E0NDg0OC04NzBiLTQ0ZTItOWZkOC04NjA1YzJjMDc5NzkiLCJncm91cF9pZCI6IjE4MTc1MDlkLTBmMzMtNDQxNC1iNjA2LTQzOGZmZjhkYTkyNiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIyMDJlMDJjNy1mMmMxLTRjMjQtYjgxYS0xMTE2OGFjYWQwNTQiLCI3MzA5N2MxMS0xNzRjLTQ1OTctODVhMi05YWY3OTM4NDJlOGQiLCI1YWNjN2QwZS1lMzYxLTQ3NGYtOWVmYS1jMjAwYTAzNThmMGQiLCJhM2QxYWQ5Yi04Y2I3LTQ3Y2MtYjI3MS1jYjE1ZjI2ZGZmZDEiLCIxOGRlODAzZC1iN2NkLTRkZjgtYWQzMC0xNjA0ZGNiMDVjZDUiXSwianRpIjoiMmQ2MjUwZTItNzBjZS00MmZkLWIzOGUtZmY5YjYwNGM3NzI2IiwiaWF0IjoxNzc0MjA3OTc0LCJleHAiOjE3NzQyOTQzNzR9.Ij1V33Q6BD7aHcsmJJWhB3dioaC-z75_hIX1VRpxH_c","event":"finished","reporting_source":"bundle_callback","action_results":[],"non_executable_results":[{"action_id":"202e02c7-f2c1-4c24-b81a-11168acad054","support_tier":"review_required_bundle","profile_id":"config_enable_account_local_delivery","strategy_id":"config_enable_account_local_delivery","reason":"review_required_metadata_only","blocked_reasons":["AWS Config delivery bucket reachability has not been proven from this account context.","AWS Config delivery bucket policy compatibility has not been proven from this account context."]},{"action_id":"73097c11-174c-4597-85a2-9af793842e8d","support_tier":"review_required_bundle","profile_id":"config_enable_account_local_delivery","strategy_id":"config_enable_account_local_delivery","reason":"review_required_metadata_only","blocked_reasons":["AWS Config delivery bucket reachability has not been proven from this account context.","AWS Config delivery bucket policy compatibility has not been proven from this account context."]},{"action_id":"5acc7d0e-e361-474f-9efa-c200a0358f0d","support_tier":"review_required_bundle","profile_id":"config_enable_account_local_delivery","strategy_id":"config_enable_account_local_delivery","reason":"review_required_metadata_only","blocked_reasons":["AWS Config delivery bucket reachability has not been proven from this account context.","AWS Config delivery bucket policy compatibility has not been proven from this account context."]},{"action_id":"a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1","support_tier":"review_required_bundle","profile_id":"config_enable_account_local_delivery","strategy_id":"config_enable_account_local_delivery","reason":"review_required_metadata_only","blocked_reasons":["AWS Config delivery bucket reachability has not been proven from this account context.","AWS Config delivery bucket policy compatibility has not been proven from this account context."]},{"action_id":"18de803d-b7cd-4df8-ad30-1604dcb05cd5","support_tier":"review_required_bundle","profile_id":"config_enable_account_local_delivery","strategy_id":"config_enable_account_local_delivery","reason":"review_required_metadata_only","blocked_reasons":["AWS Config delivery bucket reachability has not been proven from this account context.","AWS Config delivery bucket policy compatibility has not been proven from this account context."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI0M2E0NDg0OC04NzBiLTQ0ZTItOWZkOC04NjA1YzJjMDc5NzkiLCJncm91cF9pZCI6IjE4MTc1MDlkLTBmMzMtNDQxNC1iNjA2LTQzOGZmZjhkYTkyNiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIyMDJlMDJjNy1mMmMxLTRjMjQtYjgxYS0xMTE2OGFjYWQwNTQiLCI3MzA5N2MxMS0xNzRjLTQ1OTctODVhMi05YWY3OTM4NDJlOGQiLCI1YWNjN2QwZS1lMzYxLTQ3NGYtOWVmYS1jMjAwYTAzNThmMGQiLCJhM2QxYWQ5Yi04Y2I3LTQ3Y2MtYjI3MS1jYjE1ZjI2ZGZmZDEiLCIxOGRlODAzZC1iN2NkLTRkZjgtYWQzMC0xNjA0ZGNiMDVjZDUiXSwianRpIjoiMmQ2MjUwZTItNzBjZS00MmZkLWIzOGUtZmY5YjYwNGM3NzI2IiwiaWF0IjoxNzc0MjA3OTc0LCJleHAiOjE3NzQyOTQzNzR9.Ij1V33Q6BD7aHcsmJJWhB3dioaC-z75_hIX1VRpxH_c","event":"finished","reporting_source":"bundle_callback","action_results":[],"non_executable_results":[{"action_id":"202e02c7-f2c1-4c24-b81a-11168acad054","support_tier":"review_required_bundle","profile_id":"config_enable_account_local_delivery","strategy_id":"config_enable_account_local_delivery","reason":"review_required_metadata_only","blocked_reasons":["AWS Config delivery bucket reachability has not been proven from this account context.","AWS Config delivery bucket policy compatibility has not been proven from this account context."]},{"action_id":"73097c11-174c-4597-85a2-9af793842e8d","support_tier":"review_required_bundle","profile_id":"config_enable_account_local_delivery","strategy_id":"config_enable_account_local_delivery","reason":"review_required_metadata_only","blocked_reasons":["AWS Config delivery bucket reachability has not been proven from this account context.","AWS Config delivery bucket policy compatibility has not been proven from this account context."]},{"action_id":"5acc7d0e-e361-474f-9efa-c200a0358f0d","support_tier":"review_required_bundle","profile_id":"config_enable_account_local_delivery","strategy_id":"config_enable_account_local_delivery","reason":"review_required_metadata_only","blocked_reasons":["AWS Config delivery bucket reachability has not been proven from this account context.","AWS Config delivery bucket policy compatibility has not been proven from this account context."]},{"action_id":"a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1","support_tier":"review_required_bundle","profile_id":"config_enable_account_local_delivery","strategy_id":"config_enable_account_local_delivery","reason":"review_required_metadata_only","blocked_reasons":["AWS Config delivery bucket reachability has not been proven from this account context.","AWS Config delivery bucket policy compatibility has not been proven from this account context."]},{"action_id":"18de803d-b7cd-4df8-ad30-1604dcb05cd5","support_tier":"review_required_bundle","profile_id":"config_enable_account_local_delivery","strategy_id":"config_enable_account_local_delivery","reason":"review_required_metadata_only","blocked_reasons":["AWS Config delivery bucket reachability has not been proven from this account context.","AWS Config delivery bucket policy compatibility has not been proven from this account context."]}]}'
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
