# Test 01 - mixed-tier grouped bundle generation on real AWS-backed data

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T00:39:13Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18004`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `69d0da9c-3244-47ca-b556-37993e25f6ea`
- AWS Account: `696505809372`
- Region(s): `eu-north-1` for grouped probes; `us-east-1` and `eu-north-1` for ingest
- Required prior artifacts: `real ingest completed`, `action-groups-list.json`, grouped-family detail files

## Steps Executed

1. Ingested real Security Hub data from the isolated AWS account into the isolated local runtime.
2. Enumerated grouped action families and confirmed only three grouped families existed: `ebs_snapshot_block_public_access`, `s3_bucket_access_logging`, and `s3_bucket_require_ssl`.
3. Attempted an invalid synthetic mixed-tier path on the EBS group by mixing a deterministic action with an exception-only override; the route rejected it explicitly.
4. Attempted a real migrated mixed-tier candidate on the S3 SSL group with `risk_acknowledged=true`; the route rejected it because one live action had no bucket identifier and failed dependency checks.
5. Reviewed live action details and previews for all three grouped families to identify whether any one family actually produced `deterministic_bundle + review/manual` in the current dataset.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `POST` | `/api/aws/accounts/696505809372/ingest` | `register-account-request.json` had already created the account; ingest body empty | `202` | Real ingest queued against the connected ReadRole | `2026-03-15T00:24:59Z` | `../evidence/api/ingest-response.json` |
| 2 | `GET` | `/api/action-groups` | `account_id=696505809372&limit=200` | `200` | Only three grouped families had `total_actions > 1` | `2026-03-15T00:27:05Z` | `../evidence/api/action-groups-list.json` |
| 3 | `POST` | `/api/action-groups/40041bfb-2ee9-4afd-9436-cb93a976c6ca/bundle-run` | `strategy_id=snapshot_block_all_sharing` plus exception-only override | `400` | Explicit `Exception-only strategy`; no fake mixed-tier success | `2026-03-15T00:29:17Z` | `../evidence/api/rpw5-live-01-create-request.json`, `../evidence/api/rpw5-live-01-create-response.json` |
| 4 | `POST` | `/api/action-groups/72f78e58-d068-4679-a9c8-180ff944efbc/bundle-run` | `strategy_id=s3_enforce_ssl_strict_deny`, `preserve_existing_policy=true`, `risk_acknowledged=true` | `400` | Explicit `Dependency check failed`; one live action lacked a derivable bucket name | `2026-03-15T00:39:13Z` | `../evidence/api/rpw5-live-03-mixed-case-attempt-request.json`, `../evidence/api/rpw5-live-03-mixed-case-attempt-response.json` |
| 5 | `GET` | `/api/actions/{id}` for grouped members | none | `200` | Live execution guidance showed the EBS family becomes review-only when acknowledged and the S3 SSL account-scoped member is fail-blocked | `2026-03-15T00:34-00:36Z` | `../evidence/api/cd54929e-54d9-4c8a-b648-04a42bab0025-detail.json`, `../evidence/api/e3cd4d2e-9fbd-41d1-93a3-550fb3a36e27-detail.json`, `../evidence/api/d3f654b5-732f-42f2-a8c9-2f2c7aef4134-detail.json`, `../evidence/api/ac73b584-a7a6-4435-be17-2e3f783fe6c8-detail.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `fail/block` — no real grouped run in this live dataset produced the required mixed-tier split.
- Negative path: `pass` — all failed attempts returned explicit `400` contracts, not `500`.
- Auth boundary: `not exercised`
- Contract shape: `pass` — the blocker is concrete and attributable to specific grouped families, not an unknown.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — all discovery and failure responses were captured under the run folder.

## Result

- Status: `BLOCKED`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 5 / RPW5-LIVE-01`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- Exact missing live scenario:
  - `ebs_snapshot_block_public_access` becomes all-`review_required_bundle` with `risk_acknowledged=true`.
  - `s3_bucket_access_logging` is review-only in live execution guidance and includes an account-scoped member.
  - `s3_bucket_require_ssl` is mixed only in the sense that one action is review-required and the other is fail-blocked; it never yields an executable + review/manual bundle.
