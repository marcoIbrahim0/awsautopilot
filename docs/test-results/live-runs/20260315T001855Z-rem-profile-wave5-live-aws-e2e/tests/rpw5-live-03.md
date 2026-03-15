# Test 03 - SaaS plan on mixed-tier grouped bundle only targets executable actions

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
- Required prior artifacts: `accounts-list.json`, grouped family discovery, mixed-tier candidate attempts

## Steps Executed

1. Checked the isolated tenant’s connected AWS account metadata.
2. Confirmed the only connected real AWS test account had `role_write_arn: null`.
3. Attempted to locate a real mixed-tier executable grouped family.
4. Confirmed the only candidate family that differed per member (`s3_bucket_require_ssl`) was hard-blocked by missing bucket-identifier runtime evidence on the account-scoped member.
5. Did not execute SaaS plan on a fabricated or non-equivalent run.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `GET` | `/api/aws/accounts` | none | `200` | Connected isolated account showed `role_write_arn: null` | `2026-03-15T00:36:39Z` | `../evidence/api/accounts-list.json` |
| 2 | `POST` | `/api/action-groups/72f78e58-d068-4679-a9c8-180ff944efbc/bundle-run` | `strategy_id=s3_enforce_ssl_strict_deny`, `preserve_existing_policy=true`, `risk_acknowledged=true` | `400` | Real mixed-tier candidate was blocked by dependency checks on the account-scoped member | `2026-03-15T00:39:13Z` | `../evidence/api/rpw5-live-03-mixed-case-attempt-request.json`, `../evidence/api/rpw5-live-03-mixed-case-attempt-response.json` |
| 3 | `AWS CLI` | `sts assume-role` against inferred standard write role | none | `AccessDenied` | Even the inferred standard `SecurityAutopilotWriteRole` was not assumable from the SaaS account | `2026-03-15T00:42:03Z` | `../evidence/aws/write-role-assume-attempt.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `blocked` — no real mixed-tier executable grouped bundle existed to plan.
- Negative path: `pass` — the environment returned explicit missing-scenario/missing-role signals rather than a hidden platform failure.
- Auth boundary: `not exercised`
- Contract shape: `pass` — the blocker is precise: no executable mixed-tier family plus no connected WriteRole.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — both account metadata and write-role denial were captured.

## Result

- Status: `BLOCKED`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 5 / RPW5-LIVE-03`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- `RPW5-LIVE-07` proved the zero-executable `400 no_executable_bundle` contract, but that is not the same as proving SaaS plan folder selection on a real mixed-tier executable bundle.
