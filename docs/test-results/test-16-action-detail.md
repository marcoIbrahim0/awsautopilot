---
Test 16 — Action List, Detail, and Remediation Endpoints Validation
Run date: 2026-02-28
Status: FAIL

ENVIRONMENT VALUES
BACKEND_API_URL=https://api.valensjewelry.com
ADMIN_TOKEN_SOURCE=fresh login using credentials from docs/test-results/test-01-api-health.md
ACTION_ID_FROM_PROVIDED_COMMAND=jq error (payload shape mismatch)
ACTION_ID_NORMALIZED=9c31f438-1ade-4cc7-91c8-b959870a615b
DIRECT_ACTION_ID=a6e7ec82-3201-440b-9314-6255671439e2
PR_ACTION_ID=9c31f438-1ade-4cc7-91c8-b959870a615b
PR_ACTION_ID_FOR_TEST_20=9c31f438-1ade-4cc7-91c8-b959870a615b

SOURCE FILES REQUESTED BY TEST PLAN
- docs/test-results/test-01-environment.md (missing in repo)

SOURCE FILES USED
- docs/test-results/test-01-api-health.md

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 16.1 Actions list returns data | HTTP `200`, array returned | HTTP `200`; response shape is paginated object `{ \"items\": [...], \"total\": 158 }` with `items` length `5` (not top-level array) | FAIL |
| 16.2 Action has required fields | All fields present | As-provided command `jq '.[0] // .items[0] | {id,action_type,status,title,severity}'` failed: `Cannot index object with number`; schema-aware check shows `severity` is `null` | FAIL |
| 16.3 Action detail endpoint works | HTTP `200` with full action detail | As-provided `ACTION_ID` extraction failed (`Cannot index object with number`), so strict flow could not execute; diagnostic call with normalized `ACTION_ID=9c31f438-1ade-4cc7-91c8-b959870a615b` returned HTTP `200` with full action detail JSON | FAIL |
| 16.4 Remediation options endpoint works | HTTP `200` with options array | Strict flow blocked by failed as-provided `ACTION_ID` extraction; diagnostic call with normalized action ID returned HTTP `200` and `mode_options` payload | FAIL |
| 16.5 Remediation preview endpoint works | HTTP `200`, not `404` | Strict flow blocked by failed as-provided `ACTION_ID` extraction; diagnostic call with normalized action ID returned HTTP `200` | FAIL |
| 16.6 Direct-fix action exists | Non-null ID found | As-provided command failed on response shape: `Cannot index array with string \"action_type\"`; strict action_type filter found no `direct_fix` action type | FAIL |
| 16.7 PR-bundle action exists | Non-null ID found | As-provided command failed on response shape: `Cannot index array with string \"action_type\"`; strict action_type filter found no `pr_bundle`/`pr_only` action types | FAIL |

Compatibility diagnostics (for downstream test execution):
- `/api/actions` currently uses action-specific `action_type` values (for example `enable_guardduty`, `sg_restrict_public_ports`) instead of generic `direct_fix` / `pr_bundle`.
- Remediation mode is exposed in `GET /api/actions/{id}/remediation-options` under `mode_options`.
- Selected compatible IDs:
  - `DIRECT_ACTION_ID=a6e7ec82-3201-440b-9314-6255671439e2` (`action_type=enable_guardduty`, `mode_options=[\"pr_only\",\"direct_fix\"]`)
  - `PR_ACTION_ID=9c31f438-1ade-4cc7-91c8-b959870a615b` (`action_type=sg_restrict_public_ports`, `mode_options=[\"pr_only\"]`)

Failed tests:
* 16.1 Actions list returns data (response is paginated object, not top-level array)
* 16.2 Action has required fields (strict jq failed; `severity` missing/null)
* 16.3 Action detail endpoint works (strict ACTION_ID extraction failed)
* 16.4 Remediation options endpoint works (strict ACTION_ID extraction failed)
* 16.5 Remediation preview endpoint works (strict ACTION_ID extraction failed)
* 16.6 Direct-fix action exists (strict action_type contract mismatch)
* 16.7 PR-bundle action exists (strict action_type contract mismatch)

Blocking for go-live: yes
Notes:
* Requested `docs/test-results/test-01-environment.md` file is not present in this repo state; this run used `docs/test-results/test-01-api-health.md` for deterministic setup fallback.
* For strict reproducibility, test commands 16.2/16.3/16.6/16.7 assume legacy top-level array contract on `/api/actions`; current runtime contract is paginated object (`items`, `total`).
---
