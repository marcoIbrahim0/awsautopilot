#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI2YzI3YTk3NC00MjMyLTQ0NjctOTlkMi1jOTg4NjVlMjQ4ZjMiLCJncm91cF9pZCI6ImVlZmU2NmQxLTkxZTYtNDljZC1hMjdhLTVjMWFmYTcyNTU3ZCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI4MmVkMjZiMS1kOWFjLTQ2OWItODAwOC1hMmFjZGM4OWJkMzgiLCJhMWQ4ZjNiZi1lMzgxLTQ3ZDYtOTgxOC0xYTMwOTYyOTIzODEiLCJjNTMzZGZmMy1hMGYwLTRkNzYtOGRkMy0xOTMxNWZiM2U0N2QiLCJlNTVkY2E5My02NDY3LTRkY2UtYmE2Yy0xNjQ0NGYyNTk3NjAiLCI0YTVhNzY1ZS1jZjdkLTQwYmYtOTFjMi0xOWEzNjFkMjQyYWUiXSwianRpIjoiNzI3NjUyZjAtZmQ3OC00ZTViLTllNTktMTRkNzkzODc5NThlIiwiaWF0IjoxNzc0MjA3Mzg5LCJleHAiOjE3NzQyOTM3ODl9.5wTvgEBbZRzlYjy3D5nkVTJGxnhVnIhu3EgvwWgIjMA
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI2YzI3YTk3NC00MjMyLTQ0NjctOTlkMi1jOTg4NjVlMjQ4ZjMiLCJncm91cF9pZCI6ImVlZmU2NmQxLTkxZTYtNDljZC1hMjdhLTVjMWFmYTcyNTU3ZCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI4MmVkMjZiMS1kOWFjLTQ2OWItODAwOC1hMmFjZGM4OWJkMzgiLCJhMWQ4ZjNiZi1lMzgxLTQ3ZDYtOTgxOC0xYTMwOTYyOTIzODEiLCJjNTMzZGZmMy1hMGYwLTRkNzYtOGRkMy0xOTMxNWZiM2U0N2QiLCJlNTVkY2E5My02NDY3LTRkY2UtYmE2Yy0xNjQ0NGYyNTk3NjAiLCI0YTVhNzY1ZS1jZjdkLTQwYmYtOTFjMi0xOWEzNjFkMjQyYWUiXSwianRpIjoiNzI3NjUyZjAtZmQ3OC00ZTViLTllNTktMTRkNzkzODc5NThlIiwiaWF0IjoxNzc0MjA3Mzg5LCJleHAiOjE3NzQyOTM3ODl9.5wTvgEBbZRzlYjy3D5nkVTJGxnhVnIhu3EgvwWgIjMA","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI2YzI3YTk3NC00MjMyLTQ0NjctOTlkMi1jOTg4NjVlMjQ4ZjMiLCJncm91cF9pZCI6ImVlZmU2NmQxLTkxZTYtNDljZC1hMjdhLTVjMWFmYTcyNTU3ZCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI4MmVkMjZiMS1kOWFjLTQ2OWItODAwOC1hMmFjZGM4OWJkMzgiLCJhMWQ4ZjNiZi1lMzgxLTQ3ZDYtOTgxOC0xYTMwOTYyOTIzODEiLCJjNTMzZGZmMy1hMGYwLTRkNzYtOGRkMy0xOTMxNWZiM2U0N2QiLCJlNTVkY2E5My02NDY3LTRkY2UtYmE2Yy0xNjQ0NGYyNTk3NjAiLCI0YTVhNzY1ZS1jZjdkLTQwYmYtOTFjMi0xOWEzNjFkMjQyYWUiXSwianRpIjoiNzI3NjUyZjAtZmQ3OC00ZTViLTllNTktMTRkNzkzODc5NThlIiwiaWF0IjoxNzc0MjA3Mzg5LCJleHAiOjE3NzQyOTM3ODl9.5wTvgEBbZRzlYjy3D5nkVTJGxnhVnIhu3EgvwWgIjMA","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"82ed26b1-d9ac-469b-8008-a2acdc89bd38","execution_status":"success"},{"action_id":"a1d8f3bf-e381-47d6-9818-1a3096292381","execution_status":"success"},{"action_id":"c533dff3-a0f0-4d76-8dd3-19315fb3e47d","execution_status":"success"},{"action_id":"e55dca93-6467-4dce-ba6c-16444f259760","execution_status":"success"}],"non_executable_results":[{"action_id":"4a5a765e-cf7d-40bf-91c2-19a361d242ae","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["Lifecycle preservation evidence is missing for additive merge review."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI2YzI3YTk3NC00MjMyLTQ0NjctOTlkMi1jOTg4NjVlMjQ4ZjMiLCJncm91cF9pZCI6ImVlZmU2NmQxLTkxZTYtNDljZC1hMjdhLTVjMWFmYTcyNTU3ZCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyI4MmVkMjZiMS1kOWFjLTQ2OWItODAwOC1hMmFjZGM4OWJkMzgiLCJhMWQ4ZjNiZi1lMzgxLTQ3ZDYtOTgxOC0xYTMwOTYyOTIzODEiLCJjNTMzZGZmMy1hMGYwLTRkNzYtOGRkMy0xOTMxNWZiM2U0N2QiLCJlNTVkY2E5My02NDY3LTRkY2UtYmE2Yy0xNjQ0NGYyNTk3NjAiLCI0YTVhNzY1ZS1jZjdkLTQwYmYtOTFjMi0xOWEzNjFkMjQyYWUiXSwianRpIjoiNzI3NjUyZjAtZmQ3OC00ZTViLTllNTktMTRkNzkzODc5NThlIiwiaWF0IjoxNzc0MjA3Mzg5LCJleHAiOjE3NzQyOTM3ODl9.5wTvgEBbZRzlYjy3D5nkVTJGxnhVnIhu3EgvwWgIjMA","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"82ed26b1-d9ac-469b-8008-a2acdc89bd38","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"a1d8f3bf-e381-47d6-9818-1a3096292381","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"c533dff3-a0f0-4d76-8dd3-19315fb3e47d","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e55dca93-6467-4dce-ba6c-16444f259760","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"4a5a765e-cf7d-40bf-91c2-19a361d242ae","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["Lifecycle preservation evidence is missing for additive merge review."]}]}'
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
