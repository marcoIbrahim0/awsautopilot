#!/usr/bin/env bash
set +e

REPORT_URL="http://127.0.0.1:18020/api/internal/group-runs/report"
REPORT_TOKEN="<REDACTED_TOKEN>"
STARTED_TEMPLATE={"token": "<REDACTED_TOKEN>", "event": "started", "reporting_source": "bundle_callback"}
FINISHED_SUCCESS_TEMPLATE={"token": "<REDACTED_TOKEN>", "event": "finished", "reporting_source": "bundle_callback", "action_results": [{"action_id": "eabe460f-fe71-44d0-a055-4cff617b4062", "execution_status": "success"}], "non_executable_results": [{"action_id": "09eedbef-47fc-4a0c-b056-576a3aafb5d1", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "3e9757c6-c289-46cc-9b0b-8db375175959", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "700311d6-efc6-45a3-b4e4-09782339d3a2", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "78964522-d996-4c82-9fa5-437ab7f031c7", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "843e358f-1224-41f0-96f4-01c4626d9fae", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "855e6ab2-1daf-4241-a154-21e376b3448a", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "8dd30872-a0f9-46ff-84bd-70491c45ac40", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "e2696a99-0285-4e32-9212-4412c179e4fa", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": ["Log destination must be a dedicated bucket and cannot match the source bucket."]}, {"action_id": "f040f00b-5016-409a-9a73-616b6478c688", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "f291cce1-9732-4f95-a48e-d98a1d5613ea", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "19a73839-da61-4fcc-8fa9-8e29e4d1114b", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}]}
FINISHED_FAILED_TEMPLATE={"token": "<REDACTED_TOKEN>", "event": "finished", "reporting_source": "bundle_callback", "action_results": [{"action_id": "eabe460f-fe71-44d0-a055-4cff617b4062", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}], "non_executable_results": [{"action_id": "09eedbef-47fc-4a0c-b056-576a3aafb5d1", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "3e9757c6-c289-46cc-9b0b-8db375175959", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "700311d6-efc6-45a3-b4e4-09782339d3a2", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "78964522-d996-4c82-9fa5-437ab7f031c7", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "843e358f-1224-41f0-96f4-01c4626d9fae", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "855e6ab2-1daf-4241-a154-21e376b3448a", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "8dd30872-a0f9-46ff-84bd-70491c45ac40", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "e2696a99-0285-4e32-9212-4412c179e4fa", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": ["Log destination must be a dedicated bucket and cannot match the source bucket."]}, {"action_id": "f040f00b-5016-409a-9a73-616b6478c688", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "f291cce1-9732-4f95-a48e-d98a1d5613ea", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}, {"action_id": "19a73839-da61-4fcc-8fa9-8e29e4d1114b", "support_tier": "review_required_bundle", "profile_id": "s3_enable_access_logging_review_destination_safety", "strategy_id": "s3_enable_access_logging_guided", "reason": "review_required_metadata_only", "blocked_reasons": []}]}
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
