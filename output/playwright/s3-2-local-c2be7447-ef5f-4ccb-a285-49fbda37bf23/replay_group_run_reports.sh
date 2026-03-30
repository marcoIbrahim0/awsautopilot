#!/usr/bin/env bash
set -euo pipefail

REPORT_URL=http://localhost:8000/api/internal/group-runs/report
REPLAY_DIR="./.bundle-callback-replay"

if [ ! -d "$REPLAY_DIR" ]; then
  echo "Replay directory not found: $REPLAY_DIR"
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for replay."
  exit 1
fi

shopt -s nullglob
files=("$REPLAY_DIR"/*.json)
if [ "${#files[@]}" -eq 0 ]; then
  echo "No replay payloads found under $REPLAY_DIR."
  exit 0
fi

for payload_file in "${files[@]}"; do
  response_file=$(mktemp)
  http_code=$(curl -sS     --connect-timeout 5     --max-time 20     --retry 4     --retry-delay 2     --retry-all-errors     -o "$response_file"     -w "%{http_code}"     -X POST "$REPORT_URL"     -H "Content-Type: application/json"     --data-binary "@$payload_file")
  rc=$?
  response_body="$(cat "$response_file" 2>/dev/null || true)"
  rm -f "$response_file"
  if [ "$rc" -ne 0 ]; then
    echo "Replay failed for $payload_file"
    exit "$rc"
  fi
  case "$http_code" in
    2??)
      echo "Replayed $payload_file"
      rm -f "$payload_file"
      ;;
    409)
      if printf '%s' "$response_body" | grep -q 'group_run_report_replay'; then
        echo "Replay already consumed for $payload_file"
        rm -f "$payload_file"
      else
        echo "Replay conflict for $payload_file"
        exit 1
      fi
      ;;
    *)
      echo "Replay rejected for $payload_file with HTTP $http_code"
      printf '%s\n' "$response_body"
      exit 1
      ;;
  esac
done
