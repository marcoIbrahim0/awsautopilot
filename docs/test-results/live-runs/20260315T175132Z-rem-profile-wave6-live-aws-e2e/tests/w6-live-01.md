# Test 01 - EC2.53 executable profile branch

- Wave: `Wave 6`
- Date (UTC): `2026-03-15T18:04:00Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18012`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `a2805c66-3117-430d-9ab5-699835441dda`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`, `us-east-1`
- Required prior artifacts: `evidence/aws/wave6-family-finding-counts.json`, `evidence/api/wave6-action-inventory.txt`

## Steps Executed

1. Ingested fresh Security Hub findings from the isolated AWS test account into the isolated local runtime.
2. Reviewed control-family finding counts for `EC2.53` in `eu-north-1` and `us-east-1`.
3. Reviewed the post-ingest Wave 6 action inventory for any `EC2.53` remediation action surfaces.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `AWS Security Hub read` | `GetFindings` (`EC2.53`, both regions) | import-role query | `N/A` | `EC2.53` findings count was `0` in `eu-north-1` and `0` in `us-east-1` | `2026-03-15T18:09:00Z` | `../evidence/aws/wave6-family-finding-counts.json` |
| 2 | `DB inventory review` | `actions` table filtered to Wave 6 controls | SQL read only | `N/A` | No `EC2.53` action row existed after live ingest | `2026-03-15T18:09:00Z` | `../evidence/api/wave6-action-inventory.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `fail` — no live `EC2.53` action existed, so no executable branch (`close_public`, `close_and_revoke`, `restrict_to_ip`, `restrict_to_cidr`) could be exercised.
- Negative path: `pass` — the blocker is explicit missing scenario/data, not a hidden runtime exception.
- Auth boundary: `not exercised in this test`
- Contract shape: `pass` — the isolated run preserved an auditable count-based proof that the family is absent from the live dataset.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — the raw finding-count and action-inventory artifacts were saved.

## Result

- Status: `BLOCKED`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 6 / W6-LIVE-01`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- The isolated AWS test account does not currently contain any `EC2.53` finding or action, so Wave 6 cannot claim an executable live EC2.53 proof from this run.

