#!/usr/bin/env bash
set +e

REPORT_URL=http://127.0.0.1:18022/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiJiNGZmMzcxMi0wZmM0LTQyNjItOGZjOS01ZTA5ZDlhMjcyNGMiLCJncm91cF9pZCI6IjI3MzliNTNhLTc3ZjQtNGVmYS04ZjJmLTBkMTFjZjgwNzU1ZiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmOTBlN2Q5ZC04OTQ0LTRmMzktYmNlOC0wNjU5YTM2MzVlOGQiLCIyNmEzZjdmMC0zOWZkLTQ5M2MtYjFjMC0xMmRlZDk1YWMyOTciLCIxNTNmZjVmOS02OGYzLTQyMmItOTA4ZC02MGZmYWEyNTUxZGYiLCI2M2I2NWIyNC03ZGNiLTRjOTUtYTc4MS05N2RkNzI3Y2Q2YTYiLCI2NDc2ZTMxOS0wZWI3LTRhYzMtOGI5NC02ODQxNmRjNzc2ODAiLCI3M2U1NWE1Yi01M2M5LTQzNmUtYjMxZS02YzZkZjE0ZWU3MGMiLCJjM2M1NzI1OC00OGFjLTRjZjItYTFmZi04MTA3MDQ2ZTE3MGUiLCJjYjRlMDM1Yy0yYjY3LTRmNzgtOThmZS1kNGJjOWYwMmVlOTYiLCJjZjgwODIwNC1iMDQ2LTQ3MDUtYmJhZi03ZTllZDU1YWY1MzUiLCJkNzRlOTFlMy0zYjM0LTQwOGItYjMzMC0wMThkNWVlZTRlM2UiLCJlYTFmZGEwYy00NDI3LTQxM2UtYjc2OC00YjFhMTNjMWU0NzkiLCIzZDMxZDY3OC1mZDM5LTRjZWItODgwNC1kYzg3OTZhYjI3ZjUiXSwianRpIjoiN2JjNTEzZGMtZTE1Ny00Nzg4LTkxMDctN2M1OWM4OTI4YTA1IiwiaWF0IjoxNzczODY5NzY1LCJleHAiOjE3NzM5NTYxNjV9.EOlEqdXdyxLcPgDTE2prsaMIL9KDYwBeKae0uT1_WRs
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiJiNGZmMzcxMi0wZmM0LTQyNjItOGZjOS01ZTA5ZDlhMjcyNGMiLCJncm91cF9pZCI6IjI3MzliNTNhLTc3ZjQtNGVmYS04ZjJmLTBkMTFjZjgwNzU1ZiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmOTBlN2Q5ZC04OTQ0LTRmMzktYmNlOC0wNjU5YTM2MzVlOGQiLCIyNmEzZjdmMC0zOWZkLTQ5M2MtYjFjMC0xMmRlZDk1YWMyOTciLCIxNTNmZjVmOS02OGYzLTQyMmItOTA4ZC02MGZmYWEyNTUxZGYiLCI2M2I2NWIyNC03ZGNiLTRjOTUtYTc4MS05N2RkNzI3Y2Q2YTYiLCI2NDc2ZTMxOS0wZWI3LTRhYzMtOGI5NC02ODQxNmRjNzc2ODAiLCI3M2U1NWE1Yi01M2M5LTQzNmUtYjMxZS02YzZkZjE0ZWU3MGMiLCJjM2M1NzI1OC00OGFjLTRjZjItYTFmZi04MTA3MDQ2ZTE3MGUiLCJjYjRlMDM1Yy0yYjY3LTRmNzgtOThmZS1kNGJjOWYwMmVlOTYiLCJjZjgwODIwNC1iMDQ2LTQ3MDUtYmJhZi03ZTllZDU1YWY1MzUiLCJkNzRlOTFlMy0zYjM0LTQwOGItYjMzMC0wMThkNWVlZTRlM2UiLCJlYTFmZGEwYy00NDI3LTQxM2UtYjc2OC00YjFhMTNjMWU0NzkiLCIzZDMxZDY3OC1mZDM5LTRjZWItODgwNC1kYzg3OTZhYjI3ZjUiXSwianRpIjoiN2JjNTEzZGMtZTE1Ny00Nzg4LTkxMDctN2M1OWM4OTI4YTA1IiwiaWF0IjoxNzczODY5NzY1LCJleHAiOjE3NzM5NTYxNjV9.EOlEqdXdyxLcPgDTE2prsaMIL9KDYwBeKae0uT1_WRs","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiJiNGZmMzcxMi0wZmM0LTQyNjItOGZjOS01ZTA5ZDlhMjcyNGMiLCJncm91cF9pZCI6IjI3MzliNTNhLTc3ZjQtNGVmYS04ZjJmLTBkMTFjZjgwNzU1ZiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmOTBlN2Q5ZC04OTQ0LTRmMzktYmNlOC0wNjU5YTM2MzVlOGQiLCIyNmEzZjdmMC0zOWZkLTQ5M2MtYjFjMC0xMmRlZDk1YWMyOTciLCIxNTNmZjVmOS02OGYzLTQyMmItOTA4ZC02MGZmYWEyNTUxZGYiLCI2M2I2NWIyNC03ZGNiLTRjOTUtYTc4MS05N2RkNzI3Y2Q2YTYiLCI2NDc2ZTMxOS0wZWI3LTRhYzMtOGI5NC02ODQxNmRjNzc2ODAiLCI3M2U1NWE1Yi01M2M5LTQzNmUtYjMxZS02YzZkZjE0ZWU3MGMiLCJjM2M1NzI1OC00OGFjLTRjZjItYTFmZi04MTA3MDQ2ZTE3MGUiLCJjYjRlMDM1Yy0yYjY3LTRmNzgtOThmZS1kNGJjOWYwMmVlOTYiLCJjZjgwODIwNC1iMDQ2LTQ3MDUtYmJhZi03ZTllZDU1YWY1MzUiLCJkNzRlOTFlMy0zYjM0LTQwOGItYjMzMC0wMThkNWVlZTRlM2UiLCJlYTFmZGEwYy00NDI3LTQxM2UtYjc2OC00YjFhMTNjMWU0NzkiLCIzZDMxZDY3OC1mZDM5LTRjZWItODgwNC1kYzg3OTZhYjI3ZjUiXSwianRpIjoiN2JjNTEzZGMtZTE1Ny00Nzg4LTkxMDctN2M1OWM4OTI4YTA1IiwiaWF0IjoxNzczODY5NzY1LCJleHAiOjE3NzM5NTYxNjV9.EOlEqdXdyxLcPgDTE2prsaMIL9KDYwBeKae0uT1_WRs","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"d74e91e3-3b34-408b-b330-018d5eee4e3e","execution_status":"success"}],"non_executable_results":[{"action_id":"153ff5f9-68f3-422b-908d-60ffaa2551df","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"26a3f7f0-39fd-493c-b1c0-12ded95ac297","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"63b65b24-7dcb-4c95-a781-97dd727cd6a6","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"6476e319-0eb7-4ac3-8b94-68416dc77680","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"73e55a5b-53c9-436e-b31e-6c6df14ee70c","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"c3c57258-48ac-4cf2-a1ff-8107046e170e","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"cb4e035c-2b67-4f78-98fe-d4bc9f02ee96","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Log destination must be a dedicated bucket and cannot match the source bucket."]},{"action_id":"cf808204-b046-4705-bbaf-7e9ed55af535","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"ea1fda0c-4427-413e-b768-4b1a13c1e479","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"f90e7d9d-8944-4f39-bce8-0659a3635e8d","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"3d31d678-fd39-4ceb-8804-dc8796ab27f5","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiJiNGZmMzcxMi0wZmM0LTQyNjItOGZjOS01ZTA5ZDlhMjcyNGMiLCJncm91cF9pZCI6IjI3MzliNTNhLTc3ZjQtNGVmYS04ZjJmLTBkMTFjZjgwNzU1ZiIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmOTBlN2Q5ZC04OTQ0LTRmMzktYmNlOC0wNjU5YTM2MzVlOGQiLCIyNmEzZjdmMC0zOWZkLTQ5M2MtYjFjMC0xMmRlZDk1YWMyOTciLCIxNTNmZjVmOS02OGYzLTQyMmItOTA4ZC02MGZmYWEyNTUxZGYiLCI2M2I2NWIyNC03ZGNiLTRjOTUtYTc4MS05N2RkNzI3Y2Q2YTYiLCI2NDc2ZTMxOS0wZWI3LTRhYzMtOGI5NC02ODQxNmRjNzc2ODAiLCI3M2U1NWE1Yi01M2M5LTQzNmUtYjMxZS02YzZkZjE0ZWU3MGMiLCJjM2M1NzI1OC00OGFjLTRjZjItYTFmZi04MTA3MDQ2ZTE3MGUiLCJjYjRlMDM1Yy0yYjY3LTRmNzgtOThmZS1kNGJjOWYwMmVlOTYiLCJjZjgwODIwNC1iMDQ2LTQ3MDUtYmJhZi03ZTllZDU1YWY1MzUiLCJkNzRlOTFlMy0zYjM0LTQwOGItYjMzMC0wMThkNWVlZTRlM2UiLCJlYTFmZGEwYy00NDI3LTQxM2UtYjc2OC00YjFhMTNjMWU0NzkiLCIzZDMxZDY3OC1mZDM5LTRjZWItODgwNC1kYzg3OTZhYjI3ZjUiXSwianRpIjoiN2JjNTEzZGMtZTE1Ny00Nzg4LTkxMDctN2M1OWM4OTI4YTA1IiwiaWF0IjoxNzczODY5NzY1LCJleHAiOjE3NzM5NTYxNjV9.EOlEqdXdyxLcPgDTE2prsaMIL9KDYwBeKae0uT1_WRs","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"d74e91e3-3b34-408b-b330-018d5eee4e3e","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"153ff5f9-68f3-422b-908d-60ffaa2551df","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"26a3f7f0-39fd-493c-b1c0-12ded95ac297","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"63b65b24-7dcb-4c95-a781-97dd727cd6a6","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"6476e319-0eb7-4ac3-8b94-68416dc77680","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"73e55a5b-53c9-436e-b31e-6c6df14ee70c","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"c3c57258-48ac-4cf2-a1ff-8107046e170e","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"cb4e035c-2b67-4f78-98fe-d4bc9f02ee96","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":["Log destination must be a dedicated bucket and cannot match the source bucket."]},{"action_id":"cf808204-b046-4705-bbaf-7e9ed55af535","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"ea1fda0c-4427-413e-b768-4b1a13c1e479","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"f90e7d9d-8944-4f39-bce8-0659a3635e8d","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]},{"action_id":"3d31d678-fd39-4ceb-8804-dc8796ab27f5","support_tier":"review_required_bundle","profile_id":"s3_enable_access_logging_review_destination_safety","strategy_id":"s3_enable_access_logging_guided","reason":"review_required_metadata_only","blocked_reasons":[]}]}'
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
