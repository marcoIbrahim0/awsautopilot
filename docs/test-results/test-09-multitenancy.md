---
Test 09 — Multi-Tenant Isolation
Run date: 2026-02-28
Status: PASS (all tests 9.1-9.5 executed; no cross-tenant 200 responses observed)

ENVIRONMENT VALUES
BACKEND_API_URL=https://api.valensjewelry.com
ADMIN_TOKEN_SOURCE=docs/test-results/test-01-api-health.md
TENANT_B_EMAIL_SOURCE=docs/test-results/test-04-signup.md
TENANT_B_EMAIL=testuser+003422@valensjewelry.com
TENANT_B_PASSWORD_REQUESTED=TestPass123!
TENANT_B_PASSWORD_USED=TestPassword123! (fallback from test-04-signup.md because requested password returned 401)
---

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 9.1 Tenant B cannot see Tenant A findings | Tenant B returns 0 or fewer than Tenant A | Tenant A findings=`391`; Tenant B findings=`0` | PASS |
| 9.2 Tenant B cannot see Tenant A AWS accounts | Tenant B account count is 0 | Tenant B account count=`0` | PASS |
| 9.3 Tenant B cannot access Tenant A action by ID | HTTP `403` or `404`, never `200` | Tenant A action ID `927ff0e3-ac27-49f2-aad1-0d057977f98c` returned HTTP `404` for Tenant B | PASS |
| 9.4 Tenant B cannot access Tenant A remediation run by ID | HTTP `403` or `404`, never `200` | Tenant A run ID `2a5eaf37-6f0a-404d-9a67-a8de9ef08b63` returned HTTP `404` for Tenant B | PASS |
| 9.5 Tenant B cannot access Tenant A export by ID | HTTP `403` or `404`, never `200` | Tenant A export ID `2d4c8b40-1535-4cb3-a06b-3ec7e1369e5d` returned HTTP `404` for Tenant B | PASS |

Critical security blockers:
* None detected in this run (`0` cross-tenant `200` responses).

Notes:
* Requested source file `docs/test-results/test-01-environment.md` was not present; environment values were loaded from `docs/test-results/test-01-api-health.md`.
* Read `docs/test-results/test-07-account-connection.md` for account-connection context; Test 09 setup still used Test 01 + Test 04 values (`BACKEND_API_URL`, `ADMIN_TOKEN`, Tenant B signup email/password).
* Coverage completion step: created one Tenant A remediation run (`POST /api/remediation-runs`) and one Tenant A export (`POST /api/exports`) before executing 9.4 and 9.5.
---
