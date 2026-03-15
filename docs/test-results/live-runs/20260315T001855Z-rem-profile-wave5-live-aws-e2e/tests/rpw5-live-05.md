# Test 05 - grouped reporting supports non_executable_results

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T00:39:14Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18004`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `69d0da9c-3244-47ca-b556-37993e25f6ea`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Required prior artifacts: `group_run_id=9a786cb6-051a-460f-b170-de0835ed1041`, `remediation_run_id=e36343f8-dcf3-49a1-bb20-01a4a72f09c9`, live reporting token from bundle creation

## Steps Executed

1. Created a fresh zero-executable grouped EBS run to obtain a live report token and callback URL.
2. Posted a `started` callback with the live token.
3. Posted a `finished` callback with `action_results=[]` and `non_executable_results[]` for both grouped actions.
4. Queried the action-group runs list after the callback.
5. Queried `action_group_run_results` directly in the isolated database to confirm per-action persistence.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `POST` | `/api/action-groups/40041bfb-2ee9-4afd-9436-cb93a976c6ca/bundle-run` | `strategy_id=snapshot_block_all_sharing`, `risk_acknowledged=true` | `201` | Fresh group run and reporting token created | `2026-03-15T00:37:54Z` | `../evidence/api/rpw5-live-05-create-request.json`, `../evidence/api/rpw5-live-05-create-response.json` |
| 2 | `POST` | `/api/internal/group-runs/report` | `event=started` | `200` | Started callback accepted | `2026-03-15T00:39:13Z` | `../evidence/api/rpw5-live-05-callback-started-request.json`, `../evidence/api/rpw5-live-05-callback-started-response.json` |
| 3 | `POST` | `/api/internal/group-runs/report` | `event=finished`, `non_executable_results[]` only | `200` | Finished callback accepted | `2026-03-15T00:39:13Z` | `../evidence/api/rpw5-live-05-callback-finished-request.json`, `../evidence/api/rpw5-live-05-callback-finished-response.json` |
| 4 | `GET` | `/api/action-groups/40041bfb-2ee9-4afd-9436-cb93a976c6ca/runs` | none | `200` | Latest run finished with `reporting_source=bundle_callback` | `2026-03-15T00:39:14Z` | `../evidence/api/rpw5-live-05-group-runs-after-callback.json` |
| 5 | `SQL` | `action_group_run_results` for `group_run_id=9a786cb6-051a-460f-b170-de0835ed1041` | none | `N/A` | Two result rows persisted `raw_result.result_type=non_executable` and `execution_status=unknown` | `2026-03-15T00:39:14Z` | `../evidence/api/rpw5-live-05-group-run-results.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `partial` — `non_executable_results[]` was accepted and persisted coherently.
- Negative path: `pass` — the group run did not fail solely because non-executable results were present.
- Auth boundary: `not exercised in this test`
- Contract shape: `pass` — callback payloads mapped cleanly into the ActionGroupRun / ActionGroupRunResult records.
- Idempotency/retry: `not proven here`
- Auditability: `pass` — callback requests, responses, and persisted rows were all captured.

## Result

- Status: `PARTIAL`
- Severity (if issue found): `🟡 MEDIUM`
- Primary tracker mapping: `Wave 5 / RPW5-LIVE-05`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- This run could not prove `action_results[]` for executable grouped actions because the isolated live dataset had no executable grouped family.
- Callback replay behavior was tested separately under `RPW5-LIVE-08` and failed.
