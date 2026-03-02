# Test 29

- Wave: 08
- Focus: Ingest sync and account freshness field validation
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity:
  - Tenant A admin: `maromaher54@gmail.com`
  - Same-tenant member: `wave3acc+20260228T213251Z@example.com`
  - Wrong-tenant admin created during run: `wave8.test29.20260302T185356Z@example.com`
- Tenant A: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account under test: `029037611564`
- Region(s): `eu-north-1`
- Canonical evidence prefix: `test-29-live-20260302T185356Z-*`
- Progress baseline timestamp: `started_after=2026-03-02T18:54:00Z`
- Historical failing request IDs traced before fix:
  - `Zm3Mlj35Ai0ENhQ=`
  - `Zm33niMLgi0EPEg=`
  - Root-cause trace artifact: `evidence/api/test-29-live-20260302T185356Z-98-root-cause-log-trace.txt`

## Steps Executed

1. Traced historical failing request IDs in CloudWatch logs and captured backend exception evidence.
2. Deployed patched runtime and applied DB migrations to runtime head.
3. Logged in as tenant admin and captured tenant/account context (`/api/auth/me`, `/api/aws/accounts`).
4. Triggered `POST /api/aws/accounts/{account_id}/ingest-sync` with admin token.
5. Polled `GET /api/aws/accounts/{account_id}/ingest-progress?started_after=...` until terminal status.
6. Captured post-refresh account list and compared `last_synced_at` pre/post.
7. Executed boundary probes: missing `started_after`, invalid account, no token, member token, wrong-tenant token.
8. Captured no-auth UI Accounts route probe.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Admin token issued. | 2026-03-02T18:53:56Z | `evidence/api/test-29-live-20260302T185356Z-01-login-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/auth/me` | Bearer admin token | `200` | Tenant resolved as `Valens`; role=`admin`. | 2026-03-02T18:53:58Z | `evidence/api/test-29-live-20260302T185356Z-02-auth-me-admin.*` |
| 3 | GET | `https://api.valensjewelry.com/api/aws/accounts` (pre) | Bearer admin token | `200` | `last_synced_at` present/non-null (`2026-03-02T13:40:11.914670Z`). | 2026-03-02T18:53:58Z | `evidence/api/test-29-live-20260302T185356Z-03-accounts-pre.*` |
| 4 | POST | `https://api.valensjewelry.com/api/aws/accounts/029037611564/ingest-sync` | `{"regions":["eu-north-1"]}` | `200` | Success contract restored; async queued message returned. | 2026-03-02T18:54:00Z | `evidence/api/test-29-live-20260302T185356Z-05-ingest-sync-trigger.*` |
| 5 | GET (poll loop) | `/api/aws/accounts/029037611564/ingest-progress?started_after=2026-03-02T18:54:00Z` | Bearer admin token | `200` series | Progress contract observed to terminal: `queued (9%) -> running -> completed (100%)` at poll `11`, `updated_findings_count=302`. | 2026-03-02T18:54:01Z to 2026-03-02T18:54:55Z | `evidence/api/test-29-live-20260302T185356Z-06-ingest-progress-poll-1.*` ... `...-16-ingest-progress-poll-11.*`, `...-17-started-after.txt`, `...-18-terminal-status.txt`, `...-19-terminal-poll.txt` |
| 6 | GET | `https://api.valensjewelry.com/api/aws/accounts` (post) | Bearer admin token | `200` | `last_synced_at` remained non-null and advanced to `2026-03-02T18:54:10.536945Z`. | 2026-03-02T18:54:56Z | `evidence/api/test-29-live-20260302T185356Z-20-accounts-post.*` |
| 7 | GET | `https://api.valensjewelry.com/api/aws/accounts/029037611564/ingest-progress` (missing `started_after`) | Bearer admin token | `422` | Required query validation enforced (`started_after` missing). | 2026-03-02T18:54:56Z | `evidence/api/test-29-live-20260302T185356Z-21-ingest-progress-missing-started-after.*` |
| 8 | POST | `https://api.valensjewelry.com/api/aws/accounts/000000000000/ingest-sync` | Bearer admin token + same body | `404` | Invalid account correctly denied (`{"error":"Account not found"}`). | 2026-03-02T18:54:57Z | `evidence/api/test-29-live-20260302T185356Z-22-ingest-sync-invalid-account.*` |
| 9 | POST | `https://api.valensjewelry.com/api/aws/accounts/029037611564/ingest-sync` (no auth) | Same body, no token | `401` | Unauthenticated request denied. | 2026-03-02T18:54:57Z | `evidence/api/test-29-live-20260302T185356Z-23-ingest-sync-no-auth.*` |
| 10 | POST + GET + POST | `/api/auth/login` (member), `/api/auth/me` (member), `/api/aws/accounts/{id}/ingest-sync` (member) | Member creds/token + same body | `200 / 200 / 200` | Member behavior is deterministic and allowed; trigger returns same success contract as admin. | 2026-03-02T18:54:57Z to 2026-03-02T18:55:00Z | `evidence/api/test-29-live-20260302T185356Z-24-login-member.*`, `...-25-auth-me-member.*`, `...-26-ingest-sync-member-token.*` |
| 11 | POST + GET + POST | `/api/auth/signup` (tenant B), `/api/auth/me` (tenant B), `/api/aws/accounts/{id}/ingest-sync` (tenant B token) | Wrong-tenant admin token + same body | `201 / 200 / 404` | Cross-tenant ingest-sync blocked with `404` (`Account not found`). | 2026-03-02T18:55:02Z to 2026-03-02T18:55:05Z | `evidence/api/test-29-live-20260302T185356Z-27-signup-wrong-tenant-admin.*`, `...-28-auth-me-wrong-tenant.*`, `...-29-ingest-sync-wrong-tenant-token.*` |
| 12 | GET | `https://api.valensjewelry.com/api/aws/accounts` (no auth) | no token | `401` | Account-list API no-auth boundary remains closed. | 2026-03-02T18:54:00Z | `evidence/api/test-29-live-20260302T185356Z-04-accounts-no-auth.*` |
| 13 | Log trace | Historical failing request IDs (`Zm3Mlj35Ai0ENhQ=`, `Zm33niMLgi0EPEg=`) | N/A | N/A | CloudWatch trace links previous `500` to local-sync worker import path (`ModuleNotFoundError: tenacity`). | 2026-03-02 | `evidence/api/test-29-live-20260302T185356Z-98-root-cause-log-trace.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/accounts` (no auth) | No sensitive account data without auth | Returned `200` app shell; API account data still auth-protected (`401` no-auth probe). | `evidence/ui/test-29-live-20260302T185356Z-ui-01-accounts-route-no-auth.*` |

