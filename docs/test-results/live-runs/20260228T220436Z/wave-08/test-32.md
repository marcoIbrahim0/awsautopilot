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
- Canonical evidence prefix: `test-32-live-20260302T193915Z-*`
- Prerequisite IDs/tokens:
  - Admin token captured from `01-login-admin` (`200`)
  - Member token captured from `03-login-member` (`200`)
  - Admin actor UUID from `/api/auth/me`: `57e658d9-d5c1-478a-81f8-8cf0400d001e`

## Steps Executed

1. Logged in as admin and member; validated tenant/user context via `GET /api/auth/me`.
2. Validated admin read access on `GET /api/audit-log` with baseline list (`limit=25, offset=0`) and pagination probes (`limit=5, offset=0/5`), then fetched page-2 (`limit=25, offset=25`) to cover full current dataset.
3. Validated filters on admin path:
   - `actor_user_id=<admin_uuid>`
   - `resource_type=<first_row.resource_type>`
   - `resource_id=<first_row.resource_id>`
   - `from_date=2026-03-01T00:00:00Z&to_date=<now>`
4. Ran a negative contract probe for invalid filter input (`actor_user_id=not-a-uuid` -> `400`).
5. Validated access control boundaries:
   - member token -> `403`
   - no token -> `401` (with/without filters)
6. Scanned returned records for leakage patterns across:
   - baseline page (`25` rows),
   - date-window page (`25` rows),
   - full dataset (`31` rows, page0+page1).
