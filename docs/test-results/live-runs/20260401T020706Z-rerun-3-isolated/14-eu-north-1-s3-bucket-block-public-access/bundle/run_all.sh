#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJiYzYyOGFjZS04M2JmLTQ3MDktYjAxMy1jMDQyYmIzZjg3OTgiLCJncm91cF9pZCI6IjI5OTA5MDdjLWI2YmItNDgyMS05ODI1LWE1MjNjYjM4MGJmNSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIxZTI4ZGJiMS1jZjhjLTQzMDEtYmRlYy1mMjBmMzdjNjlhODkiLCIwOTYwYWJhNy1lZGRkLTQ4ZDctYWFmYy01Mzc5ZDFlNDgyZDkiLCIwYjg3ODM5Yi0yOGY1LTQxNTAtYWYyNi03NGNmMmIxYWYzYTMiLCI2ODhmNWVkMC05NTk0LTRkZjEtOTg4My1jYzE3ZmVjYTYyZjgiLCIzNTJhYzliMi1kMzQzLTQwYWMtYjQyNy00YzRmMjg1NjE1ZWYiLCIwOGE5ZjYyOS0zYmZhLTQ2YTEtYmQ4OC1lMjIwMjdmN2UxMzMiLCI3NTIyYmM5Zi01Y2FiLTRiYWQtOTA4Yi1hMzgyMDQ1ZjhkODciLCI0YTk2NWZhYy1jMTM5LTQ2ZTMtODU5NC0xMTA1OGIxZGZlMjQiLCJjZGI1M2Y1Yy04NzAxLTQ5N2QtYTg2Ni00MjU2Y2RkZDlkNjYiLCI1NTcxZTkwOS02NDkxLTQwNzctODE4ZS01NDQxYWUwZGM5NWQiLCJiZGZhODViYy1iM2EzLTQ0NTYtYjhkOS05ZWQxZGQ4OTVhZDMiLCI1MmFmZDRkMi0zNzM4LTQxNmUtYjM3Yi1mYmUxMTBkYmEzZmUiLCJkNDg3MmUxOS00YTk1LTRjYmMtOGJjNi0wMTJiM2NjZjZkMDkiLCIzOWQ3YWQxMi03OTgxLTQ2MTQtOWE2Yi04ZWMzZjdhN2I1YzEiLCJlODg4NDZmYS03MWQyLTQyOTEtYWUxMi0yYzEzYjFiNDk1NDQiXSwianRpIjoiNDY2OGZhMDAtNDdlOC00YTI4LWE5OTQtMDAyYWI0ZDlhNzkzIiwiaWF0IjoxNzc1MDA0MjU0LCJleHAiOjE3NzUwOTA2NTR9.p4u25cvfv4ry-jECnaFOW6Qu4D3VwPW-X7sElDWt0_g
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJiYzYyOGFjZS04M2JmLTQ3MDktYjAxMy1jMDQyYmIzZjg3OTgiLCJncm91cF9pZCI6IjI5OTA5MDdjLWI2YmItNDgyMS05ODI1LWE1MjNjYjM4MGJmNSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIxZTI4ZGJiMS1jZjhjLTQzMDEtYmRlYy1mMjBmMzdjNjlhODkiLCIwOTYwYWJhNy1lZGRkLTQ4ZDctYWFmYy01Mzc5ZDFlNDgyZDkiLCIwYjg3ODM5Yi0yOGY1LTQxNTAtYWYyNi03NGNmMmIxYWYzYTMiLCI2ODhmNWVkMC05NTk0LTRkZjEtOTg4My1jYzE3ZmVjYTYyZjgiLCIzNTJhYzliMi1kMzQzLTQwYWMtYjQyNy00YzRmMjg1NjE1ZWYiLCIwOGE5ZjYyOS0zYmZhLTQ2YTEtYmQ4OC1lMjIwMjdmN2UxMzMiLCI3NTIyYmM5Zi01Y2FiLTRiYWQtOTA4Yi1hMzgyMDQ1ZjhkODciLCI0YTk2NWZhYy1jMTM5LTQ2ZTMtODU5NC0xMTA1OGIxZGZlMjQiLCJjZGI1M2Y1Yy04NzAxLTQ5N2QtYTg2Ni00MjU2Y2RkZDlkNjYiLCI1NTcxZTkwOS02NDkxLTQwNzctODE4ZS01NDQxYWUwZGM5NWQiLCJiZGZhODViYy1iM2EzLTQ0NTYtYjhkOS05ZWQxZGQ4OTVhZDMiLCI1MmFmZDRkMi0zNzM4LTQxNmUtYjM3Yi1mYmUxMTBkYmEzZmUiLCJkNDg3MmUxOS00YTk1LTRjYmMtOGJjNi0wMTJiM2NjZjZkMDkiLCIzOWQ3YWQxMi03OTgxLTQ2MTQtOWE2Yi04ZWMzZjdhN2I1YzEiLCJlODg4NDZmYS03MWQyLTQyOTEtYWUxMi0yYzEzYjFiNDk1NDQiXSwianRpIjoiNDY2OGZhMDAtNDdlOC00YTI4LWE5OTQtMDAyYWI0ZDlhNzkzIiwiaWF0IjoxNzc1MDA0MjU0LCJleHAiOjE3NzUwOTA2NTR9.p4u25cvfv4ry-jECnaFOW6Qu4D3VwPW-X7sElDWt0_g","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJiYzYyOGFjZS04M2JmLTQ3MDktYjAxMy1jMDQyYmIzZjg3OTgiLCJncm91cF9pZCI6IjI5OTA5MDdjLWI2YmItNDgyMS05ODI1LWE1MjNjYjM4MGJmNSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIxZTI4ZGJiMS1jZjhjLTQzMDEtYmRlYy1mMjBmMzdjNjlhODkiLCIwOTYwYWJhNy1lZGRkLTQ4ZDctYWFmYy01Mzc5ZDFlNDgyZDkiLCIwYjg3ODM5Yi0yOGY1LTQxNTAtYWYyNi03NGNmMmIxYWYzYTMiLCI2ODhmNWVkMC05NTk0LTRkZjEtOTg4My1jYzE3ZmVjYTYyZjgiLCIzNTJhYzliMi1kMzQzLTQwYWMtYjQyNy00YzRmMjg1NjE1ZWYiLCIwOGE5ZjYyOS0zYmZhLTQ2YTEtYmQ4OC1lMjIwMjdmN2UxMzMiLCI3NTIyYmM5Zi01Y2FiLTRiYWQtOTA4Yi1hMzgyMDQ1ZjhkODciLCI0YTk2NWZhYy1jMTM5LTQ2ZTMtODU5NC0xMTA1OGIxZGZlMjQiLCJjZGI1M2Y1Yy04NzAxLTQ5N2QtYTg2Ni00MjU2Y2RkZDlkNjYiLCI1NTcxZTkwOS02NDkxLTQwNzctODE4ZS01NDQxYWUwZGM5NWQiLCJiZGZhODViYy1iM2EzLTQ0NTYtYjhkOS05ZWQxZGQ4OTVhZDMiLCI1MmFmZDRkMi0zNzM4LTQxNmUtYjM3Yi1mYmUxMTBkYmEzZmUiLCJkNDg3MmUxOS00YTk1LTRjYmMtOGJjNi0wMTJiM2NjZjZkMDkiLCIzOWQ3YWQxMi03OTgxLTQ2MTQtOWE2Yi04ZWMzZjdhN2I1YzEiLCJlODg4NDZmYS03MWQyLTQyOTEtYWUxMi0yYzEzYjFiNDk1NDQiXSwianRpIjoiNDY2OGZhMDAtNDdlOC00YTI4LWE5OTQtMDAyYWI0ZDlhNzkzIiwiaWF0IjoxNzc1MDA0MjU0LCJleHAiOjE3NzUwOTA2NTR9.p4u25cvfv4ry-jECnaFOW6Qu4D3VwPW-X7sElDWt0_g","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"0960aba7-eddd-48d7-aafc-5379d1e482d9","execution_status":"success"},{"action_id":"1e28dbb1-cf8c-4301-bdec-f20f37c69a89","execution_status":"success"},{"action_id":"0b87839b-28f5-4150-af26-74cf2b1af3a3","execution_status":"success"},{"action_id":"688f5ed0-9594-4df1-9883-cc17feca62f8","execution_status":"success"},{"action_id":"352ac9b2-d343-40ac-b427-4c4f285615ef","execution_status":"success"},{"action_id":"7522bc9f-5cab-4bad-908b-a382045f8d87","execution_status":"success"},{"action_id":"4a965fac-c139-46e3-8594-11058b1dfe24","execution_status":"success"},{"action_id":"cdb53f5c-8701-497d-a866-4256cddd9d66","execution_status":"success"},{"action_id":"5571e909-6491-4077-818e-5441ae0dc95d","execution_status":"success"},{"action_id":"bdfa85bc-b3a3-4456-b8d9-9ed1dd895ad3","execution_status":"success"},{"action_id":"52afd4d2-3738-416e-b37b-fbe110dba3fe","execution_status":"success"},{"action_id":"d4872e19-4a95-4cbc-8bc6-012b3ccf6d09","execution_status":"success"},{"action_id":"39d7ad12-7981-4614-9a6b-8ec3f7a7b5c1","execution_status":"success"},{"action_id":"e88846fa-71d2-4291-ae12-2c13b1b49544","execution_status":"success"}],"non_executable_results":[{"action_id":"08a9f629-3bfa-46a1-bd88-e22027f7e133","support_tier":"manual_guidance_only","profile_id":"s3_migrate_cloudfront_oac_private_manual_preservation","strategy_id":"s3_migrate_cloudfront_oac_private","reason":"manual_guidance_metadata_only","blocked_reasons":["Existing bucket policy preservation evidence is missing for CloudFront + OAC migration.","Missing bucket identifier for access-path validation."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiJiYzYyOGFjZS04M2JmLTQ3MDktYjAxMy1jMDQyYmIzZjg3OTgiLCJncm91cF9pZCI6IjI5OTA5MDdjLWI2YmItNDgyMS05ODI1LWE1MjNjYjM4MGJmNSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIxZTI4ZGJiMS1jZjhjLTQzMDEtYmRlYy1mMjBmMzdjNjlhODkiLCIwOTYwYWJhNy1lZGRkLTQ4ZDctYWFmYy01Mzc5ZDFlNDgyZDkiLCIwYjg3ODM5Yi0yOGY1LTQxNTAtYWYyNi03NGNmMmIxYWYzYTMiLCI2ODhmNWVkMC05NTk0LTRkZjEtOTg4My1jYzE3ZmVjYTYyZjgiLCIzNTJhYzliMi1kMzQzLTQwYWMtYjQyNy00YzRmMjg1NjE1ZWYiLCIwOGE5ZjYyOS0zYmZhLTQ2YTEtYmQ4OC1lMjIwMjdmN2UxMzMiLCI3NTIyYmM5Zi01Y2FiLTRiYWQtOTA4Yi1hMzgyMDQ1ZjhkODciLCI0YTk2NWZhYy1jMTM5LTQ2ZTMtODU5NC0xMTA1OGIxZGZlMjQiLCJjZGI1M2Y1Yy04NzAxLTQ5N2QtYTg2Ni00MjU2Y2RkZDlkNjYiLCI1NTcxZTkwOS02NDkxLTQwNzctODE4ZS01NDQxYWUwZGM5NWQiLCJiZGZhODViYy1iM2EzLTQ0NTYtYjhkOS05ZWQxZGQ4OTVhZDMiLCI1MmFmZDRkMi0zNzM4LTQxNmUtYjM3Yi1mYmUxMTBkYmEzZmUiLCJkNDg3MmUxOS00YTk1LTRjYmMtOGJjNi0wMTJiM2NjZjZkMDkiLCIzOWQ3YWQxMi03OTgxLTQ2MTQtOWE2Yi04ZWMzZjdhN2I1YzEiLCJlODg4NDZmYS03MWQyLTQyOTEtYWUxMi0yYzEzYjFiNDk1NDQiXSwianRpIjoiNDY2OGZhMDAtNDdlOC00YTI4LWE5OTQtMDAyYWI0ZDlhNzkzIiwiaWF0IjoxNzc1MDA0MjU0LCJleHAiOjE3NzUwOTA2NTR9.p4u25cvfv4ry-jECnaFOW6Qu4D3VwPW-X7sElDWt0_g","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"0960aba7-eddd-48d7-aafc-5379d1e482d9","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"1e28dbb1-cf8c-4301-bdec-f20f37c69a89","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"0b87839b-28f5-4150-af26-74cf2b1af3a3","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"688f5ed0-9594-4df1-9883-cc17feca62f8","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"352ac9b2-d343-40ac-b427-4c4f285615ef","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"7522bc9f-5cab-4bad-908b-a382045f8d87","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4a965fac-c139-46e3-8594-11058b1dfe24","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"cdb53f5c-8701-497d-a866-4256cddd9d66","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"5571e909-6491-4077-818e-5441ae0dc95d","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"bdfa85bc-b3a3-4456-b8d9-9ed1dd895ad3","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"52afd4d2-3738-416e-b37b-fbe110dba3fe","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"d4872e19-4a95-4cbc-8bc6-012b3ccf6d09","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"39d7ad12-7981-4614-9a6b-8ec3f7a7b5c1","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e88846fa-71d2-4291-ae12-2c13b1b49544","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"08a9f629-3bfa-46a1-bd88-e22027f7e133","support_tier":"manual_guidance_only","profile_id":"s3_migrate_cloudfront_oac_private_manual_preservation","strategy_id":"s3_migrate_cloudfront_oac_private","reason":"manual_guidance_metadata_only","blocked_reasons":["Existing bucket policy preservation evidence is missing for CloudFront + OAC migration.","Missing bucket identifier for access-path validation."]}]}'
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
