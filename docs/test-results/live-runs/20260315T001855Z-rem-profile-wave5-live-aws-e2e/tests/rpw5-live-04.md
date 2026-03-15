# Test 04 - SaaS apply on mixed-tier grouped bundle mutates only executable AWS targets

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T00:42:03Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18004`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `69d0da9c-3244-47ca-b556-37993e25f6ea`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Required prior artifacts: `accounts-list.json`, `write-role-assume-attempt.json`, real grouped family discovery

## Steps Executed

1. Verified that no real mixed-tier executable grouped family existed in the live dataset.
2. Verified that the connected isolated account had no connected WriteRole.
3. Verified that even the inferred standard `SecurityAutopilotWriteRole` could not be assumed from the SaaS account.
4. Did not execute any fake apply or mutate any target AWS resources.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `GET` | `/api/aws/accounts` | none | `200` | Connected account metadata showed `role_write_arn: null` | `2026-03-15T00:36:39Z` | `../evidence/api/accounts-list.json` |
| 2 | `AWS CLI` | `sts assume-role` against `arn:aws:iam::696505809372:role/SecurityAutopilotWriteRole` | none | `AccessDenied` | No usable WriteRole existed for plan/apply execution | `2026-03-15T00:42:03Z` | `../evidence/aws/write-role-assume-attempt.json` |
| 3 | `Discovery` | grouped family scan | none | `N/A` | No mixed-tier executable grouped family was available to apply | `2026-03-15T00:27-00:39Z` | `../evidence/api/action-groups-list.json`, `../evidence/api/rpw5-live-03-mixed-case-attempt-response.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `blocked` — no valid target run existed for mixed-tier apply, and the account lacked a usable WriteRole.
- Negative path: `pass` — no unintended AWS mutation was attempted.
- Auth boundary: `not exercised`
- Contract shape: `pass` — the blocker is attributable to account connectivity and missing scenario/data, not to a hidden runtime exception.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — the non-mutation outcome and missing WriteRole evidence were preserved.

## Result

- Status: `BLOCKED`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 5 / RPW5-LIVE-04`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- No AWS pre-state/post-state mutation proof was possible on this run.
- No rollback command was executed against account `696505809372` because no target-account change occurred.
