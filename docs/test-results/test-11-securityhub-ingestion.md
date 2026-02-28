---
Test 11 — Security Hub ingestion against vulnerable test architecture
Run date: 2026-02-28
Status: FAIL

ENVIRONMENT VALUES
BACKEND_API_URL=https://api.valensjewelry.com
ADMIN_TOKEN_SOURCE=docs/test-results/test-01-api-health.md
CONNECTED_ACCOUNT_ID=029037611564

GROUP B RESOURCE NAMES (from docs/prod-readiness/07-architecture-design.md)
arch1_sg_app_b2
arch1_bucket_evidence_b1
arch1_bucket_policy_evidence_b1
arch1_bucket_pab_evidence_b1
arch2_mixed_policy_role_b3

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 11.1 Trigger ingest | HTTP `200` or `202` | `POST /api/aws/accounts/029037611564/ingest` -> HTTP `202`; `jobs_queued=1` | PASS |
| 11.2 Poll until ingest completes (max 10 min) | Terminal status (`complete`/`done`/`success`) within loop window | First poll returned HTTP `200` with `status=completed`, `progress=100`, `updated_findings_count=3199` | PASS (status wording drift) |
| 11.3 Findings exist after ingest | count `> 0` | `GET /api/findings?account_id=029037611564` + `jq '.total // length'` -> `391` | PASS |
| 11.4 Group B resources have zero findings tagged `TestGroup=negative` | count `0` | As-provided jq (`[.[] | select(.resource_tags.TestGroup == "negative")]`) fails because findings API returns paginated object shape. Compatibility query (`[.items[] | select(.resource_tags.TestGroup == "negative")]`) returns `0`, but `resource_tags` is absent on findings (`0/391` have this field), so strict tag-based validation is not actually verifiable. | FAIL |
| 11.5 Group A resources have findings tagged `TestGroup=detection` | count `> 0` | As-provided jq fails for same response-shape reason. Compatibility query returns `0` and `resource_tags` is absent. Resource-name fallback against architecture names found Group A findings by `resource_id` (`18`) but not via `TestGroup=detection` tags. | FAIL |
| 11.6 Findings have required fields | includes `id`, `severity`, (`title` or `description`), (`resource_id` or `resource_name`), `account_id`, `status` | As-provided jq (`.[0] // .items[0] | keys`) fails on paginated object shape. Compatibility key check confirms `id`, `title`, `description`, `resource_id`, `account_id`, `status`, but no `severity` field (uses `severity_label`/`severity_normalized`). | FAIL |

Failed tests:
* 11.4 Group B tag-based validation (response-shape mismatch + missing `resource_tags` field)
* 11.5 Group A tag-based validation (response-shape mismatch + no `TestGroup=detection` tags)
* 11.6 Required fields validation (missing `severity`; command shape mismatch)

Blocking for go-live: yes
Notes:
* Requested source file `docs/test-results/test-01-environment.md` does not exist in repository state; fallback used `docs/test-results/test-01-api-health.md`.
* `docs/test-results/test-07-account-connection.md` stores `CONNECTED_ACCOUNT_ID` as DB row UUID; ingest/readiness routes require 12-digit AWS account ID path parameter (`029037611564`).
* `/api/findings` currently returns `{ "items": [...], "total": N }`; test commands that assume top-level array (`.[]` / `.[0]`) fail unless adapted to `.items[]`.
* Group-resource fallback (non-tag heuristic across all 391 findings):
  * Group A resource-name matches: `18`
  * Group B resource-name matches: `13`
---
