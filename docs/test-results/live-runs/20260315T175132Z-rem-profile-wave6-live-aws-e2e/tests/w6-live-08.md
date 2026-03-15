# Test 08 - S3.15 AWS-managed vs customer-managed KMS branching

- Wave: `Wave 6`
- Date (UTC): `2026-03-15T18:05:00Z`
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

1. Reviewed fresh live Security Hub counts for `S3.15`.
2. Reviewed the isolated runtime action inventory after live ingest.
3. Confirmed that no `S3.15` action surface existed for AWS-managed or customer-managed KMS branch validation.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `AWS Security Hub read` | `GetFindings` (`S3.15`, both regions) | import-role query | `N/A` | `S3.15` findings count was `0` in both monitored regions | `2026-03-15T18:09:00Z` | `../evidence/aws/wave6-family-finding-counts.json` |
| 2 | `DB inventory review` | `actions` table filtered to Wave 6 controls | SQL read only | `N/A` | No `S3.15` action row existed after live ingest | `2026-03-15T18:09:00Z` | `../evidence/api/wave6-action-inventory.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `fail` — no AWS-managed executable branch could be exercised because the family was absent from the live dataset.
- Negative path: `fail` — no customer-managed downgrade branch could be exercised for the same reason.
- Auth boundary: `not exercised in this test`
- Contract shape: `pass` — the blocker is explicit missing scenario/data.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — the raw finding-count and action-inventory artifacts were saved.

## Result

- Status: `BLOCKED`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 6 / W6-LIVE-08`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- Wave 6 cannot claim any live `S3.15` proof from this run because the isolated AWS test account did not surface the family at all.

