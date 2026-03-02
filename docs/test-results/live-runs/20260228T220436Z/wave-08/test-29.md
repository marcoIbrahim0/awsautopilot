# Test 29

- Wave: 08
- Focus: Ingest sync and account freshness field validation
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity:
  - Tenant A admin: `maromaher54@gmail.com`
  - Same-tenant member: `wave3acc+20260228T213251Z@example.com`
  - Wrong-tenant admin created during run: `wave8.test29.20260302T211811Z@example.com`
- Tenant A: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account under test: `029037611564`
- Region(s): `eu-north-1`
- Canonical evidence prefix: `test-29-live-20260302T211811Z-*`
- Progress baseline timestamp: `started_after=2026-03-02T21:18:13Z`

## Steps Executed

1. Logged in as tenant admin and captured tenant/account context (`/api/auth/me`, `/api/aws/accounts`).
2. Triggered `POST /api/aws/accounts/{account_id}/ingest-sync` with admin token.
3. Polled `GET /api/aws/accounts/{account_id}/ingest-progress?started_after=...` to terminal status.
4. Captured post-refresh account list and compared `last_synced_at` pre/post.
5. Executed boundary probes: missing `started_after`, invalid account, no token, same-tenant member token, wrong-tenant token.
6. Captured no-auth Accounts route UI probe.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Admin token issued. | 2026-03-02T21:18:11Z | `evidence/api/test-29-live-20260302T211811Z-01-login-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/auth/me` | Bearer admin token | `200` | Tenant resolved as `Valens`; role=`admin`. | 2026-03-02T21:18:12Z | `evidence/api/test-29-live-20260302T211811Z-02-auth-me-admin.*` |
| 3 | GET | `https://api.valensjewelry.com/api/aws/accounts` (pre) | Bearer admin token | `200` | `last_synced_at` present/non-null (`2026-03-02T18:55:05.887601Z`). | 2026-03-02T21:18:12Z | `evidence/api/test-29-live-20260302T211811Z-03-accounts-pre.*` |
| 4 | POST | `https://api.valensjewelry.com/api/aws/accounts/029037611564/ingest-sync` | `{"regions":["eu-north-1"]}` | `200` | Success contract returned for valid in-tenant trigger. | 2026-03-02T21:18:13Z | `evidence/api/test-29-live-20260302T211811Z-05-ingest-sync-trigger.*` |
| 5 | GET (poll loop) | `/api/aws/accounts/029037611564/ingest-progress?started_after=2026-03-02T21:18:13Z` | Bearer admin token | `200` series | Progress reached terminal `completed` at poll `7` with `progress=100`, `percent_complete=100`, `estimated_time_remaining=0`, `updated_findings_count=438`. | 2026-03-02T21:18:14Z to 2026-03-02T21:18:47Z | `evidence/api/test-29-live-20260302T211811Z-06-ingest-progress-poll-1.*` ... `...-12-ingest-progress-poll-7.*`, `...-13-started-after.txt`, `...-14-terminal-status.txt`, `...-15-terminal-poll.txt` |
| 6 | GET | `https://api.valensjewelry.com/api/aws/accounts` (post) | Bearer admin token | `200` | `last_synced_at` remained non-null and advanced to `2026-03-02T21:18:17.101603Z`. | 2026-03-02T21:18:48Z | `evidence/api/test-29-live-20260302T211811Z-16-accounts-post.*` |
| 7 | GET | `https://api.valensjewelry.com/api/aws/accounts/029037611564/ingest-progress` (missing `started_after`) | Bearer admin token | `422` | Required query validation enforced (`started_after` missing). | 2026-03-02T21:18:48Z | `evidence/api/test-29-live-20260302T211811Z-17-ingest-progress-missing-started-after.*` |
| 8 | POST | `https://api.valensjewelry.com/api/aws/accounts/000000000000/ingest-sync` | Bearer admin token + same body | `404` | Invalid account correctly denied (`{"error":"Account not found"}`). | 2026-03-02T21:18:49Z | `evidence/api/test-29-live-20260302T211811Z-18-ingest-sync-invalid-account.*` |
| 9 | POST | `https://api.valensjewelry.com/api/aws/accounts/029037611564/ingest-sync` (no auth) | Same body, no token | `401` | Unauthenticated request denied. | 2026-03-02T21:18:49Z | `evidence/api/test-29-live-20260302T211811Z-19-ingest-sync-no-auth.*` |
| 10 | POST + GET + POST | `/api/auth/login` (member), `/api/auth/me` (member), `/api/aws/accounts/{id}/ingest-sync` (member) | Member creds/token + same body | `200 / 200 / 200` | Member behavior deterministic and allowed; trigger returns same success contract. | 2026-03-02T21:18:50Z to 2026-03-02T21:18:52Z | `evidence/api/test-29-live-20260302T211811Z-20-login-member.*`, `...-21-auth-me-member.*`, `...-22-ingest-sync-member-token.*` |
| 11 | POST + GET + POST | `/api/auth/signup` (tenant B), `/api/auth/me` (tenant B), `/api/aws/accounts/{id}/ingest-sync` (tenant B token) | Wrong-tenant admin token + same body | `201 / 200 / 404` | Cross-tenant ingest-sync blocked with `404` (`Account not found`). | 2026-03-02T21:18:52Z to 2026-03-02T21:18:54Z | `evidence/api/test-29-live-20260302T211811Z-23-signup-wrong-tenant-admin.*`, `...-24-auth-me-wrong-tenant.*`, `...-25-ingest-sync-wrong-tenant-token.*` |
| 12 | Summary | Context digest | N/A | N/A | Consolidated run metadata (`started_after`, `terminal_status`, `terminal_poll`, identities). | 2026-03-02 | `evidence/api/test-29-live-20260302T211811Z-26-context-summary.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/accounts` (no auth) | No sensitive account data without auth | Returned `200` app shell; API account data remains auth-protected (`401` no-auth probe). | `evidence/ui/test-29-live-20260302T211811Z-ui-01-accounts-route-no-auth.*` |

## Assertions

- Positive path: PASS. Valid in-tenant admin `POST /ingest-sync` returned `200`.
- Progress contract: PASS. `started_after` polling advanced to terminal `completed` with `progress=100` and completion metadata.
- Freshness field: PASS. `last_synced_at` present/non-null pre and post, and advanced after completed refresh.
- Negative path: PASS. Invalid account probe returned `404`; missing `started_after` probe returned `422`.
- Auth boundary: PASS. No-auth returned `401`; wrong-tenant returned `404`.
- Member behavior: PASS. Member token produced `200` with the same queued contract.

## Tracker Updates

- Primary tracker sections updated from this run:
  - Section 1 row #14
  - Section 2 row #12
  - Section 4 row #27
  - Section 6 row #11
- Section 8 checkbox impact: none.
- Section 9 changelog impact: added Wave 8 Test 29 rerun entry with canonical prefix `test-29-live-20260302T211811Z`.

## Notes

- This run is a revalidation-only execution with no product code changes.
- Canonical assertions for this test are based on `test-29-live-20260302T211811Z-*`.
