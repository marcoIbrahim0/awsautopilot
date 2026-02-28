---
Test 08 — Service Readiness Endpoints
Run date: 2026-02-28
Status: FAIL

ENVIRONMENT VALUES
BACKEND_API_URL=https://api.valensjewelry.com
TEST_EMAIL=maromaher54@gmail.com
CONNECTED_ACCOUNT_ID=029037611564
ADMIN_TOKEN_SOURCE=fresh runtime login via POST /api/auth/login

SOURCE FILES REQUESTED BY TEST PLAN
- docs/test-results/test-01-environment.md (missing in repo)
- docs/test-results/test-07-account-connection.md (present and read)

SOURCE FILES USED
- docs/test-results/test-01-api-health.md
- docs/test-results/test-06-auth-tokens.md
- docs/test-results/test-07-account-connection.md

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 8.1 Service readiness endpoint responds | `200` with per-service status fields | `POST /api/aws/accounts/029037611564/service-readiness` -> HTTP `200`; response includes per-region service booleans and errors (`security_hub_enabled`, `aws_config_enabled`, `access_analyzer_enabled`, `inspector_enabled`) | PASS |
| 8.2 Response contains expected service fields | Response contains at minimum `security_hub`, `config`, `access_analyzer`, `inspector` fields | Top-level keys are `account_id`, `overall_ready`, `all_security_hub_enabled`, `all_aws_config_enabled`, `all_access_analyzer_enabled`, `all_inspector_enabled`, missing/multi-region arrays, `regions`; exact expected field names are not present as-is | FAIL |
| 8.3 Control plane readiness endpoint responds | `200` with `overall_ready` | `GET /api/aws/accounts/029037611564/control-plane-readiness` -> HTTP `200`; includes `overall_ready=false`, `missing_regions=["eu-north-1"]`, region freshness details | PASS |
| 8.4 Ingest progress endpoint responds | HTTP `200` (not `404`) | `GET /api/aws/accounts/029037611564/ingest-progress` -> HTTP `422` with validation error: missing required query param `started_after` | FAIL |
| 8.5 Fast path endpoint responds | HTTP `200` or `202` (not `404`) | `POST /api/aws/accounts/029037611564/onboarding-fast-path` -> HTTP `200` | PASS |
| 8.6 Account ping endpoint responds | HTTP `200` | `GET /api/aws/accounts/ping` -> HTTP `200`, body `{"status":"ok"}` | PASS |

Readiness response snapshot (8.1):
- `overall_ready=true`
- `all_security_hub_enabled=true`
- `all_aws_config_enabled=true`
- `all_access_analyzer_enabled=false`
- `all_inspector_enabled=true`
- `missing_access_analyzer_regions=["eu-north-1"]`
- `regions[0].access_analyzer_error="No active Access Analyzer analyzer found."`

Failed tests:
* 8.2 Response contains expected service fields (exact expected field names not present)
* 8.4 Ingest progress endpoint responds (request shape changed: `started_after` now required)

Blocking for go-live: yes
Notes:
- The service-readiness endpoint is functionally returning meaningful per-region status and error context.
- `test-07-account-connection.md` currently records `CONNECTED_ACCOUNT_ID=cdc6355d-2f56-4f19-b8de-a200ed521c07` (DB row UUID), but these Test 08 endpoints validate `account_id` with pattern `^\\d{12}$`; this suite used `account_id=029037611564`.
- Diagnostic verification for ingest progress: adding `started_after` returns HTTP `200` with valid progress payload, confirming endpoint exists but contract now requires a query parameter.
