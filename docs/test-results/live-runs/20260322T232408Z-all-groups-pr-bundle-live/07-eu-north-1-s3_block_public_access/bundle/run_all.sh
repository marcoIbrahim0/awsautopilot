#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI3MTU2YThiNi04NzU5LTRjMzUtYjc5OS05ZDBjY2Y5NzU4MDAiLCJncm91cF9pZCI6ImY1OTg0NzM4LTgzYWMtNDQ0Yy1iN2UwLTMwNmEyYjMwZTE1YyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI2MmU3ZmYwZC01ZGQ1LTRjY2QtYTJkOC1mNjJiNGYwZDdlOGIiXSwianRpIjoiYzgwMTM3NTctZWQ2OS00ZTU5LTgwMmYtNTliYWJlZjk0MWFlIiwiaWF0IjoxNzc0MjIxOTYwLCJleHAiOjE3NzQzMDgzNjB9.bpqV9euQdShHlKE4_AT1x7v9Bl67CQl3cbeyVFmkK-4
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI3MTU2YThiNi04NzU5LTRjMzUtYjc5OS05ZDBjY2Y5NzU4MDAiLCJncm91cF9pZCI6ImY1OTg0NzM4LTgzYWMtNDQ0Yy1iN2UwLTMwNmEyYjMwZTE1YyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI2MmU3ZmYwZC01ZGQ1LTRjY2QtYTJkOC1mNjJiNGYwZDdlOGIiXSwianRpIjoiYzgwMTM3NTctZWQ2OS00ZTU5LTgwMmYtNTliYWJlZjk0MWFlIiwiaWF0IjoxNzc0MjIxOTYwLCJleHAiOjE3NzQzMDgzNjB9.bpqV9euQdShHlKE4_AT1x7v9Bl67CQl3cbeyVFmkK-4","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI3MTU2YThiNi04NzU5LTRjMzUtYjc5OS05ZDBjY2Y5NzU4MDAiLCJncm91cF9pZCI6ImY1OTg0NzM4LTgzYWMtNDQ0Yy1iN2UwLTMwNmEyYjMwZTE1YyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI2MmU3ZmYwZC01ZGQ1LTRjY2QtYTJkOC1mNjJiNGYwZDdlOGIiXSwianRpIjoiYzgwMTM3NTctZWQ2OS00ZTU5LTgwMmYtNTliYWJlZjk0MWFlIiwiaWF0IjoxNzc0MjIxOTYwLCJleHAiOjE3NzQzMDgzNjB9.bpqV9euQdShHlKE4_AT1x7v9Bl67CQl3cbeyVFmkK-4","event":"finished","reporting_source":"bundle_callback","action_results":[],"non_executable_results":[{"action_id":"62e7ff0d-5dd5-4ccd-a2d8-f62b4f0d7e8b","support_tier":"review_required_bundle","profile_id":"s3_account_block_public_access_pr_bundle","strategy_id":"s3_account_block_public_access_pr_bundle","reason":"review_required_metadata_only","blocked_reasons":[]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI3MTU2YThiNi04NzU5LTRjMzUtYjc5OS05ZDBjY2Y5NzU4MDAiLCJncm91cF9pZCI6ImY1OTg0NzM4LTgzYWMtNDQ0Yy1iN2UwLTMwNmEyYjMwZTE1YyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI2MmU3ZmYwZC01ZGQ1LTRjY2QtYTJkOC1mNjJiNGYwZDdlOGIiXSwianRpIjoiYzgwMTM3NTctZWQ2OS00ZTU5LTgwMmYtNTliYWJlZjk0MWFlIiwiaWF0IjoxNzc0MjIxOTYwLCJleHAiOjE3NzQzMDgzNjB9.bpqV9euQdShHlKE4_AT1x7v9Bl67CQl3cbeyVFmkK-4","event":"finished","reporting_source":"bundle_callback","action_results":[],"non_executable_results":[{"action_id":"62e7ff0d-5dd5-4ccd-a2d8-f62b4f0d7e8b","support_tier":"review_required_bundle","profile_id":"s3_account_block_public_access_pr_bundle","strategy_id":"s3_account_block_public_access_pr_bundle","reason":"review_required_metadata_only","blocked_reasons":[]}]}'
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
