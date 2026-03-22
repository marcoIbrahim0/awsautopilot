#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ID="${1:-$(date -u +"%Y%m%dT%H%M%SZ")}" 
FRONTEND_URL="${FRONTEND_URL:-https://ocypheris.com}"
BACKEND_URL="${BACKEND_URL:-https://api.ocypheris.com}"
TRACKER_REL="docs/live-e2e-testing/00-BASE-ISSUE-TRACKER.md"
RUN_DIR="$ROOT_DIR/docs/test-results/live-runs/$RUN_ID"

if [[ -e "$RUN_DIR" ]]; then
  echo "Run directory already exists: $RUN_DIR" >&2
  exit 1
fi

wave_for_test() {
  local t="$1"
  if (( t == 1 )); then
    echo "01"
  elif (( t >= 2 && t <= 4 )); then
    echo "02"
  elif (( t >= 5 && t <= 8 )); then
    echo "03"
  elif (( t >= 9 && t <= 12 )); then
    echo "04"
  elif (( t >= 13 && t <= 16 )); then
    echo "05"
  elif (( t >= 17 && t <= 22 )); then
    echo "06"
  elif (( t >= 23 && t <= 28 )); then
    echo "07"
  elif (( t >= 29 && t <= 33 )); then
    echo "08"
  else
    echo "09"
  fi
}

focus_for_test() {
  local t="$1"
  case "$t" in
    1) echo "Platform/API health and baseline connectivity" ;;
    2) echo "Signup flow and initial tenant creation contract" ;;
    3) echo "Login/session lifecycle, refresh, and logout invalidation" ;;
    4) echo "Password management and forgot-password behavior" ;;
    5) echo "Environment/setup and prerequisite validation" ;;
    6) echo "Auth/onboarding token and readiness contract checks" ;;
    7) echo "AWS account connection and duplicate behavior" ;;
    8) echo "Invite and service-readiness related endpoint behavior" ;;
    9) echo "Tenant isolation across findings/accounts/resources" ;;
    10) echo "RBAC boundaries for protected operations" ;;
    11) echo "Findings filtering correctness and pagination stability" ;;
    12) echo "Cross-tenant access and ingestion trigger isolation" ;;
    13) echo "Action/finding detail content completeness" ;;
    14) echo "Findings API contracts and duplicate-run guard behavior" ;;
    15) echo "Run progress and findings filter contract behavior" ;;
    16) echo "Action detail/options/preview and recompute endpoint behavior" ;;
    17) echo "Grouped PR bundle creation endpoints and execution flow" ;;
    18) echo "PR bundle download auth and artifact correctness" ;;
    19) echo "Slack/digest settings and webhook security validation" ;;
    20) echo "Internal scheduler endpoint auth and secret-guard behavior" ;;
    21) echo "Export creation-to-download contract (download_url population)" ;;
    22) echo "Baseline report generation, viewer endpoint, and throttling" ;;
    23) echo "Adversarial S3 blast-radius validation" ;;
    24) echo "Adversarial SG dependency-chain validation" ;;
    25) echo "Adversarial IAM multi-principal validation" ;;
    26) echo "Adversarial complex S3 policy preservation checks" ;;
    27) echo "Adversarial mixed SG rule preservation checks" ;;
    28) echo "Adversarial IAM inline+managed policy preservation checks" ;;
    29) echo "Ingest sync and account freshness field validation" ;;
    30) echo "Login rate-limit and Retry-After contract checks" ;;
    31) echo "Non-admin invite/delete authorization boundaries" ;;
    32) echo "Audit-log access controls and secret leakage checks" ;;
    33) echo "PR proof artifact completeness (C2/C5 evidence fields)" ;;
    34) echo "Full regression pass on previously failed/blocking tests" ;;
    35) echo "Final go-live blocker closure and tracker gate sweep" ;;
    *) echo "Live SaaS behavior validation" ;;
  esac
}

