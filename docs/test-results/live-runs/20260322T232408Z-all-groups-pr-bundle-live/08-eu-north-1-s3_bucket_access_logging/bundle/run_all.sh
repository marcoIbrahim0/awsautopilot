#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=<REDACTED_TOKEN>
STARTED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[],"non_executable_results":[{"action_id":"318c8b1d-0a93-43f0-9b32-24014b6dbf15","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"6ba6522c-a1d9-48bd-ab96-b6129f4363b8","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"770a4f18-3858-4efd-8973-a39d154fa919","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"82072bfa-7707-411b-ab5a-4b8a75bef104","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"8499e226-d3e8-4031-b225-9f905160ef5f","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"a8a06ade-67b9-4b5b-89df-1f4f430036a5","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"e97ffef8-f6f9-4417-ac99-0e83305df718","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"ece8a96e-8e9c-44de-a715-d0b7caa061c1","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"f67a9064-2a5f-47fd-820c-15797f354c7c","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"f9535173-3de1-44d0-8583-ee937e1ad811","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"8f64dd84-763c-4081-ad1e-9a36757b5c87","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"257bc11e-c522-4419-8af5-be24ae406691","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"<REDACTED_TOKEN>","event":"finished","reporting_source":"bundle_callback","action_results":[],"non_executable_results":[{"action_id":"318c8b1d-0a93-43f0-9b32-24014b6dbf15","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"6ba6522c-a1d9-48bd-ab96-b6129f4363b8","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"770a4f18-3858-4efd-8973-a39d154fa919","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"82072bfa-7707-411b-ab5a-4b8a75bef104","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"8499e226-d3e8-4031-b225-9f905160ef5f","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"a8a06ade-67b9-4b5b-89df-1f4f430036a5","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"e97ffef8-f6f9-4417-ac99-0e83305df718","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"ece8a96e-8e9c-44de-a715-d0b7caa061c1","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"f67a9064-2a5f-47fd-820c-15797f354c7c","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"f9535173-3de1-44d0-8583-ee937e1ad811","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"8f64dd84-763c-4081-ad1e-9a36757b5c87","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]},{"action_id":"257bc11e-c522-4419-8af5-be24ae406691","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Destination log bucket '"'"'security-autopilot-access-logs-696505809372'"'"' could not be verified from this account context (404)."]}]}'
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
