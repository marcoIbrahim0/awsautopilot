#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=<REDACTED_TOKEN>
STARTED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[],"non_executable_results":[{"action_id":"abf5eb48-ea9b-48d0-a534-236cf8818bf9","support_tier":"manual_guidance_only","profile_id":"s3_migrate_cloudfront_oac_private_manual_preservation","strategy_id":"s3_migrate_cloudfront_oac_private","reason":"manual_guidance_metadata_only","blocked_reasons":["Unable to inspect bucket website configuration (AccessDenied)."]},{"action_id":"f497bc0c-ddcb-4191-8fa5-c6ed21bbe134","support_tier":"manual_guidance_only","profile_id":"s3_migrate_cloudfront_oac_private_manual_preservation","strategy_id":"s3_migrate_cloudfront_oac_private","reason":"manual_guidance_metadata_only","blocked_reasons":["Unable to inspect bucket website configuration (AccessDenied)."]},{"action_id":"19337c80-843c-40fb-b35c-fd561406009f","support_tier":"manual_guidance_only","profile_id":"s3_migrate_cloudfront_oac_private_manual_preservation","strategy_id":"s3_migrate_cloudfront_oac_private","reason":"manual_guidance_metadata_only","blocked_reasons":["Existing bucket policy preservation evidence is missing for CloudFront + OAC migration.","Missing bucket identifier for access-path validation."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[],"non_executable_results":[{"action_id":"abf5eb48-ea9b-48d0-a534-236cf8818bf9","support_tier":"manual_guidance_only","profile_id":"s3_migrate_cloudfront_oac_private_manual_preservation","strategy_id":"s3_migrate_cloudfront_oac_private","reason":"manual_guidance_metadata_only","blocked_reasons":["Unable to inspect bucket website configuration (AccessDenied)."]},{"action_id":"f497bc0c-ddcb-4191-8fa5-c6ed21bbe134","support_tier":"manual_guidance_only","profile_id":"s3_migrate_cloudfront_oac_private_manual_preservation","strategy_id":"s3_migrate_cloudfront_oac_private","reason":"manual_guidance_metadata_only","blocked_reasons":["Unable to inspect bucket website configuration (AccessDenied)."]},{"action_id":"19337c80-843c-40fb-b35c-fd561406009f","support_tier":"manual_guidance_only","profile_id":"s3_migrate_cloudfront_oac_private_manual_preservation","strategy_id":"s3_migrate_cloudfront_oac_private","reason":"manual_guidance_metadata_only","blocked_reasons":["Existing bucket policy preservation evidence is missing for CloudFront + OAC migration.","Missing bucket identifier for access-path validation."]}]}'
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
