#!/usr/bin/env bash
set +e

REPORT_URL="http://127.0.0.1:18020/api/internal/group-runs/report"
REPORT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJmYTAzY2NkZi0xZDc4LTQzOGItYjEwYS0wOGE1ODY3YzRiNDMiLCJncm91cF9ydW5faWQiOiJjYWRhMGNhNy1jMDBlLTRlNWMtYjNmYS05YTYxYzdhNGJjNGYiLCJncm91cF9pZCI6IjRhOWU5NTZjLTA4YmQtNDMzMC04OGNhLTRmOGVhY2FlMDVlYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJkNmViOWNiOS0zMzI1LTRhNWUtYTI1MC03NjBjMDAyNmZmMTAiLCIwMGI4YzM5Yy02OWE0LTQ1NTctOGM3My03ZDk2ZTRkNzJjMTkiLCIxZGYwMTI2ZC1kNDI0LTQxY2QtYjA1Zi1jMzA3OTc0MmU0YjQiLCIzZjY4Y2VmOC01MDI5LTQzZDktYWQ0MS1lZTBiYjc4ZTg4MTUiLCI3ZGYyODY2Mi0yZTc2LTQ2N2MtYWYxMi05MTI4Yzk0ZjMxZDkiLCI3ZjYyNGUwNy02MWVhLTRjZjEtYmE5Zi05M2I1MTg5OWRjN2MiLCI4MTYyNWI2YS01MWZlLTRkMjUtODg2OS1iMDEwNDIxOTE5YTMiLCI5MmY1ZjVhMy1kNmMwLTRjYzQtYjM0OS1lOTA5NDBhMWU3OGEiLCI5YzYyMjMxZi04ZjlmLTQ5NzItYmJjZC00MjYwZjVkNWRjMDIiLCIwMDZiNmJhNi1hOWY1LTRiMTUtOTdjMS0yNjE2YjdkOWIyYzgiLCJjOTcxNmViMy1lZTRkLTRhOTItYWYyZi00NjRmZGFiYjk5NGUiXSwianRpIjoiOGY2N2IxNDctZmIxOC00ZjYyLTkzMDUtNmEyMTExZmZmZWNiIiwiaWF0IjoxNzczNjIwNDgzLCJleHAiOjE3NzM3MDY4ODN9.NjtfhVOcFX7oZeZs4W55sJQ5-9YHEGmkOeDrT5NWiRs"
STARTED_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJmYTAzY2NkZi0xZDc4LTQzOGItYjEwYS0wOGE1ODY3YzRiNDMiLCJncm91cF9ydW5faWQiOiJjYWRhMGNhNy1jMDBlLTRlNWMtYjNmYS05YTYxYzdhNGJjNGYiLCJncm91cF9pZCI6IjRhOWU5NTZjLTA4YmQtNDMzMC04OGNhLTRmOGVhY2FlMDVlYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJkNmViOWNiOS0zMzI1LTRhNWUtYTI1MC03NjBjMDAyNmZmMTAiLCIwMGI4YzM5Yy02OWE0LTQ1NTctOGM3My03ZDk2ZTRkNzJjMTkiLCIxZGYwMTI2ZC1kNDI0LTQxY2QtYjA1Zi1jMzA3OTc0MmU0YjQiLCIzZjY4Y2VmOC01MDI5LTQzZDktYWQ0MS1lZTBiYjc4ZTg4MTUiLCI3ZGYyODY2Mi0yZTc2LTQ2N2MtYWYxMi05MTI4Yzk0ZjMxZDkiLCI3ZjYyNGUwNy02MWVhLTRjZjEtYmE5Zi05M2I1MTg5OWRjN2MiLCI4MTYyNWI2YS01MWZlLTRkMjUtODg2OS1iMDEwNDIxOTE5YTMiLCI5MmY1ZjVhMy1kNmMwLTRjYzQtYjM0OS1lOTA5NDBhMWU3OGEiLCI5YzYyMjMxZi04ZjlmLTQ5NzItYmJjZC00MjYwZjVkNWRjMDIiLCIwMDZiNmJhNi1hOWY1LTRiMTUtOTdjMS0yNjE2YjdkOWIyYzgiLCJjOTcxNmViMy1lZTRkLTRhOTItYWYyZi00NjRmZGFiYjk5NGUiXSwianRpIjoiOGY2N2IxNDctZmIxOC00ZjYyLTkzMDUtNmEyMTExZmZmZWNiIiwiaWF0IjoxNzczNjIwNDgzLCJleHAiOjE3NzM3MDY4ODN9.NjtfhVOcFX7oZeZs4W55sJQ5-9YHEGmkOeDrT5NWiRs", "event": "started", "reporting_source": "bundle_callback"}
FINISHED_SUCCESS_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJmYTAzY2NkZi0xZDc4LTQzOGItYjEwYS0wOGE1ODY3YzRiNDMiLCJncm91cF9ydW5faWQiOiJjYWRhMGNhNy1jMDBlLTRlNWMtYjNmYS05YTYxYzdhNGJjNGYiLCJncm91cF9pZCI6IjRhOWU5NTZjLTA4YmQtNDMzMC04OGNhLTRmOGVhY2FlMDVlYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJkNmViOWNiOS0zMzI1LTRhNWUtYTI1MC03NjBjMDAyNmZmMTAiLCIwMGI4YzM5Yy02OWE0LTQ1NTctOGM3My03ZDk2ZTRkNzJjMTkiLCIxZGYwMTI2ZC1kNDI0LTQxY2QtYjA1Zi1jMzA3OTc0MmU0YjQiLCIzZjY4Y2VmOC01MDI5LTQzZDktYWQ0MS1lZTBiYjc4ZTg4MTUiLCI3ZGYyODY2Mi0yZTc2LTQ2N2MtYWYxMi05MTI4Yzk0ZjMxZDkiLCI3ZjYyNGUwNy02MWVhLTRjZjEtYmE5Zi05M2I1MTg5OWRjN2MiLCI4MTYyNWI2YS01MWZlLTRkMjUtODg2OS1iMDEwNDIxOTE5YTMiLCI5MmY1ZjVhMy1kNmMwLTRjYzQtYjM0OS1lOTA5NDBhMWU3OGEiLCI5YzYyMjMxZi04ZjlmLTQ5NzItYmJjZC00MjYwZjVkNWRjMDIiLCIwMDZiNmJhNi1hOWY1LTRiMTUtOTdjMS0yNjE2YjdkOWIyYzgiLCJjOTcxNmViMy1lZTRkLTRhOTItYWYyZi00NjRmZGFiYjk5NGUiXSwianRpIjoiOGY2N2IxNDctZmIxOC00ZjYyLTkzMDUtNmEyMTExZmZmZWNiIiwiaWF0IjoxNzczNjIwNDgzLCJleHAiOjE3NzM3MDY4ODN9.NjtfhVOcFX7oZeZs4W55sJQ5-9YHEGmkOeDrT5NWiRs", "event": "finished", "reporting_source": "bundle_callback", "action_results": [{"action_id": "1df0126d-d424-41cd-b05f-c3079742e4b4", "execution_status": "success"}, {"action_id": "3f68cef8-5029-43d9-ad41-ee0bb78e8815", "execution_status": "success"}, {"action_id": "7df28662-2e76-467c-af12-9128c94f31d9", "execution_status": "success"}, {"action_id": "7f624e07-61ea-4cf1-ba9f-93b51899dc7c", "execution_status": "success"}, {"action_id": "81625b6a-51fe-4d25-8869-b010421919a3", "execution_status": "success"}, {"action_id": "9c62231f-8f9f-4972-bbcd-4260f5d5dc02", "execution_status": "success"}], "non_executable_results": [{"action_id": "006b6ba6-a9f5-4b15-97c1-2616b7d9b2c8", "support_tier": "manual_guidance_only", "profile_id": "s3_enable_abort_incomplete_uploads", "strategy_id": "s3_enable_abort_incomplete_uploads", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["AccessDenied", "Lifecycle preservation evidence is missing for additive merge review."]}, {"action_id": "00b8c39c-69a4-4557-8c73-7d96e4d72c19", "support_tier": "manual_guidance_only", "profile_id": "s3_enable_abort_incomplete_uploads", "strategy_id": "s3_enable_abort_incomplete_uploads", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["AccessDenied", "Lifecycle preservation evidence is missing for additive merge review."]}, {"action_id": "92f5f5a3-d6c0-4cc4-b349-e90940a1e78a", "support_tier": "manual_guidance_only", "profile_id": "s3_enable_abort_incomplete_uploads", "strategy_id": "s3_enable_abort_incomplete_uploads", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["AccessDenied", "Lifecycle preservation evidence is missing for additive merge review."]}, {"action_id": "d6eb9cb9-3325-4a5e-a250-760c0026ff10", "support_tier": "manual_guidance_only", "profile_id": "s3_enable_abort_incomplete_uploads", "strategy_id": "s3_enable_abort_incomplete_uploads", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["AccessDenied", "Lifecycle preservation evidence is missing for additive merge review."]}, {"action_id": "c9716eb3-ee4d-4a92-af2f-464fdabb994e", "support_tier": "manual_guidance_only", "profile_id": "s3_enable_abort_incomplete_uploads", "strategy_id": "s3_enable_abort_incomplete_uploads", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["Lifecycle preservation evidence is missing for additive merge review."]}]}
FINISHED_FAILED_TEMPLATE={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJmYTAzY2NkZi0xZDc4LTQzOGItYjEwYS0wOGE1ODY3YzRiNDMiLCJncm91cF9ydW5faWQiOiJjYWRhMGNhNy1jMDBlLTRlNWMtYjNmYS05YTYxYzdhNGJjNGYiLCJncm91cF9pZCI6IjRhOWU5NTZjLTA4YmQtNDMzMC04OGNhLTRmOGVhY2FlMDVlYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJkNmViOWNiOS0zMzI1LTRhNWUtYTI1MC03NjBjMDAyNmZmMTAiLCIwMGI4YzM5Yy02OWE0LTQ1NTctOGM3My03ZDk2ZTRkNzJjMTkiLCIxZGYwMTI2ZC1kNDI0LTQxY2QtYjA1Zi1jMzA3OTc0MmU0YjQiLCIzZjY4Y2VmOC01MDI5LTQzZDktYWQ0MS1lZTBiYjc4ZTg4MTUiLCI3ZGYyODY2Mi0yZTc2LTQ2N2MtYWYxMi05MTI4Yzk0ZjMxZDkiLCI3ZjYyNGUwNy02MWVhLTRjZjEtYmE5Zi05M2I1MTg5OWRjN2MiLCI4MTYyNWI2YS01MWZlLTRkMjUtODg2OS1iMDEwNDIxOTE5YTMiLCI5MmY1ZjVhMy1kNmMwLTRjYzQtYjM0OS1lOTA5NDBhMWU3OGEiLCI5YzYyMjMxZi04ZjlmLTQ5NzItYmJjZC00MjYwZjVkNWRjMDIiLCIwMDZiNmJhNi1hOWY1LTRiMTUtOTdjMS0yNjE2YjdkOWIyYzgiLCJjOTcxNmViMy1lZTRkLTRhOTItYWYyZi00NjRmZGFiYjk5NGUiXSwianRpIjoiOGY2N2IxNDctZmIxOC00ZjYyLTkzMDUtNmEyMTExZmZmZWNiIiwiaWF0IjoxNzczNjIwNDgzLCJleHAiOjE3NzM3MDY4ODN9.NjtfhVOcFX7oZeZs4W55sJQ5-9YHEGmkOeDrT5NWiRs", "event": "finished", "reporting_source": "bundle_callback", "action_results": [{"action_id": "1df0126d-d424-41cd-b05f-c3079742e4b4", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "3f68cef8-5029-43d9-ad41-ee0bb78e8815", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "7df28662-2e76-467c-af12-9128c94f31d9", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "7f624e07-61ea-4cf1-ba9f-93b51899dc7c", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "81625b6a-51fe-4d25-8869-b010421919a3", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}, {"action_id": "9c62231f-8f9f-4972-bbcd-4260f5d5dc02", "execution_status": "failed", "execution_error_code": "bundle_runner_failed", "execution_error_message": "run_actions.sh exited non-zero"}], "non_executable_results": [{"action_id": "006b6ba6-a9f5-4b15-97c1-2616b7d9b2c8", "support_tier": "manual_guidance_only", "profile_id": "s3_enable_abort_incomplete_uploads", "strategy_id": "s3_enable_abort_incomplete_uploads", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["AccessDenied", "Lifecycle preservation evidence is missing for additive merge review."]}, {"action_id": "00b8c39c-69a4-4557-8c73-7d96e4d72c19", "support_tier": "manual_guidance_only", "profile_id": "s3_enable_abort_incomplete_uploads", "strategy_id": "s3_enable_abort_incomplete_uploads", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["AccessDenied", "Lifecycle preservation evidence is missing for additive merge review."]}, {"action_id": "92f5f5a3-d6c0-4cc4-b349-e90940a1e78a", "support_tier": "manual_guidance_only", "profile_id": "s3_enable_abort_incomplete_uploads", "strategy_id": "s3_enable_abort_incomplete_uploads", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["AccessDenied", "Lifecycle preservation evidence is missing for additive merge review."]}, {"action_id": "d6eb9cb9-3325-4a5e-a250-760c0026ff10", "support_tier": "manual_guidance_only", "profile_id": "s3_enable_abort_incomplete_uploads", "strategy_id": "s3_enable_abort_incomplete_uploads", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["AccessDenied", "Lifecycle preservation evidence is missing for additive merge review."]}, {"action_id": "c9716eb3-ee4d-4a92-af2f-464fdabb994e", "support_tier": "manual_guidance_only", "profile_id": "s3_enable_abort_incomplete_uploads", "strategy_id": "s3_enable_abort_incomplete_uploads", "reason": "manual_guidance_metadata_only", "blocked_reasons": ["Lifecycle preservation evidence is missing for additive merge review."]}]}
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
