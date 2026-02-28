# Test 05

- Wave: 03
- Focus: Deployment prerequisites, frontend reachability, and account-list auth boundary
- Status: PASS
- Severity (if issue): ⚪ SKIP/NA

## Preconditions

- Identity: Existing admin test user `maromaher54@gmail.com`
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens: Admin bearer token acquired via `POST /api/auth/login`; deployment prerequisite labels verified from `docs/prod-readiness/08-deployment-report.md`

## Steps Executed

1. Logged in as admin to capture current tenant/account context and bearer token for authenticated checks.
2. Verified backend and frontend public reachability (`/health` and frontend root `/`).
3. Verified account listing with auth and auth-boundary behavior without auth.
4. Rechecked deployment report prerequisite labels (`TEST_ACCOUNT_ID`, `READ_ROLE_ARN`, `WRITE_ROLE_ARN`) and captured UI note artifact.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Login returned auth contract with `access_token`, `user.role=admin`, tenant `Valens`, `saas_account_id=029037611564` | 2026-02-28T21:43:59Z | `evidence/api/test-05-rerun-20260228T214336Z-login-admin.status`, `evidence/api/test-05-rerun-20260228T214336Z-login-admin.json`, `evidence/api/test-05-rerun-20260228T214336Z-login-admin.request.txt` |
| 2 | GET | `https://api.valensjewelry.com/health` | None | `200` | Health probe returned `{"status":"ok","app":"AWS Security Autopilot"}` | 2026-02-28T21:44:00Z | `evidence/api/test-05-rerun-20260228T214336Z-backend-health.status`, `evidence/api/test-05-rerun-20260228T214336Z-backend-health.json`, `evidence/api/test-05-rerun-20260228T214336Z-backend-health.request.txt` |
| 3 | GET | `https://dev.valensjewelry.com/` | None | `200` | Frontend root served app HTML successfully | 2026-02-28T21:44:01Z | `evidence/api/test-05-rerun-20260228T214336Z-frontend-root.status`, `evidence/api/test-05-rerun-20260228T214336Z-frontend-root.html`, `evidence/api/test-05-rerun-20260228T214336Z-frontend-root.request.txt` |
| 4 | GET | `https://api.valensjewelry.com/api/aws/accounts` | `Authorization: Bearer <admin_token>` | `200` | Account list returned connected account `029037611564` with read/write role ARNs and regions | 2026-02-28T21:44:00Z | `evidence/api/test-05-rerun-20260228T214336Z-accounts-auth.status`, `evidence/api/test-05-rerun-20260228T214336Z-accounts-auth.json`, `evidence/api/test-05-rerun-20260228T214336Z-accounts-auth.request.txt` |
| 5 | GET | `https://api.valensjewelry.com/api/aws/accounts` | No auth header | `401` | Unauthenticated request rejected (`Authentication required or tenant_id must be provided`) | 2026-02-28T21:44:00Z | `evidence/api/test-05-rerun-20260228T214336Z-accounts-no-auth.status`, `evidence/api/test-05-rerun-20260228T214336Z-accounts-no-auth.json`, `evidence/api/test-05-rerun-20260228T214336Z-accounts-no-auth.request.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| Frontend root load | App root reachable over HTTPS | Observed HTTP `200` and rendered app HTML | `evidence/screenshots/test-05-rerun-20260228T214336Z-frontend-root.png` |
| Deployment report prerequisite labels | `TEST_ACCOUNT_ID`, `READ_ROLE_ARN`, `WRITE_ROLE_ARN` explicitly present in deployment report | All three labels found with concrete values in `08-deployment-report.md` | N/A (`evidence/ui/test-05-rerun-20260228T214336Z-prereq-doc-check.txt`) |

## Assertions

- Positive path: PASS (login, backend health, frontend root, and authenticated account listing all returned expected success status)
- Negative path: PASS (unauthenticated account listing rejected with `401`)
- Auth boundary: PASS (`/api/aws/accounts` did not allow no-auth access)
- Contract shape: PASS (login and accounts payloads include required tenant/account/role fields used by onboarding/account views)
- Idempotency/retry: N/A for this test scope (read-only checks and single login acquisition)
- Auditability: PASS (API, UI notes, and screenshot artifacts are present and traceable)

## Tracker Updates

- Primary tracker section/row: Section 7 row #2 (`08-deployment-report.md` prerequisite labels revalidated)
- Tracker section hint: Section 7
- Section 8 checkbox impact: No direct checkbox change from Test 05
- Section 9 changelog update needed: No additional entry (already recorded in tracker changelog for this fixed row)

## Notes

- Test 05 rerun verifies HTTPS frontend availability and prerequisite documentation labels from observed artifacts only.
- HTTP-to-HTTPS redirect behavior was not rechecked in this rerun artifact set.
