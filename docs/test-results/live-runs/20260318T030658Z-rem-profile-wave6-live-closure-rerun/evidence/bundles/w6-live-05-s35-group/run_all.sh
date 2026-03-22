#!/usr/bin/env bash
set +e

REPORT_URL=http://127.0.0.1:18022/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiJkZjZhNGIzNC0wMGI2LTRiZmYtYmU2YS00M2RiMTliOWE0YmQiLCJncm91cF9pZCI6IjNiZGEyM2E4LWI4MDMtNDE3ZC05MmM0LTk2YTQxMTBjNGJjMSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmMzExMDI2OS1jOTY0LTRiOWQtOWRiMi0zODA5Nzc0NzZjMzkiLCIyYjAyMGMyMC05NWEwLTRlMjktYjM4OC03Yjc2NDkzOGFkMTUiLCIzMzJhN2Q2Zi1jZGFkLTQ3ZTQtYWI4Yi02ZDg0NTkyNDg5NDAiLCI0Y2EzNmE4NS0wNmExLTQ4ZjQtYWM3NS04ZGYzNTZjMDFlYjkiLCI2MWM0ZWQ4MC0yNzc4LTQyYTAtYjBmMi00ZmYxMDk1ZjkwMzciLCI2NDY1MGJjZi0wMGYzLTQ3ZDItYmUzOS0zY2Y3NzBlNGUyNmIiLCI4ZTRhOTAyZC1iMDFkLTRmZWEtOWU4NC1mZWZlMzM4MzFlYzkiLCI4ZjFiNmNmNS05ZWNhLTQ1ZTUtYmUzNS1iNTg1MWQzNDVhMzgiLCI5Yzk5Y2Q3ZS0wN2M1LTRlYmUtOTk4OS01YzE3MjA1M2I2NGYiLCIwYTU2MmYyNi03Y2U4LTQ3MTktOGMzZi1kMjhiZWY0ZTU0M2MiLCJlYWJmZTE5ZS03NDAzLTQ5ZGItYTk0NC1hMGIyMzYxMDc1NTQiLCJjODllMmMwMS1jZGExLTRkMzUtODk0NS1jY2E4MDk2YjhiNjAiXSwianRpIjoiYjY2ZmZmM2UtNWM4Mi00YTU0LTgxZDItYzk0ZTg1YzU2Zjk5IiwiaWF0IjoxNzczODQ4MzYxLCJleHAiOjE3NzM5MzQ3NjF9.U7qYtgdTxBGqiXfn-l6y-MiuoDtSGSSyVcYhRo87tW0
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiJkZjZhNGIzNC0wMGI2LTRiZmYtYmU2YS00M2RiMTliOWE0YmQiLCJncm91cF9pZCI6IjNiZGEyM2E4LWI4MDMtNDE3ZC05MmM0LTk2YTQxMTBjNGJjMSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmMzExMDI2OS1jOTY0LTRiOWQtOWRiMi0zODA5Nzc0NzZjMzkiLCIyYjAyMGMyMC05NWEwLTRlMjktYjM4OC03Yjc2NDkzOGFkMTUiLCIzMzJhN2Q2Zi1jZGFkLTQ3ZTQtYWI4Yi02ZDg0NTkyNDg5NDAiLCI0Y2EzNmE4NS0wNmExLTQ4ZjQtYWM3NS04ZGYzNTZjMDFlYjkiLCI2MWM0ZWQ4MC0yNzc4LTQyYTAtYjBmMi00ZmYxMDk1ZjkwMzciLCI2NDY1MGJjZi0wMGYzLTQ3ZDItYmUzOS0zY2Y3NzBlNGUyNmIiLCI4ZTRhOTAyZC1iMDFkLTRmZWEtOWU4NC1mZWZlMzM4MzFlYzkiLCI4ZjFiNmNmNS05ZWNhLTQ1ZTUtYmUzNS1iNTg1MWQzNDVhMzgiLCI5Yzk5Y2Q3ZS0wN2M1LTRlYmUtOTk4OS01YzE3MjA1M2I2NGYiLCIwYTU2MmYyNi03Y2U4LTQ3MTktOGMzZi1kMjhiZWY0ZTU0M2MiLCJlYWJmZTE5ZS03NDAzLTQ5ZGItYTk0NC1hMGIyMzYxMDc1NTQiLCJjODllMmMwMS1jZGExLTRkMzUtODk0NS1jY2E4MDk2YjhiNjAiXSwianRpIjoiYjY2ZmZmM2UtNWM4Mi00YTU0LTgxZDItYzk0ZTg1YzU2Zjk5IiwiaWF0IjoxNzczODQ4MzYxLCJleHAiOjE3NzM5MzQ3NjF9.U7qYtgdTxBGqiXfn-l6y-MiuoDtSGSSyVcYhRo87tW0","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiJkZjZhNGIzNC0wMGI2LTRiZmYtYmU2YS00M2RiMTliOWE0YmQiLCJncm91cF9pZCI6IjNiZGEyM2E4LWI4MDMtNDE3ZC05MmM0LTk2YTQxMTBjNGJjMSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmMzExMDI2OS1jOTY0LTRiOWQtOWRiMi0zODA5Nzc0NzZjMzkiLCIyYjAyMGMyMC05NWEwLTRlMjktYjM4OC03Yjc2NDkzOGFkMTUiLCIzMzJhN2Q2Zi1jZGFkLTQ3ZTQtYWI4Yi02ZDg0NTkyNDg5NDAiLCI0Y2EzNmE4NS0wNmExLTQ4ZjQtYWM3NS04ZGYzNTZjMDFlYjkiLCI2MWM0ZWQ4MC0yNzc4LTQyYTAtYjBmMi00ZmYxMDk1ZjkwMzciLCI2NDY1MGJjZi0wMGYzLTQ3ZDItYmUzOS0zY2Y3NzBlNGUyNmIiLCI4ZTRhOTAyZC1iMDFkLTRmZWEtOWU4NC1mZWZlMzM4MzFlYzkiLCI4ZjFiNmNmNS05ZWNhLTQ1ZTUtYmUzNS1iNTg1MWQzNDVhMzgiLCI5Yzk5Y2Q3ZS0wN2M1LTRlYmUtOTk4OS01YzE3MjA1M2I2NGYiLCIwYTU2MmYyNi03Y2U4LTQ3MTktOGMzZi1kMjhiZWY0ZTU0M2MiLCJlYWJmZTE5ZS03NDAzLTQ5ZGItYTk0NC1hMGIyMzYxMDc1NTQiLCJjODllMmMwMS1jZGExLTRkMzUtODk0NS1jY2E4MDk2YjhiNjAiXSwianRpIjoiYjY2ZmZmM2UtNWM4Mi00YTU0LTgxZDItYzk0ZTg1YzU2Zjk5IiwiaWF0IjoxNzczODQ4MzYxLCJleHAiOjE3NzM5MzQ3NjF9.U7qYtgdTxBGqiXfn-l6y-MiuoDtSGSSyVcYhRo87tW0","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"332a7d6f-cdad-47e4-ab8b-6d8459248940","execution_status":"success"},{"action_id":"4ca36a85-06a1-48f4-ac75-8df356c01eb9","execution_status":"success"},{"action_id":"64650bcf-00f3-47d2-be39-3cf770e4e26b","execution_status":"success"},{"action_id":"8e4a902d-b01d-4fea-9e84-fefe33831ec9","execution_status":"success"},{"action_id":"8f1b6cf5-9eca-45e5-be35-b5851d345a38","execution_status":"success"},{"action_id":"eabfe19e-7403-49db-a944-a0b236107554","execution_status":"success"},{"action_id":"f3110269-c964-4b9d-9db2-380977476c39","execution_status":"success"}],"non_executable_results":[{"action_id":"0a562f26-7ce8-4719-8c3f-d28bef4e543c","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["AccessDenied","Bucket policy preservation evidence is missing for merge-safe SSL enforcement.","Existing bucket policy capture failed (AccessDenied)."]},{"action_id":"2b020c20-95a0-4e29-b388-7b764938ad15","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["AccessDenied","Bucket policy preservation evidence is missing for merge-safe SSL enforcement.","Existing bucket policy capture failed (AccessDenied)."]},{"action_id":"61c4ed80-2778-42a0-b0f2-4ff1095f9037","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["AccessDenied","Bucket policy preservation evidence is missing for merge-safe SSL enforcement.","Existing bucket policy capture failed (AccessDenied)."]},{"action_id":"9c99cd7e-07c5-4ebe-9989-5c172053b64f","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["AccessDenied","Bucket policy preservation evidence is missing for merge-safe SSL enforcement.","Existing bucket policy capture failed (AccessDenied)."]},{"action_id":"c89e2c01-cda1-4d35-8945-cca8096b8b60","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["Bucket policy preservation evidence is missing for merge-safe SSL enforcement."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI3ZjEwOWVmZi0yNWJlLTQ3MDgtYWYxOC0xYzVlZjU2ZTNhMjAiLCJncm91cF9ydW5faWQiOiJkZjZhNGIzNC0wMGI2LTRiZmYtYmU2YS00M2RiMTliOWE0YmQiLCJncm91cF9pZCI6IjNiZGEyM2E4LWI4MDMtNDE3ZC05MmM0LTk2YTQxMTBjNGJjMSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmMzExMDI2OS1jOTY0LTRiOWQtOWRiMi0zODA5Nzc0NzZjMzkiLCIyYjAyMGMyMC05NWEwLTRlMjktYjM4OC03Yjc2NDkzOGFkMTUiLCIzMzJhN2Q2Zi1jZGFkLTQ3ZTQtYWI4Yi02ZDg0NTkyNDg5NDAiLCI0Y2EzNmE4NS0wNmExLTQ4ZjQtYWM3NS04ZGYzNTZjMDFlYjkiLCI2MWM0ZWQ4MC0yNzc4LTQyYTAtYjBmMi00ZmYxMDk1ZjkwMzciLCI2NDY1MGJjZi0wMGYzLTQ3ZDItYmUzOS0zY2Y3NzBlNGUyNmIiLCI4ZTRhOTAyZC1iMDFkLTRmZWEtOWU4NC1mZWZlMzM4MzFlYzkiLCI4ZjFiNmNmNS05ZWNhLTQ1ZTUtYmUzNS1iNTg1MWQzNDVhMzgiLCI5Yzk5Y2Q3ZS0wN2M1LTRlYmUtOTk4OS01YzE3MjA1M2I2NGYiLCIwYTU2MmYyNi03Y2U4LTQ3MTktOGMzZi1kMjhiZWY0ZTU0M2MiLCJlYWJmZTE5ZS03NDAzLTQ5ZGItYTk0NC1hMGIyMzYxMDc1NTQiLCJjODllMmMwMS1jZGExLTRkMzUtODk0NS1jY2E4MDk2YjhiNjAiXSwianRpIjoiYjY2ZmZmM2UtNWM4Mi00YTU0LTgxZDItYzk0ZTg1YzU2Zjk5IiwiaWF0IjoxNzczODQ4MzYxLCJleHAiOjE3NzM5MzQ3NjF9.U7qYtgdTxBGqiXfn-l6y-MiuoDtSGSSyVcYhRo87tW0","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"332a7d6f-cdad-47e4-ab8b-6d8459248940","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4ca36a85-06a1-48f4-ac75-8df356c01eb9","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"64650bcf-00f3-47d2-be39-3cf770e4e26b","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"8e4a902d-b01d-4fea-9e84-fefe33831ec9","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"8f1b6cf5-9eca-45e5-be35-b5851d345a38","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"eabfe19e-7403-49db-a944-a0b236107554","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"f3110269-c964-4b9d-9db2-380977476c39","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"0a562f26-7ce8-4719-8c3f-d28bef4e543c","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["AccessDenied","Bucket policy preservation evidence is missing for merge-safe SSL enforcement.","Existing bucket policy capture failed (AccessDenied)."]},{"action_id":"2b020c20-95a0-4e29-b388-7b764938ad15","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["AccessDenied","Bucket policy preservation evidence is missing for merge-safe SSL enforcement.","Existing bucket policy capture failed (AccessDenied)."]},{"action_id":"61c4ed80-2778-42a0-b0f2-4ff1095f9037","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["AccessDenied","Bucket policy preservation evidence is missing for merge-safe SSL enforcement.","Existing bucket policy capture failed (AccessDenied)."]},{"action_id":"9c99cd7e-07c5-4ebe-9989-5c172053b64f","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["AccessDenied","Bucket policy preservation evidence is missing for merge-safe SSL enforcement.","Existing bucket policy capture failed (AccessDenied)."]},{"action_id":"c89e2c01-cda1-4d35-8945-cca8096b8b60","support_tier":"review_required_bundle","profile_id":"s3_enforce_ssl_strict_deny","strategy_id":"s3_enforce_ssl_strict_deny","reason":"review_required_metadata_only","blocked_reasons":["Bucket policy preservation evidence is missing for merge-safe SSL enforcement."]}]}'
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
