#!/usr/bin/env bash
set +e

REPORT_URL="http://127.0.0.1:18020/api/internal/group-runs/report"
REPORT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJmYTAzY2NkZi0xZDc4LTQzOGItYjEwYS0wOGE1ODY3YzRiNDMiLCJncm91cF9ydW5faWQiOiJmMzkzZDI5OC00MmMyLTQ2N2YtYTI4MS1hOTNmZjNlMGQ1OTEiLCJncm91cF9pZCI6Ijc2NTg3MGRmLTViYmQtNGQ4MS1hMmE4LTI0YjA5MzJlOGRkMCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmMDRiYTFlYi1iMTUwLTQwYTAtOTRhNS00MDg3ZDAyMzFjMzIiLCIxNmJmODY3Zi01MDQyLTRjYWUtOTlkMi1jNDA2ODg0YjRjOTYiLCIxN2VmZDE4NS0xOThhLTQxYzQtODQ1NC0xMDg3NWFhODlkYWEiLCIyY2I4Mzc0Ni1jMDY4LTRkZWYtOTc3Yi1mZDRiZmVhZDI1MTkiLCIzNDQ4NTBlZS03OTZkLTRmYmMtOTkwNi1lNzQ1YWFmYjJkZjYiLCIzOGE2NDBiMS02MmViLTRkZWItYmQ2NC0yZDhhZWIyNDk5ODIiLCI0YjBiM2U0Zi1iYmU4LTRjNTgtYjljMS1jYTM5Yzg2ODNjYTIiLCI2MDliYjhkYi0zYmQ2LTRkYmMtYjU2Mi1lOTQzMGE0YmRhZWIiLCJhZGM5N2YwOC0xYWFmLTQyODAtODRmMy04NTRmMjEzNjFmNjYiLCJiZGNjMWEzMy04ZDM3LTRkMDEtOGFjOC01YmZhMzliMTFhMWQiLCJkZDY0ODEwYy03ZDgzLTRiNDYtOWM4ZS01ZjNiNDAwYmU4ZDIiLCIwMjQyYTEwNy0zMmZhLTQ0ZjMtYmNhOC04MjBkMTRjMjBhZmYiXSwianRpIjoiMTk5Y2RkMGMtN2M3Yy00OGNkLWE4NmUtNmIzMjg3YTg0MmQ4IiwiaWF0IjoxNzczNjIwNjc1LCJleHAiOjE3NzM3MDcwNzV9.XIbGrHQzkFWr9eHf6nUf4rJvPQ7L6WD8UoHsJGH3onc"
STARTED_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJmYTAzY2NkZi0xZDc4LTQzOGItYjEwYS0wOGE1ODY3YzRiNDMiLCJncm91cF9ydW5faWQiOiJmMzkzZDI5OC00MmMyLTQ2N2YtYTI4MS1hOTNmZjNlMGQ1OTEiLCJncm91cF9pZCI6Ijc2NTg3MGRmLTViYmQtNGQ4MS1hMmE4LTI0YjA5MzJlOGRkMCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmMDRiYTFlYi1iMTUwLTQwYTAtOTRhNS00MDg3ZDAyMzFjMzIiLCIxNmJmODY3Zi01MDQyLTRjYWUtOTlkMi1jNDA2ODg0YjRjOTYiLCIxN2VmZDE4NS0xOThhLTQxYzQtODQ1NC0xMDg3NWFhODlkYWEiLCIyY2I4Mzc0Ni1jMDY4LTRkZWYtOTc3Yi1mZDRiZmVhZDI1MTkiLCIzNDQ4NTBlZS03OTZkLTRmYmMtOTkwNi1lNzQ1YWFmYjJkZjYiLCIzOGE2NDBiMS02MmViLTRkZWItYmQ2NC0yZDhhZWIyNDk5ODIiLCI0YjBiM2U0Zi1iYmU4LTRjNTgtYjljMS1jYTM5Yzg2ODNjYTIiLCI2MDliYjhkYi0zYmQ2LTRkYmMtYjU2Mi1lOTQzMGE0YmRhZWIiLCJhZGM5N2YwOC0xYWFmLTQyODAtODRmMy04NTRmMjEzNjFmNjYiLCJiZGNjMWEzMy04ZDM3LTRkMDEtOGFjOC01YmZhMzliMTFhMWQiLCJkZDY0ODEwYy03ZDgzLTRiNDYtOWM4ZS01ZjNiNDAwYmU4ZDIiLCIwMjQyYTEwNy0zMmZhLTQ0ZjMtYmNhOC04MjBkMTRjMjBhZmYiXSwianRpIjoiMTk5Y2RkMGMtN2M3Yy00OGNkLWE4NmUtNmIzMjg3YTg0MmQ4IiwiaWF0IjoxNzczNjIwNjc1LCJleHAiOjE3NzM3MDcwNzV9.XIbGrHQzkFWr9eHf6nUf4rJvPQ7L6WD8UoHsJGH3onc", "event": "started", "reporting_source": "bundle_callback"}
FINISHED_SUCCESS_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJmYTAzY2NkZi0xZDc4LTQzOGItYjEwYS0wOGE1ODY3YzRiNDMiLCJncm91cF9ydW5faWQiOiJmMzkzZDI5OC00MmMyLTQ2N2YtYTI4MS1hOTNmZjNlMGQ1OTEiLCJncm91cF9pZCI6Ijc2NTg3MGRmLTViYmQtNGQ4MS1hMmE4LTI0YjA5MzJlOGRkMCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmMDRiYTFlYi1iMTUwLTQwYTAtOTRhNS00MDg3ZDAyMzFjMzIiLCIxNmJmODY3Zi01MDQyLTRjYWUtOTlkMi1jNDA2ODg0YjRjOTYiLCIxN2VmZDE4NS0xOThhLTQxYzQtODQ1NC0xMDg3NWFhODlkYWEiLCIyY2I4Mzc0Ni1jMDY4LTRkZWYtOTc3Yi1mZDRiZmVhZDI1MTkiLCIzNDQ4NTBlZS03OTZkLTRmYmMtOTkwNi1lNzQ1YWFmYjJkZjYiLCIzOGE2NDBiMS02MmViLTRkZWItYmQ2NC0yZDhhZWIyNDk5ODIiLCI0YjBiM2U0Zi1iYmU4LTRjNTgtYjljMS1jYTM5Yzg2ODNjYTIiLCI2MDliYjhkYi0zYmQ2LTRkYmMtYjU2Mi1lOTQzMGE0YmRhZWIiLCJhZGM5N2YwOC0xYWFmLTQyODAtODRmMy04NTRmMjEzNjFmNjYiLCJiZGNjMWEzMy04ZDM3LTRkMDEtOGFjOC01YmZhMzliMTFhMWQiLCJkZDY0ODEwYy03ZDgzLTRiNDYtOWM4ZS01ZjNiNDAwYmU4ZDIiLCIwMjQyYTEwNy0zMmZhLTQ0ZjMtYmNhOC04MjBkMTRjMjBhZmYiXSwianRpIjoiMTk5Y2RkMGMtN2M3Yy00OGNkLWE4NmUtNmIzMjg3YTg0MmQ4IiwiaWF0IjoxNzczNjIwNjc1LCJleHAiOjE3NzM3MDcwNzV9.XIbGrHQzkFWr9eHf6nUf4rJvPQ7L6WD8UoHsJGH3onc", "event": "finished", "reporting_source": "bundle_callback", "action_results": [{"action_id": "2cb83746-c068-4def-977b-fd4bfead2519", "execution_status": "success"}, {"action_id": "344850ee-796d-4fbc-9906-e745aafb2df6", "execution_status": "success"}, {"action_id": "38a640b1-62eb-4deb-bd64-2d8aeb249982", "execution_status": "success"}, {"action_id": "4b0b3e4f-bbe8-4c58-b9c1-ca39c8683ca2", "execution_status": "success"}, {"action_id": "609bb8db-3bd6-4dbc-b562-e9430a4bdaeb", "execution_status": "success"}, {"action_id": "adc97f08-1aaf-4280-84f3-854f21361f66", "execution_status": "success"}, {"action_id": "bdcc1a33-8d37-4d01-8ac8-5bfa39b11a1d", "execution_status": "success"}], "non_executable_results": [{"action_id": "16bf867f-5042-4cae-99d2-c406884b4c96", "support_tier": "review_required_bundle", "profile_id": "s3_enforce_ssl_strict_deny", "strategy_id": "s3_enforce_ssl_strict_deny", "reason": "review_required_metadata_only", "blocked_reasons": ["AccessDenied", "Bucket policy preservation evidence is missing for merge-safe SSL enforcement.", "Existing bucket policy capture failed (AccessDenied)."]}, {"action_id": "17efd185-198a-41c4-8454-10875aa89daa", "support_tier": "review_required_bundle", "profile_id": "s3_enforce_ssl_strict_deny", "strategy_id": "s3_enforce_ssl_strict_deny", "reason": "review_required_metadata_only", "blocked_reasons": ["AccessDenied", "Bucket policy preservation evidence is missing for merge-safe SSL enforcement.", "Existing bucket policy capture failed (AccessDenied)."]}, {"action_id": "dd64810c-7d83-4b46-9c8e-5f3b400be8d2", "support_tier": "review_required_bundle", "profile_id": "s3_enforce_ssl_strict_deny", "strategy_id": "s3_enforce_ssl_strict_deny", "reason": "review_required_metadata_only", "blocked_reasons": ["AccessDenied", "Bucket policy preservation evidence is missing for merge-safe SSL enforcement.", "Existing bucket policy capture failed (AccessDenied)."]}, {"action_id": "f04ba1eb-b150-40a0-94a5-4087d0231c32", "support_tier": "review_required_bundle", "profile_id": "s3_enforce_ssl_strict_deny", "strategy_id": "s3_enforce_ssl_strict_deny", "reason": "review_required_metadata_only", "blocked_reasons": ["AccessDenied", "Bucket policy preservation evidence is missing for merge-safe SSL enforcement.", "Existing bucket policy capture failed (AccessDenied)."]}, {"action_id": "0242a107-32fa-44f3-bca8-820d14c20aff", "support_tier": "review_required_bundle", "profile_id": "s3_enforce_ssl_strict_deny", "strategy_id": "s3_enforce_ssl_strict_deny", "reason": "review_required_metadata_only", "blocked_reasons": ["Bucket policy preservation evidence is missing for merge-safe SSL enforcement."]}]}
FINISHED_FAILED_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJmYTAzY2NkZi0xZDc4LTQzOGItYjEwYS0wOGE1ODY3YzRiNDMiLCJncm91cF9ydW5faWQiOiJmMzkzZDI5OC00MmMyLTQ2N2YtYTI4MS1hOTNmZjNlMGQ1OTEiLCJncm91cF9pZCI6Ijc2NTg3MGRmLTViYmQtNGQ4MS1hMmE4LTI0YjA5MzJlOGRkMCIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJmMDRiYTFlYi1iMTUwLTQwYTAtOTRhNS00MDg3ZDAyMzFjMzIiLCIxNmJmODY3Zi01MDQyLTRjYWUtOTlkMi1jNDA2ODg0YjRjOTYiLCIxN2VmZDE4NS0xOThhLTQxYzQtODQ1NC0xMDg3NWFhODlkYWEiLCIyY2I4Mzc0Ni1jMDY4LTRkZWYtOTc3Yi1mZDRiZmVhZDI1MTkiLCIzNDQ4NTBlZS03OTZkLTRmYmMtOTkwNi1lNzQ1YWFmYjJkZjYiLCIzOGE2NDBiMS02MmViLTRkZWItYmQ2NC0yZDhhZWIyNDk5ODIiLCI0YjBiM2U0Zi1iYmU4LTRjNTgtYjljMS1jYTM5Yzg2ODNjYTIiLCI2MDliYjhkYi0zYmQ2LTRkYmMtYjU2Mi1lOTQzMGE0YmRhZWIiLCJhZGM5N2YwOC0xYWFmLTQyODAtODRmMy04NTRmMjEzNjFmNjYiLCJiZGNjMWEzMy04ZDM3LTRkMDEtOGFjOC01YmZhMzliMTFhMWQiLCJkZDY0ODEwYy03ZDgzLTRiNDYtOWM4ZS01ZjNiNDAwYmU4ZDIiLCIwMjQyYTEwNy0zMmZhLTQ0ZjMtYmNhOC04MjBkMTRjMjBhZmYiXSwianRpIjoiMTk5Y2RkMGMtN2M3Yy00OGNkLWE4NmUtNmIzMjg3YTg0MmQ4IiwiaWF0IjoxNzczNjIwNjc1LCJleHAiOjE3NzM3MDcwNzV9.XIbGrHQzkFWr9eHf6nUf4rJvPQ7L6WD8UoHsJGH3onc", "event": "finished", "reporting_source": "bundle_callback", "action_results": [{"action_id": "2cb83746-c068-4def-977b-fd4bfead2519", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "344850ee-796d-4fbc-9906-e745aafb2df6", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "38a640b1-62eb-4deb-bd64-2d8aeb249982", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "4b0b3e4f-bbe8-4c58-b9c1-ca39c8683ca2", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "609bb8db-3bd6-4dbc-b562-e9430a4bdaeb", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "adc97f08-1aaf-4280-84f3-854f21361f66", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "bdcc1a33-8d37-4d01-8ac8-5bfa39b11a1d", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}], "non_executable_results": [{"action_id": "16bf867f-5042-4cae-99d2-c406884b4c96", "support_tier": "review_required_bundle", "profile_id": "s3_enforce_ssl_strict_deny", "strategy_id": "s3_enforce_ssl_strict_deny", "reason": "review_required_metadata_only", "blocked_reasons": ["AccessDenied", "Bucket policy preservation evidence is missing for merge-safe SSL enforcement.", "Existing bucket policy capture failed (AccessDenied)."]}, {"action_id": "17efd185-198a-41c4-8454-10875aa89daa", "support_tier": "review_required_bundle", "profile_id": "s3_enforce_ssl_strict_deny", "strategy_id": "s3_enforce_ssl_strict_deny", "reason": "review_required_metadata_only", "blocked_reasons": ["AccessDenied", "Bucket policy preservation evidence is missing for merge-safe SSL enforcement.", "Existing bucket policy capture failed (AccessDenied)."]}, {"action_id": "dd64810c-7d83-4b46-9c8e-5f3b400be8d2", "support_tier": "review_required_bundle", "profile_id": "s3_enforce_ssl_strict_deny", "strategy_id": "s3_enforce_ssl_strict_deny", "reason": "review_required_metadata_only", "blocked_reasons": ["AccessDenied", "Bucket policy preservation evidence is missing for merge-safe SSL enforcement.", "Existing bucket policy capture failed (AccessDenied)."]}, {"action_id": "f04ba1eb-b150-40a0-94a5-4087d0231c32", "support_tier": "review_required_bundle", "profile_id": "s3_enforce_ssl_strict_deny", "strategy_id": "s3_enforce_ssl_strict_deny", "reason": "review_required_metadata_only", "blocked_reasons": ["AccessDenied", "Bucket policy preservation evidence is missing for merge-safe SSL enforcement.", "Existing bucket policy capture failed (AccessDenied)."]}, {"action_id": "0242a107-32fa-44f3-bca8-820d14c20aff", "support_tier": "review_required_bundle", "profile_id": "s3_enforce_ssl_strict_deny", "strategy_id": "s3_enforce_ssl_strict_deny", "reason": "review_required_metadata_only", "blocked_reasons": ["Bucket policy preservation evidence is missing for merge-safe SSL enforcement."]}]}
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