## Assertions

- Positive path: PASS. Valid in-tenant admin `POST /ingest-sync` returned `200` with queued async message.
- Progress contract: PASS. `started_after` polling advanced to terminal `completed` with `progress=100` and completion metadata.
- Freshness field: PASS. `last_synced_at` present/non-null pre and post, and advanced after completed refresh.
- Negative path: PASS. Invalid account probe returned `404`; missing `started_after` probe returned `422`.
- Auth boundary: PASS. No-auth returned `401`; wrong-tenant returned `404`.
- Member behavior: PASS (deterministic allow). Member token produced `200` with same queued contract.
- Root-cause evidence quality: PASS. Historical failing request IDs mapped to backend exception chain in CloudWatch evidence.

## Tracker Updates

- Primary tracker sections updated from this run:
  - Section 1 row #14
  - Section 2 row #12
  - Section 4 row #27
  - Section 6 row #11
  - Section 7 (environment note for migration-guard deployment prerequisite)
- Section 8 checkbox impact: none.

## Notes

- Non-canonical attempt `test-29-live-20260302T184423Z-*` was captured during deployment window where API startup was blocked by DB migration guard mismatch and therefore is excluded from final assertions.
- Canonical PASS assertions are based only on `test-29-live-20260302T185356Z-*`.
