#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiJmZjA3ODMzNC0xODY5LTRjOWUtOTA2Yy0xMjM4MjUyNTQ1MjkiLCJncm91cF9pZCI6IjNkMjc5MjdlLTkyNTAtNGY5NS04ZGVlLWJjOGFkYjQwN2U4OCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJiMWM1OTJjMC1kZTljLTQzZDAtYmY0MC04ODNkOGFlMTYyM2QiLCIzZWViMDE5NS00NGUzLTRkZjYtOWFlMy03OGUwMjAzNDhlNDIiXSwianRpIjoiMTkxNTlkMDYtZDcyOC00YTg3LWE1NDUtMzVkYzhkMWY3OGViIiwiaWF0IjoxNzc0MjA3MTQzLCJleHAiOjE3NzQyOTM1NDN9.vLNPjTaTFzzf_rnWqtG_riFK2dL0A2jujKMWnxmKD8s
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiJmZjA3ODMzNC0xODY5LTRjOWUtOTA2Yy0xMjM4MjUyNTQ1MjkiLCJncm91cF9pZCI6IjNkMjc5MjdlLTkyNTAtNGY5NS04ZGVlLWJjOGFkYjQwN2U4OCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJiMWM1OTJjMC1kZTljLTQzZDAtYmY0MC04ODNkOGFlMTYyM2QiLCIzZWViMDE5NS00NGUzLTRkZjYtOWFlMy03OGUwMjAzNDhlNDIiXSwianRpIjoiMTkxNTlkMDYtZDcyOC00YTg3LWE1NDUtMzVkYzhkMWY3OGViIiwiaWF0IjoxNzc0MjA3MTQzLCJleHAiOjE3NzQyOTM1NDN9.vLNPjTaTFzzf_rnWqtG_riFK2dL0A2jujKMWnxmKD8s","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiJmZjA3ODMzNC0xODY5LTRjOWUtOTA2Yy0xMjM4MjUyNTQ1MjkiLCJncm91cF9pZCI6IjNkMjc5MjdlLTkyNTAtNGY5NS04ZGVlLWJjOGFkYjQwN2U4OCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJiMWM1OTJjMC1kZTljLTQzZDAtYmY0MC04ODNkOGFlMTYyM2QiLCIzZWViMDE5NS00NGUzLTRkZjYtOWFlMy03OGUwMjAzNDhlNDIiXSwianRpIjoiMTkxNTlkMDYtZDcyOC00YTg3LWE1NDUtMzVkYzhkMWY3OGViIiwiaWF0IjoxNzc0MjA3MTQzLCJleHAiOjE3NzQyOTM1NDN9.vLNPjTaTFzzf_rnWqtG_riFK2dL0A2jujKMWnxmKD8s","event":"finished","reporting_source":"bundle_callback","action_results":[],"non_executable_results":[{"action_id":"b1c592c0-de9c-43d0-bf40-883d8ae1623d","support_tier":"review_required_bundle","profile_id":"snapshot_block_all_sharing","strategy_id":"snapshot_block_all_sharing","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"3eeb0195-44e3-4df6-9ae3-78e020348e42","support_tier":"review_required_bundle","profile_id":"snapshot_block_all_sharing","strategy_id":"snapshot_block_all_sharing","reason":"review_required_metadata_only","blocked_reasons":[]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiJmZjA3ODMzNC0xODY5LTRjOWUtOTA2Yy0xMjM4MjUyNTQ1MjkiLCJncm91cF9pZCI6IjNkMjc5MjdlLTkyNTAtNGY5NS04ZGVlLWJjOGFkYjQwN2U4OCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJiMWM1OTJjMC1kZTljLTQzZDAtYmY0MC04ODNkOGFlMTYyM2QiLCIzZWViMDE5NS00NGUzLTRkZjYtOWFlMy03OGUwMjAzNDhlNDIiXSwianRpIjoiMTkxNTlkMDYtZDcyOC00YTg3LWE1NDUtMzVkYzhkMWY3OGViIiwiaWF0IjoxNzc0MjA3MTQzLCJleHAiOjE3NzQyOTM1NDN9.vLNPjTaTFzzf_rnWqtG_riFK2dL0A2jujKMWnxmKD8s","event":"finished","reporting_source":"bundle_callback","action_results":[],"non_executable_results":[{"action_id":"b1c592c0-de9c-43d0-bf40-883d8ae1623d","support_tier":"review_required_bundle","profile_id":"snapshot_block_all_sharing","strategy_id":"snapshot_block_all_sharing","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"3eeb0195-44e3-4df6-9ae3-78e020348e42","support_tier":"review_required_bundle","profile_id":"snapshot_block_all_sharing","strategy_id":"snapshot_block_all_sharing","reason":"review_required_metadata_only","blocked_reasons":[]}]}'
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
