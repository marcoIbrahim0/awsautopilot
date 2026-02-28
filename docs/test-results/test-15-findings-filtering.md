---
Test 15 — Findings Filtering and Pagination Validation
Run date: 2026-02-28
Status: FAIL

ENVIRONMENT VALUES
BACKEND_API_URL=https://api.valensjewelry.com
ADMIN_TOKEN_SOURCE=docs/test-results/test-01-api-health.md
CONNECTED_ACCOUNT_ID=cdc6355d-2f56-4f19-b8de-a200ed521c07

SOURCE FILES REQUESTED BY TEST PLAN
- docs/test-results/test-01-environment.md (missing in repo)
- docs/test-results/test-07-account-connection.md (present and read)

SOURCE FILES USED
- docs/test-results/test-01-api-health.md
- docs/test-results/test-07-account-connection.md

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 15.1 Filter by severity CRITICAL | Only `CRITICAL` in results | HTTP `200`; as-provided command failed: `jq: error ... Cannot index array with string "severity"` | FAIL |
| 15.2 Filter by account_id | First result `account_id` matches `CONNECTED_ACCOUNT_ID` | HTTP `200`; response `{ "items": [], "total": 0 }`; as-provided jq failed (`Cannot index object with number`) and no matching findings returned | FAIL |
| 15.3 Filter by status open | Number returned, no `400` error | HTTP `200`; `Open findings: 0` | PASS |
| 15.4 Pagination works | Different first IDs between page 1 and page 2 | HTTP `200` on both calls; as-provided jq returned errors on both pages (`Cannot index object with number`) so ID comparison could not run | FAIL |
| 15.5 Invalid filter returns 400 not 500 | HTTP `400` or `422` (not `500`) | `Invalid filter HTTP: 200` | FAIL |
| 15.6 Grouped by resource works | Positive number | HTTP `200`; as-provided command output `2` | PASS |
| 15.7 Combined filters work | HTTP `200`, valid JSON | HTTP `200`; as-provided `jq 'length'` output `2` | PASS |

Diagnostics:
- Current `/api/findings` response is paginated object shape (`items`, `total`), not top-level array; this caused jq failures in 15.1, 15.2, and 15.4 with the exact command forms.
- 15.1 compatibility check: `jq '[.items[].severity_label] | unique'` returned `["CRITICAL"]`.
- 15.4 compatibility check:
  - Page 1 first id: `16c83cc5-4c33-4f8b-ab10-4508aa3c77c5`
  - Page 2 first id: `12863225-4d28-4c2c-b091-155e4ba43746`
  - IDs are different (pagination behavior appears correct under object-shape query).
- 15.6 compatibility check: `.items | length` returned `33` grouped rows.

Failed tests:
* 15.1 Filter by severity CRITICAL (as-provided jq incompatible with response shape/field naming)
* 15.2 Filter by account_id (no results with provided `CONNECTED_ACCOUNT_ID` value; as-provided jq incompatible with response shape)
* 15.4 Pagination works (as-provided jq incompatible with response shape)
* 15.5 Invalid filter returns 400 not 500 (got `200`, expected `400/422`)

Blocking for go-live: yes
Notes:
* `CONNECTED_ACCOUNT_ID` in `test-07-account-connection.md` is a DB row UUID; findings `account_id` values are 12-digit AWS account IDs (for example `029037611564`), which explains the zero-result outcome in 15.2.
* `severity` filter currently accepts invalid enum value `INVALID_VALUE` and returns HTTP `200` with empty result set instead of validation error.
---