7. Added focused Wave 7 event-type scan for action keywords (`root`, `governance`, `secret_migration`, `exception`, `notification`) and ran same leakage rules against that focused subset.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Admin token issued. | 2026-03-02T19:39:25Z | `evidence/api/test-32-live-20260302T193915Z-01-login-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/auth/me` | Bearer admin token | `200` | Admin context confirmed (`tenant=Valens`, `user.role=admin`, `user.id=57e658d9-d5c1-478a-81f8-8cf0400d001e`). | 2026-03-02T19:39:32Z | `evidence/api/test-32-live-20260302T193915Z-02-auth-me-admin.*` |
| 3 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"wave3acc+20260228T213251Z@example.com","password":"***REDACTED***"}` | `200` | Member token issued. | 2026-03-02T19:39:35Z | `evidence/api/test-32-live-20260302T193915Z-03-login-member.*` |
| 4 | GET | `https://api.valensjewelry.com/api/auth/me` | Bearer member token | `200` | Member context confirmed (`role=member`, same tenant). | 2026-03-02T19:39:37Z | `evidence/api/test-32-live-20260302T193915Z-04-auth-me-member.*` |
| 5 | GET | `https://api.valensjewelry.com/api/audit-log?limit=25&offset=0` | Bearer admin token | `200` | Baseline contract: `total=31`, `items=25`, `limit=25`, `offset=0`; shape fields present (`id, tenant_id, actor_user_id, action, resource_type, resource_id, timestamp, created_at, payload`), `payload=null` on all rows. | 2026-03-02T19:39:39Z | `evidence/api/test-32-live-20260302T193915Z-05-audit-log-admin-limit25-offset0.*` |
| 6 | GET | `https://api.valensjewelry.com/api/audit-log?limit=5&offset=0` | Bearer admin token | `200` | Pagination page 1 returned 5 rows. | 2026-03-02T19:39:41Z | `evidence/api/test-32-live-20260302T193915Z-06-audit-log-admin-limit5-offset0.*` |
| 7 | GET | `https://api.valensjewelry.com/api/audit-log?limit=5&offset=5` | Bearer admin token | `200` | Pagination page 2 returned 5 rows; no overlap with page 1 (`overlap_count=0`). | 2026-03-02T19:39:42Z | `evidence/api/test-32-live-20260302T193915Z-07-audit-log-admin-limit5-offset5.*` |
| 8 | GET | `https://api.valensjewelry.com/api/audit-log?actor_user_id=<admin_uuid>&limit=25&offset=0` | Bearer admin token | `200` | Actor filter succeeded; returned rows bound to `actor_user_id=57e658d9-d5c1-478a-81f8-8cf0400d001e`. | 2026-03-02T19:39:48Z | `evidence/api/test-32-live-20260302T193915Z-08-audit-log-admin-filter-actor-user.*` |
| 9 | GET | `https://api.valensjewelry.com/api/audit-log?resource_type=remediation_run&limit=25&offset=0` | Bearer admin token | `200` | Resource-type filter succeeded (`total=29`, resource_type fixed to `remediation_run`). | 2026-03-02T19:39:51Z | `evidence/api/test-32-live-20260302T193915Z-09-audit-log-admin-filter-resource-type.*` |
| 10 | GET | `https://api.valensjewelry.com/api/audit-log?resource_id=b9e50351-02a0-4784-a2f1-473929da696e&limit=25&offset=0` | Bearer admin token | `200` | Resource-id filter succeeded (`total=1`, stable target row). | 2026-03-02T19:39:52Z | `evidence/api/test-32-live-20260302T193915Z-10-audit-log-admin-filter-resource-id.*` |
| 11 | GET | `https://api.valensjewelry.com/api/audit-log?from_date=2026-03-01T00:00:00Z&to_date=<run_now>&limit=200&offset=0` | Bearer admin token | `200` | Date filter succeeded (`total=25`, all returned actions in this window were `remediation_run_completed`). | 2026-03-02T19:39:54Z | `evidence/api/test-32-live-20260302T193915Z-11-audit-log-admin-filter-date-range.*` |
| 12 | GET | `https://api.valensjewelry.com/api/audit-log?actor_user_id=not-a-uuid&limit=25&offset=0` | Bearer admin token | `400` | Filter validation enforced (`detail=\"actor_user_id must be a valid UUID\"`). | 2026-03-02T19:39:56Z | `evidence/api/test-32-live-20260302T193915Z-12-audit-log-admin-invalid-actor-filter.*` |
| 13 | GET | `https://api.valensjewelry.com/api/audit-log?limit=25&offset=0` | Bearer member token | `403` | Non-admin access blocked (`Only tenant admins can view audit logs.`). | 2026-03-02T19:39:57Z | `evidence/api/test-32-live-20260302T193915Z-13-audit-log-member-forbidden.*` |
| 14 | GET | `https://api.valensjewelry.com/api/audit-log?limit=25&offset=0` | No token | `401` | Unauthenticated access blocked (`Not authenticated`). | 2026-03-02T19:39:58Z | `evidence/api/test-32-live-20260302T193915Z-14-audit-log-no-auth.*` |
| 15 | GET | `https://api.valensjewelry.com/api/audit-log?actor_user_id=<admin_uuid>&limit=25&offset=0` | No token | `401` | Unauthenticated filtered request also blocked (`Not authenticated`). | 2026-03-02T19:40:00Z | `evidence/api/test-32-live-20260302T193915Z-15-audit-log-no-auth-with-filter.*` |
| 16 | GET | `https://api.valensjewelry.com/api/audit-log?limit=25&offset=25` | Bearer admin token | `200` | Full-dataset tail page returned 6 rows; combined full scan size `31`. | 2026-03-02T19:40:52Z | `evidence/api/test-32-live-20260302T193915Z-16-audit-log-admin-limit25-offset25.*` |
| 17 | N/A | N/A | Leakage + focused wave-event scans | N/A | No leakage pattern matches in baseline/date/full/focus scans; focused wave-event keyword subset returned `0` rows in current tenant dataset. | 2026-03-02T19:40:00Z to 2026-03-02T19:40:52Z | `evidence/api/test-32-live-20260302T193915Z-90-summary-contract-security.json`, `...-91-focus-wave7-actions.json`, `...-92-leakage-scan-details.json`, `...-93-full-dataset-leakage-wave7-scan.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| API-only security/contract test | N/A | No UI-specific assertion required for this test scope. | N/A |

## Assertions

- Positive path: PASS. Admin can read `/api/audit-log` (`200`) and receives stable list contract with pagination and filter support (`actor_user_id`, `resource_type`, `resource_id`, `from_date/to_date`).
- Negative path: PASS. Invalid UUID filter rejects with `400` and deterministic validation message.
- Auth boundary: PASS. Member access is blocked (`403`), no-auth access is blocked (`401`) for both base and filtered requests.
- Contract shape: PASS. Returned rows consistently include expected keys and `payload=null`; pagination counts/offsets are coherent (`total=31`, `limit/offset` echoed, page overlap `0`).
- Idempotency/retry: Not exercised (read-only endpoint probes only).
- Auditability: PASS. Full evidence captured per call (`request`, `status`, `headers`, `json`, `timestamp`) plus scan summaries and context digest.

## Tracker Updates

- Primary tracker section/row:
  - Section 3 row `#11` (`Audit records contain secrets...`) -> `✅ FIXED`
  - Section 3 row `#12` (`Non-admin user can read audit log`) -> `✅ FIXED`
- Tracker section hint: Section 1 and Section 3
- Section 8 checkbox impact:
  - `T32` -> checked (`[x]`)
- Section 9 changelog update needed:
  - Added `2026-03-02` entry for Wave 8 Test 32 closure (`test-32-live-20260302T193915Z`).
  - Section 1 intentionally unchanged in this update because `/api/audit-log` was present at runtime (`200`, not `404`).

## Notes

- Full-dataset action mix (31 rows): `remediation_run_completed=29`, `control_plane_token_rotated=2`.
- Focused Wave 7 event-type keyword scan (`root|governance|secret_migration|exception|notification`) returned no matching action names in the current tenant dataset; leakage checks were still executed over baseline/date/full datasets and returned zero hits.
