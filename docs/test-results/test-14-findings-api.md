---
Test 14 — Findings API contract validation
Run date: 2026-02-28
Status: FAIL

ENVIRONMENT VALUES
BACKEND_API_URL=https://api.valensjewelry.com
ADMIN_TOKEN_SOURCE=docs/test-results/test-01-api-health.md

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 14.1 Findings list returns correctly shaped response | array or paginated object with `items` array | `GET /api/findings?limit=5` returned object `{ items: [...], total: 391 }` with `items` array | PASS |
| 14.2 Each finding has required fields | `id`, `severity`, `title`, `description`, `resource_id`, `account_id`, `status`, `source`, `created_at` all present and non-null | As-provided jq chain failed because response is paginated object (`jq` attempted `.[0]`). Compatibility check on `.items[0]` showed `severity=null` and `severity_label="INFORMATIONAL"` | FAIL |
| 14.3 Severity values are valid | only `CRITICAL/HIGH/MEDIUM/LOW/INFORMATIONAL` or numeric equivalents | As-provided jq failed due expression/shape mismatch. Compatibility checks showed `severity_label` unique values: `["INFORMATIONAL"]`; `severity_normalized` unique values: `[0]` | FAIL (strict command contract) |
| 14.4 No raw internal IDs exposed as display values | human-readable string, not UUID | As-provided jq failed because response is paginated object (`.[0].title`). Compatibility check on `.items[0].title` returned human-readable title; UUID check=false | FAIL (strict command contract) |
| 14.5 Single finding detail endpoint works | `200` with full finding detail | As-provided `FINDING_ID` extraction failed (`jq` shape mismatch on `.[0].id`). Compatibility extraction (`.items[0].id`) returned `16c83cc5-4c33-4f8b-ab10-4508aa3c77c5`; `GET /api/findings/{id}` returned HTTP `200` with full detail payload | FAIL (strict command contract) |
| 14.6 Grouped findings endpoint works | `200` with grouped structure | `GET /api/findings/grouped` returned HTTP `200` with `{ items: [...], total: 33 }` grouped payload | PASS |
| 14.7 Total count is consistent | non-zero positive number | `jq '.total // length'` returned `391` | PASS |

Failed tests:
* 14.2 Required field contract (`severity` missing; runtime uses `severity_label`/`severity_normalized`) and strict jq shape mismatch.
* 14.3 Strict jq command failed on current findings response shape/field contract.
* 14.4 Strict jq command failed on current findings response shape.
* 14.5 Strict `FINDING_ID` jq extraction failed on current findings response shape (detail endpoint itself is healthy when ID is extracted from `.items[0].id`).

Blocking for go-live: yes
Notes:
* Requested source file `docs/test-results/test-01-environment.md` does not exist in repository state. Fallback source used: `docs/test-results/test-01-api-health.md`.
* Current findings-list API contract is paginated object (`items`, `total`). Test commands that index top-level array (`.[0]`, `.[]`) fail unless adapted to `.items[0]` / `.items[]`.
* Findings payload does not expose a literal `severity` key; it exposes `severity_label` and `severity_normalized`.
---
