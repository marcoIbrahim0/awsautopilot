# Test 32

- Wave: 08
- Focus: Audit-log access controls and secret leakage checks
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity:
  - Tenant A admin: `maromaher54@gmail.com`
  - Same-tenant member: `wave3acc+20260228T213251Z@example.com`
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Canonical evidence prefix: `test-32-live-20260302T213947Z-*`
- Prerequisite IDs/tokens:
  - Admin actor UUID from `/api/auth/me`: `57e658d9-d5c1-478a-81f8-8cf0400d001e`
  - First-row resource pivot: `resource_type=remediation_run`, `resource_id=b9e50351-02a0-4784-a2f1-473929da696e`

## Steps Executed

1. Logged in as admin and member; validated tenant/user context via `GET /api/auth/me`.
2. Validated admin read access on `GET /api/audit-log` baseline list (`limit=25, offset=0`) and pagination probes (`limit=5, offset=0/5`, plus tail page `offset=25`).
3. Validated admin filters:
   - `actor_user_id=<admin_uuid>`
   - `resource_type=<first_row.resource_type>`
   - `resource_id=<first_row.resource_id>`
   - `from_date=2026-03-01T00:00:00Z&to_date=<run_now>`
4. Ran invalid-filter probe (`actor_user_id=not-a-uuid` -> `400`).
5. Validated access-control boundaries:
   - member token -> `403`
   - no token -> `401` (base and filtered requests)