tracker_hint_for_test() {
  local t="$1"
  case "$t" in
    1) echo "Section 7 (environment) and Quick Status Board" ;;
    2) echo "Section 2 (frontend wiring)" ;;
    3) echo "Section 1 and Section 4" ;;
    4) echo "Section 1, Section 4, and Section 6" ;;
    5) echo "Section 7" ;;
    6) echo "Section 2 and Section 6" ;;
    7) echo "Section 7 and Section 4" ;;
    8) echo "Section 3 and Section 4" ;;
    9) echo "Section 2 and Section 3" ;;
    10) echo "Section 2 and Section 3" ;;
    11) echo "Section 4" ;;
    12) echo "Section 3" ;;
    13) echo "Section 2" ;;
    14) echo "Section 4" ;;
    15) echo "Section 2" ;;
    16) echo "Section 1 and Section 4" ;;
    17) echo "Section 1 and Section 4" ;;
    18) echo "Section 3 and Section 4" ;;
    19) echo "Section 1 and Section 3" ;;
    20) echo "Section 1 and Section 4" ;;
    21) echo "Section 6" ;;
    22) echo "Section 1, Section 2, Section 4, and Section 6" ;;
    23|24|25|26|27|28) echo "Section 5" ;;
    29) echo "Section 1 and Section 2" ;;
    30) echo "Section 3 and Section 7" ;;
    31) echo "Section 3" ;;
    32) echo "Section 1 and Section 3" ;;
    33) echo "Section 4" ;;
    34|35) echo "Section 8 and Section 9" ;;
    *) echo "Section TBD" ;;
  esac
}

mkdir -p \
  "$RUN_DIR/evidence/api" \
  "$RUN_DIR/evidence/ui" \
  "$RUN_DIR/evidence/screenshots" \
  "$RUN_DIR/notes"

for wave in 01 02 03 04 05 06 07 08 09; do
  mkdir -p "$RUN_DIR/wave-$wave"
done

if [[ -f "$ROOT_DIR/$TRACKER_REL" ]]; then
  cp "$ROOT_DIR/$TRACKER_REL" "$RUN_DIR/00-base-issue-tracker-snapshot.md"
fi

cat > "$RUN_DIR/00-run-metadata.md" <<METADATA
# Live E2E Run Metadata

- Run ID: \
  $RUN_ID
- Created at (UTC): \
  $(date -u +"%Y-%m-%dT%H:%M:%SZ")
- Frontend URL: \
  $FRONTEND_URL
- Backend URL: \
  $BACKEND_URL
- Source tracker: \
  $TRACKER_REL

## Required Identities

- Admin user (primary tenant)
- Member user (same tenant)
- Separate user in second tenant

## Required AWS States

- One account connected for normal flows
- One account/state for adversarial tests 23-28
METADATA

for t in $(seq 1 35); do
  test_id=$(printf "%02d" "$t")
  wave_id=$(wave_for_test "$t")
  focus=$(focus_for_test "$t")
  tracker_hint=$(tracker_hint_for_test "$t")
  out_file="$RUN_DIR/wave-$wave_id/test-$test_id.md"

  cat > "$out_file" <<TESTFILE
# Test $test_id

- Wave: $wave_id
- Focus: $focus
- Status: PASS | FAIL | PARTIAL | BLOCKED
- Severity (if issue): 🔴 BLOCKING | 🟠 HIGH | 🟡 MEDIUM | 🔵 LOW

## Preconditions

- Identity:
- Tenant:
- AWS account:
- Region(s):
- Prerequisite IDs/tokens:

## Steps Executed

1.
2.
3.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| | | | |

## Assertions

- Positive path:
- Negative path:
- Auth boundary:
- Contract shape:
- Idempotency/retry:
- Auditability:

## Tracker Updates

- Primary tracker section/row:
- Tracker section hint: $tracker_hint
- Section 8 checkbox impact:
- Section 9 changelog update needed:

## Notes

- 
TESTFILE
done

cat > "$RUN_DIR/README.md" <<README
# Live E2E Run $RUN_ID

This folder contains all evidence and per-test result logs for one full run (Tests 01-35).

## Structure

- \
  00-run-metadata.md
- \
  00-base-issue-tracker-snapshot.md
- \
  wave-01 ... wave-09 with test markdown files
- \
  evidence/api, evidence/ui, evidence/screenshots
- \
  notes/

## Update Rules During Execution

1. Complete each test markdown file immediately after execution.
2. Save raw evidence into evidence folders with timestamped filenames.
3. Apply issue mapping updates in docs/live-e2e-testing/00-BASE-ISSUE-TRACKER.md after each test.
README

echo "Created live E2E run scaffold: $RUN_DIR"
echo "Next step: open $RUN_DIR/00-run-metadata.md and begin with wave-01/test-01.md"
