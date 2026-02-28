---
Test 12 — Access Analyzer Ingestion Validation
Run date: 2026-02-28
Status: FAIL

ENVIRONMENT VALUES
BACKEND_API_URL=https://api.valensjewelry.com
ADMIN_TOKEN_SOURCE=fresh login via credentials from docs/test-results/test-01-api-health.md
CONNECTED_ACCOUNT_ID=029037611564
CONNECTED_ACCOUNT_ROW_ID=851580aa-460c-4c44-8763-b4b6574229a3

SOURCE FILES REQUESTED BY TEST PLAN
- docs/test-results/test-01-environment.md (missing in repo)
- docs/test-results/test-07-account-connection.md (present and read)

SOURCE FILES USED
- docs/test-results/test-01-api-health.md
- docs/test-results/test-07-account-connection.md

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 12.1 Trigger Access Analyzer ingest | HTTP `200` or `202` | `POST /api/aws/accounts/029037611564/ingest-access-analyzer` -> HTTP `202` | PASS |
| 12.2 Job completes or gracefully skips | No error state; complete or clean skip if AA not configured | As-provided request `GET /api/aws/accounts/029037611564/ingest-progress` returned validation error: `{"detail":[{"type":"missing","loc":["query","started_after"],"msg":"Field required","input":null}]}` | FAIL |
| 12.3 No 500 errors in response | No `.error` field with 500-class content | `POST /api/aws/accounts/029037611564/ingest-access-analyzer` body: `{"account_id":"029037611564","jobs_queued":1,"regions":["eu-north-1"],"message_ids":["ee65a21c-bc55-41b4-a1bd-d6961dd748d4"],"message":"Access Analyzer ingestion jobs queued successfully"}`; jq check -> `OK` | PASS |
| 12.4 Source field distinguishes AA findings | Command returns numeric count (0 acceptable) | As-provided command `jq '[.[] | select(.source == "access_analyzer")] | length'` failed on current findings payload shape: `jq: error ... Cannot index array with string "source"` | FAIL |

Diagnostic checks:
- `GET /api/aws/accounts/029037611564/ingest-progress?started_after=1970-01-01T00:00:00Z` returned `{"status":"completed","progress":100,"updated_findings_count":3199,...}`.
- `GET /api/findings` currently returns object shape `{ "items": [...], "total": ... }` (not top-level array).
- Schema-aware count `jq '[.items[] | select(.source == "access_analyzer")] | length'` returned `0`.

Failed tests:
* 12.2 Job completes or gracefully skips (request-contract mismatch: `started_after` is required by API)
* 12.4 Source field distinguishes AA findings (provided jq assumes array response; API returns paginated object)

Blocking for go-live: yes
Notes:
* `docs/test-results/test-01-environment.md` is still missing; this run reused Test 01 API health values and performed a fresh login for `ADMIN_TOKEN`.
* `docs/test-results/test-07-account-connection.md` stores `CONNECTED_ACCOUNT_ID` as DB row UUID, but this endpoint family requires 12-digit AWS `account_id`; this run used live `account_id=029037611564`.
---
