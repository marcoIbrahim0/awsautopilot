# Test 20

- Wave: 06
- Focus: Internal scheduler endpoint auth and secret-guard behavior
- Status: PASS
- Severity (if issue): N/A

## Preconditions

- Identity: Tenant A admin (`maromaher54@gmail.com`) with fresh token from `POST /api/auth/login`.
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`).
- AWS account: `029037611564`.
- Region(s): `eu-north-1`.
- Prerequisite IDs/tokens: Scheduler endpoint tested at `/api/internal/reconciliation/schedule-tick`; runtime secret source verified from Lambda env (`has_reconciliation_scheduler=false`, `has_control_plane_events=true`) and header value supplied from runtime `CONTROL_PLANE_EVENTS_SECRET` fallback.

## Steps Executed

1. Captured live runtime secret-source preconditions from `security-autopilot-dev-api` Lambda configuration.
2. Logged in as tenant admin and revalidated tenant context via `GET /api/auth/me`.
3. Called `POST /api/internal/reconciliation/schedule-tick` with no secret, wrong secret, and user token only.
4. Called `POST /api/internal/reconciliation/schedule-tick` with the correct scheduler secret.
5. Validated status codes and error contracts, then generated a contract summary artifact.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | N/A | Runtime precondition capture | Lambda env variable presence query | N/A | `DIGEST_CRON_SECRET` absent, `RECONCILIATION_SCHEDULER_SECRET` absent, `CONTROL_PLANE_EVENTS_SECRET` present | 2026-03-01T01:14:50Z | `evidence/api/test-20-live-20260301T011449Z-00-runtime-secret-source.*` |
| 2 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Admin token issued | 2026-03-01T01:14:52Z | `evidence/api/test-20-live-20260301T011449Z-01-login-admin.*` |
| 3 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <admin_token>` | `200` | Tenant/user context confirmed (`Valens`, `admin`) | 2026-03-01T01:14:53Z | `evidence/api/test-20-live-20260301T011449Z-02-auth-me-admin.*` |
| 4 | POST | `https://api.valensjewelry.com/api/internal/reconciliation/schedule-tick` | `{"dry_run":true,"limit":1}` (no secret, no auth) | `403` | Denied with `{"detail":"Invalid or missing X-Reconciliation-Scheduler-Secret."}` | 2026-03-01T01:14:53Z | `evidence/api/test-20-live-20260301T011449Z-03-scheduler-no-secret.*` |
| 5 | POST | `https://api.valensjewelry.com/api/internal/reconciliation/schedule-tick` | `{"dry_run":true,"limit":1}` + `X-Reconciliation-Scheduler-Secret: wrong-secret` | `403` | Wrong secret denied with same error contract | 2026-03-01T01:14:53Z | `evidence/api/test-20-live-20260301T011449Z-04-scheduler-wrong-secret.*` |
| 6 | POST | `https://api.valensjewelry.com/api/internal/reconciliation/schedule-tick` | `{"dry_run":true,"limit":1}` + `Authorization: Bearer <admin_token>` | `403` | User token alone denied; secret guard enforced | 2026-03-01T01:14:54Z | `evidence/api/test-20-live-20260301T011449Z-05-scheduler-user-token-only.*` |
| 7 | POST | `https://api.valensjewelry.com/api/internal/reconciliation/schedule-tick` | `{"dry_run":true,"limit":1}` + `X-Reconciliation-Scheduler-Secret: <runtime secret>` | `200` | Accepted; scheduler response returned counters (`evaluated/enqueued/...`, `dry_run=true`) | 2026-03-01T01:14:54Z | `evidence/api/test-20-live-20260301T011449Z-06-scheduler-correct-secret.*` |
| 8 | N/A | Contract summary | N/A | N/A | Expected matrix satisfied: `403/403/403/200`, `all_pass=true` | 2026-03-01T01:14:54Z | `evidence/api/test-20-live-20260301T011449Z-07-contract-check.json`, `...-99-context-summary.txt` |
| 9 | N/A | Rerun contract summary | N/A | N/A | Fresh rerun matched the same matrix (`403/403/403/200`, `all_pass=true`) | 2026-03-01T01:42:58Z | `evidence/api/test-20-rerun-20260301T014248Z-07-contract-check.json`, `...-99-context-summary.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| N/A (API-only security contract test) | Secret-guard behavior validated from API contracts | Confirmed from captured API evidence | N/A |

## Assertions

- Positive path: PASS (`correct secret -> 200` with scheduler counters payload).
- Negative path: PASS (`no secret -> 403`, `wrong secret -> 403`).
- Auth boundary: PASS (`user token only -> 403`; bearer auth does not bypass internal secret guard).
- Contract shape: PASS (all denied calls returned `{"detail":"Invalid or missing X-Reconciliation-Scheduler-Secret."}`).
- Idempotency/retry: PASS (all deny-path calls returned stable status/error contract).
- Auditability: PASS (request/status/headers/body/timestamp + contract summary artifacts captured).

## Tracker Updates

- Primary tracker section/row: Section 4 row #9 (`/api/internal/*` auth guard).
- Tracker section hint: Section 1 and Section 4.
- Section 8 checkbox impact: `T20-9` remains complete.
- Section 9 changelog update needed: Yes (Wave 6 Test 20 revalidation evidence).

## Notes

- This run validated the scheduler route `/api/internal/reconciliation/schedule-tick` secret guard end-to-end.
- Runtime precondition evidence showed `DIGEST_CRON_SECRET` is not present on the live API Lambda environment for this deployment.
- Fresh redo run completed under prefix `test-20-rerun-20260301T014248Z-*` with the same passing auth/secret-guard results.
- No product code changes were made during this test.
