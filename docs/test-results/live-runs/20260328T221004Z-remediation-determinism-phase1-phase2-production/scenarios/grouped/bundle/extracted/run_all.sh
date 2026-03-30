#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJjZmUwZWFhMi0wYmUyLTRmZjktYTkwNy0yZjU2YWFmMzM2YjAiLCJncm91cF9pZCI6IjlhOTA0ZTZhLTNhYjgtNGVjYS1iZTkyLWI3MjdiMGFhY2Y2NyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI0Yjk3Y2Y5YS1mNTE0LTQwMzMtYjU0ZS1kZDY3OWM0MjdjZDkiLCI4YWIyOTk5Ny1iYjZjLTQxZmUtYmEwYy0yNmYwMzUyM2YwZWQiLCJjYmUwZDJjMy1jNjA5LTRhYTItYTEyZi02YWZiMzM2Y2Q1MDciLCIxNzZjMjllZC1mY2VjLTQ5MzQtYTFhYi0zNDRiYjRiNmY0NDQiLCJhOWU1YTk4OS0zZGJhLTQxMTQtYWVhZi0yZGRhYzEyMGFjMGMiLCIzN2UwZjcxZC00ODA1LTQ2ZDAtOWY5Zi1iZjQzNDJkN2U2M2MiLCJhYmFhOWRlNy1hYzA4LTRiN2MtODY2MC05MzY5NWU5OTJjMWEiXSwianRpIjoiNWI4ZDU1ZGEtODU4NC00NWZjLThiZmEtY2FhYjM2Zjk0NWQzIiwiaWF0IjoxNzc0NzM4OTIyLCJleHAiOjE3NzQ4MjUzMjJ9.G77cEwzQLuhTTW9GXLOVtt3PNdxDdj-kw09_aFPQEe0
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJjZmUwZWFhMi0wYmUyLTRmZjktYTkwNy0yZjU2YWFmMzM2YjAiLCJncm91cF9pZCI6IjlhOTA0ZTZhLTNhYjgtNGVjYS1iZTkyLWI3MjdiMGFhY2Y2NyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI0Yjk3Y2Y5YS1mNTE0LTQwMzMtYjU0ZS1kZDY3OWM0MjdjZDkiLCI4YWIyOTk5Ny1iYjZjLTQxZmUtYmEwYy0yNmYwMzUyM2YwZWQiLCJjYmUwZDJjMy1jNjA5LTRhYTItYTEyZi02YWZiMzM2Y2Q1MDciLCIxNzZjMjllZC1mY2VjLTQ5MzQtYTFhYi0zNDRiYjRiNmY0NDQiLCJhOWU1YTk4OS0zZGJhLTQxMTQtYWVhZi0yZGRhYzEyMGFjMGMiLCIzN2UwZjcxZC00ODA1LTQ2ZDAtOWY5Zi1iZjQzNDJkN2U2M2MiLCJhYmFhOWRlNy1hYzA4LTRiN2MtODY2MC05MzY5NWU5OTJjMWEiXSwianRpIjoiNWI4ZDU1ZGEtODU4NC00NWZjLThiZmEtY2FhYjM2Zjk0NWQzIiwiaWF0IjoxNzc0NzM4OTIyLCJleHAiOjE3NzQ4MjUzMjJ9.G77cEwzQLuhTTW9GXLOVtt3PNdxDdj-kw09_aFPQEe0","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJjZmUwZWFhMi0wYmUyLTRmZjktYTkwNy0yZjU2YWFmMzM2YjAiLCJncm91cF9pZCI6IjlhOTA0ZTZhLTNhYjgtNGVjYS1iZTkyLWI3MjdiMGFhY2Y2NyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI0Yjk3Y2Y5YS1mNTE0LTQwMzMtYjU0ZS1kZDY3OWM0MjdjZDkiLCI4YWIyOTk5Ny1iYjZjLTQxZmUtYmEwYy0yNmYwMzUyM2YwZWQiLCJjYmUwZDJjMy1jNjA5LTRhYTItYTEyZi02YWZiMzM2Y2Q1MDciLCIxNzZjMjllZC1mY2VjLTQ5MzQtYTFhYi0zNDRiYjRiNmY0NDQiLCJhOWU1YTk4OS0zZGJhLTQxMTQtYWVhZi0yZGRhYzEyMGFjMGMiLCIzN2UwZjcxZC00ODA1LTQ2ZDAtOWY5Zi1iZjQzNDJkN2U2M2MiLCJhYmFhOWRlNy1hYzA4LTRiN2MtODY2MC05MzY5NWU5OTJjMWEiXSwianRpIjoiNWI4ZDU1ZGEtODU4NC00NWZjLThiZmEtY2FhYjM2Zjk0NWQzIiwiaWF0IjoxNzc0NzM4OTIyLCJleHAiOjE3NzQ4MjUzMjJ9.G77cEwzQLuhTTW9GXLOVtt3PNdxDdj-kw09_aFPQEe0","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"4b97cf9a-f514-4033-b54e-dd679c427cd9","execution_status":"success"},{"action_id":"8ab29997-bb6c-41fe-ba0c-26f03523f0ed","execution_status":"success"}],"non_executable_results":[{"action_id":"cbe0d2c3-c609-4aa2-a12f-6afb336cd507","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"176c29ed-fcec-4934-a1ab-344bb4b6f444","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["NoSuchBucket","Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"a9e5a989-3dba-4114-aeaf-2ddac120ac0c","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["NoSuchBucket","Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"37e0f71d-4805-46d0-9f9f-bf4342d7e63c","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["NoSuchBucket","Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"abaa9de7-ac08-4b7c-8660-93695e992c1a","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["NoSuchBucket","Lifecycle preservation evidence is missing for additive merge review."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJjZmUwZWFhMi0wYmUyLTRmZjktYTkwNy0yZjU2YWFmMzM2YjAiLCJncm91cF9pZCI6IjlhOTA0ZTZhLTNhYjgtNGVjYS1iZTkyLWI3MjdiMGFhY2Y2NyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI0Yjk3Y2Y5YS1mNTE0LTQwMzMtYjU0ZS1kZDY3OWM0MjdjZDkiLCI4YWIyOTk5Ny1iYjZjLTQxZmUtYmEwYy0yNmYwMzUyM2YwZWQiLCJjYmUwZDJjMy1jNjA5LTRhYTItYTEyZi02YWZiMzM2Y2Q1MDciLCIxNzZjMjllZC1mY2VjLTQ5MzQtYTFhYi0zNDRiYjRiNmY0NDQiLCJhOWU1YTk4OS0zZGJhLTQxMTQtYWVhZi0yZGRhYzEyMGFjMGMiLCIzN2UwZjcxZC00ODA1LTQ2ZDAtOWY5Zi1iZjQzNDJkN2U2M2MiLCJhYmFhOWRlNy1hYzA4LTRiN2MtODY2MC05MzY5NWU5OTJjMWEiXSwianRpIjoiNWI4ZDU1ZGEtODU4NC00NWZjLThiZmEtY2FhYjM2Zjk0NWQzIiwiaWF0IjoxNzc0NzM4OTIyLCJleHAiOjE3NzQ4MjUzMjJ9.G77cEwzQLuhTTW9GXLOVtt3PNdxDdj-kw09_aFPQEe0","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"4b97cf9a-f514-4033-b54e-dd679c427cd9","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"8ab29997-bb6c-41fe-ba0c-26f03523f0ed","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"cbe0d2c3-c609-4aa2-a12f-6afb336cd507","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"176c29ed-fcec-4934-a1ab-344bb4b6f444","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["NoSuchBucket","Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"a9e5a989-3dba-4114-aeaf-2ddac120ac0c","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["NoSuchBucket","Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"37e0f71d-4805-46d0-9f9f-bf4342d7e63c","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["NoSuchBucket","Lifecycle preservation evidence is missing for additive merge review."]},{"action_id":"abaa9de7-ac08-4b7c-8660-93695e992c1a","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["NoSuchBucket","Lifecycle preservation evidence is missing for additive merge review."]}]}'
REPLAY_DIR="./.bundle-callback-replay"
RUNNER="./run_actions.sh"
RUN_RC=1
FINISH_SENT=0

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
    local response_file http_code rc
    response_file=$(mktemp)
    http_code=$(curl -sS       --connect-timeout 5       --max-time 20       --retry 4       --retry-delay 2       --retry-all-errors       -o "$response_file"       -w "%{http_code}"       -X POST "$REPORT_URL"       -H "Content-Type: application/json"       -d "$payload")
    rc=$?
    if [ "$rc" -ne 0 ]; then
      rm -f "$response_file"
      return "$rc"
    fi
    rm -f "$response_file"
    case "$http_code" in
      2??)
        return 0
        ;;
    esac
    return 1
  fi
  return 1
}

persist_replay() {
  local suffix="$1"
  local payload="$2"
  local file="$REPLAY_DIR/${suffix}-$(date +%s).json"
  printf '%s\n' "$payload" > "$file"
}

emit_finished_callback() {
  local exit_code="$1"
  local finished_at payload
  if [ "$FINISH_SENT" -eq 1 ]; then
    return 0
  fi
  FINISH_SENT=1
  finished_at="$(iso_now)"
  if [ "$exit_code" -eq 0 ]; then
    payload="$(inject_timestamp "$FINISHED_SUCCESS_TEMPLATE" "finished_at" "$finished_at")"
  else
    payload="$(inject_timestamp "$FINISHED_FAILED_TEMPLATE" "finished_at" "$finished_at")"
  fi
  if ! post_payload "$payload"; then
    persist_replay "finished" "$payload"
  fi
}

handle_exit() {
  local exit_code="$1"
  emit_finished_callback "$exit_code"
  exit "$exit_code"
}

STARTED_AT="$(iso_now)"
START_PAYLOAD="$(inject_timestamp "$STARTED_TEMPLATE" "started_at" "$STARTED_AT")"
if ! post_payload "$START_PAYLOAD"; then
  persist_replay "started" "$START_PAYLOAD"
fi

trap 'handle_exit $?' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

chmod +x "$RUNNER"
"$RUNNER"
RUN_RC=$?
exit "$RUN_RC"
