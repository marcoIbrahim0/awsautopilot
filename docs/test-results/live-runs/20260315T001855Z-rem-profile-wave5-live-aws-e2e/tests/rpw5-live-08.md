# Test 08 - auth, tenant isolation, and execution safety boundaries

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T00:40:27Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18004`

## Preconditions

- Identity: `isolated local admin user` plus a second isolated tenant admin
- Tenant: `69d0da9c-3244-47ca-b556-37993e25f6ea` and `59d0e0eb-e324-4565-af49-a2f5be451f17`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Required prior artifacts: `run_id=8745650b-c730-416f-8375-7fbbec760aff`, `group_run_id=9a786cb6-051a-460f-b170-de0835ed1041`, live callback token

## Steps Executed

1. Called `execute-pr-bundle` and remediation-run detail with no bearer token.
2. Signed up a second isolated tenant admin user.
3. Called `execute-pr-bundle`, `approve-apply`, and the action-group run list with the second tenant token.
4. Posted a valid callback payload for the first tenant’s live group-run token.
5. Posted an invalid callback token.
6. Replayed the same valid finished callback payload a second time.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `POST` | `/api/remediation-runs/8745650b-c730-416f-8375-7fbbec760aff/execute-pr-bundle` | `{}` without auth | `401` | Unauthorized execute denied | `2026-03-15T00:40:14Z` | `../evidence/api/rpw5-live-08-unauthorized-execute-response.json` |
| 2 | `GET` | `/api/remediation-runs/8745650b-c730-416f-8375-7fbbec760aff` | none without auth | `401` | Unauthorized run detail denied | `2026-03-15T00:40:14Z` | `../evidence/api/rpw5-live-08-unauthorized-run-detail-response.json` |
| 3 | `POST` | `/api/auth/signup` | second-tenant signup | `201` | Second isolated tenant created | `2026-03-15T00:40:27Z` | `../evidence/api/rpw5-live-08-signup-tenant2-response.json` |
| 4 | `POST` | `/api/remediation-runs/8745650b-c730-416f-8375-7fbbec760aff/execute-pr-bundle` | `{}` with second-tenant token | `404` | Wrong-tenant execute denied | `2026-03-15T00:40:47Z` | `../evidence/api/rpw5-live-08-wrong-tenant-execute-response.json` |
| 5 | `POST` | `/api/remediation-runs/8745650b-c730-416f-8375-7fbbec760aff/approve-apply` | none with second-tenant token | `404` | Wrong-tenant approve denied | `2026-03-15T00:40:47Z` | `../evidence/api/rpw5-live-08-wrong-tenant-approve-response.json` |
| 6 | `GET` | `/api/action-groups/40041bfb-2ee9-4afd-9436-cb93a976c6ca/runs` | none with second-tenant token | `200` | Wrong-tenant group-run listing returned an empty set, not the first tenant’s data | `2026-03-15T00:40:47Z` | `../evidence/api/rpw5-live-08-wrong-tenant-group-runs-response.json` |
| 7 | `POST` | `/api/internal/group-runs/report` | invalid token payload | `401` | Invalid reporting token rejected | `2026-03-15T00:39:14Z` | `../evidence/api/rpw5-live-08-invalid-token-request.json`, `../evidence/api/rpw5-live-08-invalid-token-response.json` |
| 8 | `POST` | `/api/internal/group-runs/report` | replay of identical valid finished payload | `200` | Replay was accepted instead of rejected | `2026-03-15T00:39:14Z` | `../evidence/api/rpw5-live-08-callback-replay-response.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `fail` — callback replay tokens were not rejected.
- Negative path: `pass` — invalid callback token was rejected with `401`.
- Auth boundary: `pass` for unauthorized and wrong-tenant execute/apply probes; `pass` for no cross-tenant leakage in tested list surface.
- Contract shape: `fail` — replayed valid finished callback should have been rejected or otherwise fenced, but it was accepted a second time.
- Idempotency/retry: `fail` — the replay acceptance shows missing callback replay protection.
- Auditability: `pass` — all unauthorized, wrong-tenant, invalid-token, and replay responses were captured.

## Result

- Status: `FAIL`
- Severity (if issue found): `🟠 HIGH`
- Primary tracker mapping: `Wave 5 / RPW5-LIVE-08`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- Wrong-tenant group-run listing did not leak the first tenant’s rows; it returned `{"items":[],"total":0}`.
- The callback replay issue is a concrete gate failure for Wave 5 execution-safety boundaries.
