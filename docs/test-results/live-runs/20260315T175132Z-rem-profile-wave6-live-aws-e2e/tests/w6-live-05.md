# Test 05 - S3.5 preservation-evidence gating

- Wave: `Wave 6`
- Date (UTC): `2026-03-15T18:06:05Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18012`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `a2805c66-3117-430d-9ab5-699835441dda`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Required prior artifacts: `action_id=dc64daaa-a4d4-4352-be62-edfaee3e459a`

## Steps Executed

1. Fetched remediation options for the bucket-scoped `S3.5` action.
2. Previewed `s3_enforce_ssl_strict_deny`.
3. Created the acknowledged run and fetched run detail after worker completion.
4. Inspected the generated bundle and confirmed it was guidance-only because preservation evidence was incomplete.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `GET` | `/api/actions/dc64daaa-a4d4-4352-be62-edfaee3e459a/remediation-options` | none | `200` | Bucket-policy preservation evidence failed with `AccessDenied`; profile stayed `review_required_bundle` | `2026-03-15T18:04:41Z` | `../evidence/api/dc64daaa-a4d4-4352-be62-edfaee3e459a-options.json` |
| 2 | `GET` | `/api/actions/dc64daaa-a4d4-4352-be62-edfaee3e459a/remediation-preview` | strict-deny preview | `200` | Preview resolution stayed `review_required_bundle` with explicit preservation blockers | `2026-03-15T18:05:07Z` | `../evidence/api/w6-live-05-s3-5-preview.json` |
| 3 | `POST` | `/api/remediation-runs` | acknowledged create | `201` | Review-tier run was accepted | `2026-03-15T18:06:05Z` | `../evidence/api/w6-live-05-s3-5-create-ack-request.json`, `../evidence/api/w6-live-05-s3-5-create-ack-response.json` |
| 4 | `GET` | `/api/remediation-runs/dfd14fde-5744-4b05-81af-7248c6a5d466` | none | `200` | Canonical resolution persisted `review_required_bundle` with `AccessDenied` blockers | `2026-03-15T18:06:05Z` | `../evidence/api/w6-live-05-s3-5-run-detail.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `fail` — no executable S3.5 branch could be proven because the runtime could not inspect the existing bucket policy.
- Negative path: `pass` — the under-proven branch downgraded explicitly and emitted only `decision.json` guidance, not Terraform.
- Auth boundary: `not exercised in this test`
- Contract shape: `pass` — blocked reasons named the missing merge-safe policy evidence and the underlying `AccessDenied`.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — options, preview, create, run detail, and the non-executable bundle were saved.

## Result

- Status: `BLOCKED`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 6 / W6-LIVE-05`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- The current runtime emitted the downgrade bundle as guidance only under `../evidence/bundles/w6-live-05-s3-5/`.
- Because the import-role credential set lacks the S3 policy-read proof needed for preservation safety, no executable S3.5 live proof was reachable in this environment.

