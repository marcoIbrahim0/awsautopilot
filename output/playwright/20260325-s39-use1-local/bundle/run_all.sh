#!/usr/bin/env bash
set +e

REPORT_URL=http://127.0.0.1:8000/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJjMzM1MWEwMi0wYmMyLTQ0NDktYmVlZC1kNTlkN2FjOTM3ZDAiLCJncm91cF9ydW5faWQiOiI0NzI5NTEyMS02YTIzLTQ2MGYtODY1Yy02ZTY0NWM0ZjAyMzEiLCJncm91cF9pZCI6ImM5MTgwM2M0LTYzYzQtNGJiZS05M2NhLTcyMmJlZjg4MzNmYyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJjNmM5MjBmZC1iOWY2LTQwMTUtOGVkZS1hMDcyZDVhZDIyYzUiXSwianRpIjoiZDc5NGIxOGQtMThhNC00NDM0LTg1NTEtNmFkNGZkNTA3YzU0IiwiaWF0IjoxNzc0NDcwOTAyLCJleHAiOjE3NzQ1NTczMDJ9.zmYXn77lQT1yGAfT-mF1SBE-klvk7PPFnUvYaKr25TQ
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJjMzM1MWEwMi0wYmMyLTQ0NDktYmVlZC1kNTlkN2FjOTM3ZDAiLCJncm91cF9ydW5faWQiOiI0NzI5NTEyMS02YTIzLTQ2MGYtODY1Yy02ZTY0NWM0ZjAyMzEiLCJncm91cF9pZCI6ImM5MTgwM2M0LTYzYzQtNGJiZS05M2NhLTcyMmJlZjg4MzNmYyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJjNmM5MjBmZC1iOWY2LTQwMTUtOGVkZS1hMDcyZDVhZDIyYzUiXSwianRpIjoiZDc5NGIxOGQtMThhNC00NDM0LTg1NTEtNmFkNGZkNTA3YzU0IiwiaWF0IjoxNzc0NDcwOTAyLCJleHAiOjE3NzQ1NTczMDJ9.zmYXn77lQT1yGAfT-mF1SBE-klvk7PPFnUvYaKr25TQ","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJjMzM1MWEwMi0wYmMyLTQ0NDktYmVlZC1kNTlkN2FjOTM3ZDAiLCJncm91cF9ydW5faWQiOiI0NzI5NTEyMS02YTIzLTQ2MGYtODY1Yy02ZTY0NWM0ZjAyMzEiLCJncm91cF9pZCI6ImM5MTgwM2M0LTYzYzQtNGJiZS05M2NhLTcyMmJlZjg4MzNmYyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJjNmM5MjBmZC1iOWY2LTQwMTUtOGVkZS1hMDcyZDVhZDIyYzUiXSwianRpIjoiZDc5NGIxOGQtMThhNC00NDM0LTg1NTEtNmFkNGZkNTA3YzU0IiwiaWF0IjoxNzc0NDcwOTAyLCJleHAiOjE3NzQ1NTczMDJ9.zmYXn77lQT1yGAfT-mF1SBE-klvk7PPFnUvYaKr25TQ","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"c6c920fd-b9f6-4015-8ede-a072d5ad22c5","execution_status":"success"}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJjMzM1MWEwMi0wYmMyLTQ0NDktYmVlZC1kNTlkN2FjOTM3ZDAiLCJncm91cF9ydW5faWQiOiI0NzI5NTEyMS02YTIzLTQ2MGYtODY1Yy02ZTY0NWM0ZjAyMzEiLCJncm91cF9pZCI6ImM5MTgwM2M0LTYzYzQtNGJiZS05M2NhLTcyMmJlZjg4MzNmYyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJjNmM5MjBmZC1iOWY2LTQwMTUtOGVkZS1hMDcyZDVhZDIyYzUiXSwianRpIjoiZDc5NGIxOGQtMThhNC00NDM0LTg1NTEtNmFkNGZkNTA3YzU0IiwiaWF0IjoxNzc0NDcwOTAyLCJleHAiOjE3NzQ1NTczMDJ9.zmYXn77lQT1yGAfT-mF1SBE-klvk7PPFnUvYaKr25TQ","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"c6c920fd-b9f6-4015-8ede-a072d5ad22c5","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}]}'
SUMMARY_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJjMzM1MWEwMi0wYmMyLTQ0NDktYmVlZC1kNTlkN2FjOTM3ZDAiLCJncm91cF9ydW5faWQiOiI0NzI5NTEyMS02YTIzLTQ2MGYtODY1Yy02ZTY0NWM0ZjAyMzEiLCJncm91cF9pZCI6ImM5MTgwM2M0LTYzYzQtNGJiZS05M2NhLTcyMmJlZjg4MzNmYyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJjNmM5MjBmZC1iOWY2LTQwMTUtOGVkZS1hMDcyZDVhZDIyYzUiXSwianRpIjoiZDc5NGIxOGQtMThhNC00NDM0LTg1NTEtNmFkNGZkNTA3YzU0IiwiaWF0IjoxNzc0NDcwOTAyLCJleHAiOjE3NzQ1NTczMDJ9.zmYXn77lQT1yGAfT-mF1SBE-klvk7PPFnUvYaKr25TQ","event":"finished","reporting_source":"bundle_callback","action_results":[],"shared_execution_results":[]}'
REPLAY_DIR="./.bundle-callback-replay"
RUNNER="./run_actions.sh"
SUMMARY_FILE="./.bundle-execution-summary.json"
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

build_finished_payload() {
  local exit_code="$1"
  local finished_at="$2"
  python3 - "$SUMMARY_TEMPLATE" "$SUMMARY_FILE" "$finished_at" "$FINISHED_SUCCESS_TEMPLATE" "$FINISHED_FAILED_TEMPLATE" "$exit_code" <<'PY'
import json
import sys
from pathlib import Path

summary_template = json.loads(sys.argv[1])
summary_path = Path(sys.argv[2])
finished_at = sys.argv[3]
success_fallback = json.loads(sys.argv[4])
failed_fallback = json.loads(sys.argv[5])
exit_code = int(sys.argv[6])

payload = dict(summary_template)
payload["finished_at"] = finished_at
if summary_path.is_file():
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        summary = None
    if isinstance(summary, dict):
        action_results = summary.get("action_results")
        shared_execution_results = summary.get("shared_execution_results")
        if isinstance(action_results, list):
            payload["action_results"] = action_results
        if isinstance(shared_execution_results, list) and shared_execution_results:
            payload["shared_execution_results"] = shared_execution_results
        print(json.dumps(payload, separators=(",", ":")))
        sys.exit(0)

fallback = success_fallback if exit_code == 0 else failed_fallback
fallback["finished_at"] = finished_at
print(json.dumps(fallback, separators=(",", ":")))
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
  payload="$(build_finished_payload "$exit_code" "$finished_at")"
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
