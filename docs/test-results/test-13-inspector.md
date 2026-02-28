---
Test 13 — Inspector Ingestion Validation
Run date: 2026-02-28
Status: FAIL

ENVIRONMENT VALUES
BACKEND_API_URL=https://api.valensjewelry.com
ADMIN_TOKEN_SOURCE=docs/test-results/test-01-api-health.md
CONNECTED_ACCOUNT_ID=029037611564

SOURCE FILES REQUESTED BY TEST PLAN
- docs/test-results/test-01-environment.md (missing in repo)
- docs/test-results/test-07-account-connection.md (present and read)

SOURCE FILES USED
- docs/test-results/test-01-api-health.md
- docs/test-results/test-07-account-connection.md

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 13.1 Trigger Inspector ingest | HTTP `200` or `202` | `POST /api/aws/accounts/029037611564/ingest-inspector` -> HTTP `202`; body: `{\"account_id\":\"029037611564\",\"jobs_queued\":1,\"regions\":[\"eu-north-1\"],\"message\":\"Inspector ingestion jobs queued successfully\"}` | PASS |
| 13.2 Job completes or gracefully skips | No unhandled exception message | After `sleep 60`, second `POST /api/aws/accounts/029037611564/ingest-inspector` returned normal queue response JSON with no unhandled exception text | PASS |
| 13.3 Source field distinguishes Inspector findings | Command returns a numeric count (0 acceptable) | As-provided command `jq '[.[] | select(.source == \"inspector\")] | length'` failed on current payload shape: `jq: error ... Cannot index array with string \"source\"` | FAIL |

Diagnostic (schema-aware) check for 13.3:
- `GET /api/findings` currently returns object shape `{ \"items\": [...], \"total\": ... }` (not top-level array).
- Using `jq '[.items[] | select(.source == \"inspector\")] | length'` returned `0`.

Failed tests:
* 13.3 Source field distinguishes Inspector findings (command/query shape mismatch with paginated findings response)

Blocking for go-live: yes
Notes:
* `docs/test-results/test-01-environment.md` is still missing; this run reused values from `docs/test-results/test-01-api-health.md`.
* `docs/test-results/test-07-account-connection.md` stores `CONNECTED_ACCOUNT_ID` as DB row UUID, but this endpoint requires 12-digit AWS `account_id`; this run used `029037611564` from live `/api/aws/accounts`.
---
