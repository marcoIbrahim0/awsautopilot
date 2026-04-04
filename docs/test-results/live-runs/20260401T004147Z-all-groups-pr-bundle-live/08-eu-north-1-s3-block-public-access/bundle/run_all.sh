#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI4MjgwMzhhNS1kM2E5LTRjMDItODU3NS1jOTFkOTgxZTQ5NDgiLCJncm91cF9pZCI6IjhiODFjMWE4LWEyYzctNDI1MC1hYWYyLWQ1YWU2MmYwOGRkYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIxOGU0NTliMS0zYmMyLTQ3YjQtYTUyMC1jOTU1ZTkyMWM3NWYiXSwianRpIjoiMzFiZGMwZWUtY2VmYi00YmQ3LThkOWItNDQzMmQ1NDE5YmYyIiwiaWF0IjoxNzc1MDA0MTk2LCJleHAiOjE3NzUwOTA1OTZ9.bOtvhnHIXVeo0H2o0yjG_lFz4gAx4PeAHhiL75edmYM
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI4MjgwMzhhNS1kM2E5LTRjMDItODU3NS1jOTFkOTgxZTQ5NDgiLCJncm91cF9pZCI6IjhiODFjMWE4LWEyYzctNDI1MC1hYWYyLWQ1YWU2MmYwOGRkYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIxOGU0NTliMS0zYmMyLTQ3YjQtYTUyMC1jOTU1ZTkyMWM3NWYiXSwianRpIjoiMzFiZGMwZWUtY2VmYi00YmQ3LThkOWItNDQzMmQ1NDE5YmYyIiwiaWF0IjoxNzc1MDA0MTk2LCJleHAiOjE3NzUwOTA1OTZ9.bOtvhnHIXVeo0H2o0yjG_lFz4gAx4PeAHhiL75edmYM","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI4MjgwMzhhNS1kM2E5LTRjMDItODU3NS1jOTFkOTgxZTQ5NDgiLCJncm91cF9pZCI6IjhiODFjMWE4LWEyYzctNDI1MC1hYWYyLWQ1YWU2MmYwOGRkYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIxOGU0NTliMS0zYmMyLTQ3YjQtYTUyMC1jOTU1ZTkyMWM3NWYiXSwianRpIjoiMzFiZGMwZWUtY2VmYi00YmQ3LThkOWItNDQzMmQ1NDE5YmYyIiwiaWF0IjoxNzc1MDA0MTk2LCJleHAiOjE3NzUwOTA1OTZ9.bOtvhnHIXVeo0H2o0yjG_lFz4gAx4PeAHhiL75edmYM","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"18e459b1-3bc2-47b4-a520-c955e921c75f","execution_status":"success"}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI4MjgwMzhhNS1kM2E5LTRjMDItODU3NS1jOTFkOTgxZTQ5NDgiLCJncm91cF9pZCI6IjhiODFjMWE4LWEyYzctNDI1MC1hYWYyLWQ1YWU2MmYwOGRkYSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIxOGU0NTliMS0zYmMyLTQ3YjQtYTUyMC1jOTU1ZTkyMWM3NWYiXSwianRpIjoiMzFiZGMwZWUtY2VmYi00YmQ3LThkOWItNDQzMmQ1NDE5YmYyIiwiaWF0IjoxNzc1MDA0MTk2LCJleHAiOjE3NzUwOTA1OTZ9.bOtvhnHIXVeo0H2o0yjG_lFz4gAx4PeAHhiL75edmYM","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"18e459b1-3bc2-47b4-a520-c955e921c75f","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}]}'
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
