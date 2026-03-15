# Test 06 - all-executable grouped run remains live-AWS compatible

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T00:39:13Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18004`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `69d0da9c-3244-47ca-b556-37993e25f6ea`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Required prior artifacts: `action-groups-list.json`, grouped family details, `accounts-list.json`

## Steps Executed

1. Enumerated all grouped families available after real ingest.
2. Verified only three grouped families existed.
3. Tested the EBS grouped family without risk acknowledgement to see whether an all-executable bundle still existed.
4. Reviewed the live execution guidance on the S3 access-logging family.
5. Reviewed the S3 SSL family and its failed grouped creation attempt.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `GET` | `/api/action-groups` | `account_id=696505809372&limit=200` | `200` | Only three grouped families were available to test | `2026-03-15T00:27:05Z` | `../evidence/api/action-groups-list.json` |
| 2 | `POST` | `/api/action-groups/40041bfb-2ee9-4afd-9436-cb93a976c6ca/bundle-run` | `strategy_id=snapshot_block_all_sharing`, `risk_acknowledged=false` | `400` | Explicit `Risk acknowledgement required` for the EBS family | `2026-03-15T00:36:39Z` | `../evidence/api/rpw5-live-06-create-request.json`, `../evidence/api/rpw5-live-06-create-response.json` |
| 3 | `GET` | `/api/actions/bb487cfd-2d28-41a6-8ec3-5f685e4eaa26` and `/api/actions/47c023ae-945c-42bf-9b44-018d276046fa` | none | `200` | Both access-logging actions exposed `risk_evaluation_not_specialized` unknown in execution guidance | `2026-03-15T00:34-00:35Z` | `../evidence/api/bb487cfd-2d28-41a6-8ec3-5f685e4eaa26-detail.json`, `../evidence/api/47c023ae-945c-42bf-9b44-018d276046fa-detail.json` |
| 4 | `POST` | `/api/action-groups/72f78e58-d068-4679-a9c8-180ff944efbc/bundle-run` | `strategy_id=s3_enforce_ssl_strict_deny`, `preserve_existing_policy=true`, `risk_acknowledged=true` | `400` | The SSL family is blocked by missing bucket-identifier evidence on the account-scoped member | `2026-03-15T00:39:13Z` | `../evidence/api/rpw5-live-03-mixed-case-attempt-response.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `blocked` — no all-executable grouped run existed in the isolated live dataset.
- Negative path: `pass` — each blocker was explicit (`risk_ack_required` or dependency failure), not a hidden `500`.
- Auth boundary: `not exercised`
- Contract shape: `pass` — the exact missing all-executable scenario is now concrete.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — all family-specific blockers were captured.

## Result

- Status: `BLOCKED`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 5 / RPW5-LIVE-06`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- The isolated AWS account also lacked a connected WriteRole, so even a discovered executable grouped run would still have been unable to reach plan/apply in this environment.