6. Scanned baseline/date/full datasets for leakage patterns (JWT/access-token/password/role_arn/AWS key/private key/webhook).
7. Ran focused Wave 7 keyword scan (`root|governance|secret_migration|exception|notification`) and leakage check on that subset.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Admin token issued. | 2026-03-02T21:39:47Z | `evidence/api/test-32-live-20260302T213947Z-01-login-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/auth/me` | Bearer admin token | `200` | Admin context confirmed (`user.id=57e658d9-d5c1-478a-81f8-8cf0400d001e`). | 2026-03-02T21:39:48Z | `evidence/api/test-32-live-20260302T213947Z-02-auth-me-admin.*` |
| 3 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"wave3acc+20260228T213251Z@example.com","password":"***REDACTED***"}` | `200` | Member token issued. | 2026-03-02T21:39:48Z | `evidence/api/test-32-live-20260302T213947Z-03-login-member.*` |
| 4 | GET | `https://api.valensjewelry.com/api/auth/me` | Bearer member token | `200` | Member context confirmed (`role=member`, same tenant). | 2026-03-02T21:39:49Z | `evidence/api/test-32-live-20260302T213947Z-04-auth-me-member.*` |
| 5 | GET | `https://api.valensjewelry.com/api/audit-log?limit=25&offset=0` | Bearer admin token | `200` | Baseline list contract: `total=31`, `items=25`, expected item keys, `payload=null`. | 2026-03-02T21:39:49Z | `evidence/api/test-32-live-20260302T213947Z-05-audit-log-admin-limit25-offset0.*` |
| 6 | GET | `https://api.valensjewelry.com/api/audit-log?limit=5&offset=0` | Bearer admin token | `200` | Pagination page 1 returned 5 rows. | 2026-03-02T21:39:50Z | `evidence/api/test-32-live-20260302T213947Z-06-audit-log-admin-limit5-offset0.*` |
| 7 | GET | `https://api.valensjewelry.com/api/audit-log?limit=5&offset=5` | Bearer admin token | `200` | Pagination page 2 returned 5 rows; overlap with page 1 = `0`. | 2026-03-02T21:39:50Z | `evidence/api/test-32-live-20260302T213947Z-07-audit-log-admin-limit5-offset5.*` |
| 8 | GET | `https://api.valensjewelry.com/api/audit-log?actor_user_id=<admin_uuid>&limit=25&offset=0` | Bearer admin token | `200` | Actor filter succeeded for admin UUID. | 2026-03-02T21:39:50Z | `evidence/api/test-32-live-20260302T213947Z-08-audit-log-admin-filter-actor-user.*` |
| 9 | GET | `https://api.valensjewelry.com/api/audit-log?resource_type=remediation_run&limit=25&offset=0` | Bearer admin token | `200` | Resource-type filter succeeded. | 2026-03-02T21:39:51Z | `evidence/api/test-32-live-20260302T213947Z-09-audit-log-admin-filter-resource-type.*` |
| 10 | GET | `https://api.valensjewelry.com/api/audit-log?resource_id=b9e50351-02a0-4784-a2f1-473929da696e&limit=25&offset=0` | Bearer admin token | `200` | Resource-id filter succeeded with stable row return. | 2026-03-02T21:39:51Z | `evidence/api/test-32-live-20260302T213947Z-10-audit-log-admin-filter-resource-id.*` |
| 11 | GET | `https://api.valensjewelry.com/api/audit-log?from_date=2026-03-01T00:00:00Z&to_date=<run_now>&limit=200&offset=0` | Bearer admin token | `200` | Date-window filter succeeded (`row_count=25`). | 2026-03-02T21:39:52Z | `evidence/api/test-32-live-20260302T213947Z-11-audit-log-admin-filter-date-range.*` |
| 12 | GET | `https://api.valensjewelry.com/api/audit-log?actor_user_id=not-a-uuid&limit=25&offset=0` | Bearer admin token | `400` | Filter validation enforced (`actor_user_id must be a valid UUID`). | 2026-03-02T21:39:52Z | `evidence/api/test-32-live-20260302T213947Z-12-audit-log-admin-invalid-actor-filter.*` |
| 13 | GET | `https://api.valensjewelry.com/api/audit-log?limit=25&offset=0` | Bearer member token | `403` | Non-admin access blocked (`Only tenant admins can view audit logs.`). | 2026-03-02T21:39:52Z | `evidence/api/test-32-live-20260302T213947Z-13-audit-log-member-forbidden.*` |
| 14 | GET | `https://api.valensjewelry.com/api/audit-log?limit=25&offset=0` | No token | `401` | Unauthenticated access blocked (`Not authenticated`). | 2026-03-02T21:39:53Z | `evidence/api/test-32-live-20260302T213947Z-14-audit-log-no-auth.*` |
| 15 | GET | `https://api.valensjewelry.com/api/audit-log?actor_user_id=<admin_uuid>&limit=25&offset=0` | No token | `401` | Unauthenticated filtered request blocked. | 2026-03-02T21:39:53Z | `evidence/api/test-32-live-20260302T213947Z-15-audit-log-no-auth-with-filter.*` |
| 16 | GET | `https://api.valensjewelry.com/api/audit-log?limit=25&offset=25` | Bearer admin token | `200` | Tail page returned 6 rows; full dataset size remained 31. | 2026-03-02T21:39:54Z | `evidence/api/test-32-live-20260302T213947Z-16-audit-log-admin-limit25-offset25.*` |
| 17 | N/A | N/A | Leakage + focused wave-event scans | N/A | No leakage matches in baseline/date/full datasets; focused keyword subset had 0 rows and 0 hits. | 2026-03-02 | `evidence/api/test-32-live-20260302T213947Z-90-summary-contract-security.json`, `...-91-focus-wave7-actions.json`, `...-92-leakage-scan-details.json`, `...-93-full-dataset-leakage-wave7-scan.json`, `...-99-context-summary.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| API-only security/contract test | N/A | No UI-specific assertion required for this test scope. | N/A |

## Assertions

- Positive path: PASS. Admin can read `/api/audit-log` (`200`) with stable list/pagination/filter contract.
- Negative path: PASS. Invalid UUID filter rejected with `400`.
- Auth boundary: PASS. Member blocked with `403`; unauthenticated blocked with `401`.
- Contract shape: PASS. Rows consistently include expected keys and `payload=null`; pagination coherence preserved.
- Leakage check: PASS. Baseline/date/full scans found `0` secret-pattern hits.
- Focused Wave 7 keyword scan: PASS. Focused subset had `0` rows and `0` hits.

## Tracker Updates

- Primary tracker section/row:
  - Section 3 row #11 (`Audit records contain secrets...`) -> ✅ FIXED (revalidated)
  - Section 3 row #12 (`Non-admin user can read audit log`) -> ✅ FIXED (revalidated)
- Section 8 checkbox impact:
  - `T32` remains checked (`[x]`)
- Section 9 changelog impact:
  - Added Wave 8 Test 32 rerun entry with canonical prefix `test-32-live-20260302T213947Z`.

## Notes

- Full-dataset action mix stayed narrow in this tenant (`remediation_run_completed` and `control_plane_token_rotated`), so focused Wave 7 keyword subset remained empty.
- Canonical PASS assertions for this test are based on `test-32-live-20260302T213947Z-*`.
