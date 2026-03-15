# Test 02 - EC2.53 downgraded profile branch

- Wave: `Wave 6`
- Date (UTC): `2026-03-15T18:04:30Z`
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

1. Reviewed fresh live Security Hub counts for `EC2.53`.
2. Verified that no `EC2.53` action was materialized into the isolated runtime after live ingest.
3. Confirmed that no options/preview/create surface could be exercised for the expected downgrade branches (`ssm_only`, `bastion_sg_reference`) because no tenant-scoped action existed.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `AWS Security Hub read` | `GetFindings` (`EC2.53`, both regions) | import-role query | `N/A` | No `EC2.53` finding was present to drive a downgrade-path action | `2026-03-15T18:09:00Z` | `../evidence/aws/wave6-family-finding-counts.json` |
| 2 | `DB inventory review` | `actions` table filtered to Wave 6 controls | SQL read only | `N/A` | No `EC2.53` action row existed for downgrade-path validation | `2026-03-15T18:09:00Z` | `../evidence/api/wave6-action-inventory.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `fail` — no downgraded `EC2.53` live branch could be proven because the family is absent from the live dataset.
- Negative path: `pass` — the run did not misclassify any unrelated action as `EC2.53`.
- Auth boundary: `not exercised in this test`
- Contract shape: `pass` — the missing-scenario blocker is explicit and auditable.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — the raw finding-count and action-inventory artifacts were saved.

## Result

- Status: `BLOCKED`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 6 / W6-LIVE-02`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- Because no `EC2.53` tenant action existed, this run could not prove the downgraded `ssm_only` or `bastion_sg_reference` resolver branches on live data.

