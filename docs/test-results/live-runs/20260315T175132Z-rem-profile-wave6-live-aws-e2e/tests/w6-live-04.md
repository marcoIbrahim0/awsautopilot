# Test 04 - S3.2 executable and manual-fallback branches

- Wave: `Wave 6`
- Date (UTC): `2026-03-15T18:06:06Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18012`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `a2805c66-3117-430d-9ab5-699835441dda`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Required prior artifacts: `action_id=f081ae21-1114-4a0e-8af3-e5a308615d34`

## Steps Executed

1. Fetched remediation options for the live `S3.2` account-scoped action.
2. Previewed the explicit fallback profile `s3_bucket_block_public_access_manual_preservation`.
3. Attempted create without `risk_acknowledged` and verified the explicit acknowledgment gate.
4. Re-ran create with `risk_acknowledged=true`, fetched run detail, and inspected the generated guidance bundle.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `GET` | `/api/actions/f081ae21-1114-4a0e-8af3-e5a308615d34/remediation-options` | none | `200` | Only manual-guidance S3.2 profiles were available for the live action | `2026-03-15T18:04:43Z` | `../evidence/api/f081ae21-1114-4a0e-8af3-e5a308615d34-options.json` |
| 2 | `GET` | `/api/actions/f081ae21-1114-4a0e-8af3-e5a308615d34/remediation-preview` | manual-preservation preview | `200` | Preview resolution stayed `manual_guidance_only` with explicit blocked reasons | `2026-03-15T18:05:06Z` | `../evidence/api/w6-live-04-s3-2-preview.json` |
| 3 | `POST` | `/api/remediation-runs` | create without risk acknowledgement | `400` | Explicit `Risk acknowledgement required` gate fired before bundle generation | `2026-03-15T18:05:10Z` | `../evidence/api/w6-live-04-s3-2-create-request.json`, `../evidence/api/w6-live-04-s3-2-create-response.json` |
| 4 | `POST` | `/api/remediation-runs` | create with `risk_acknowledged=true` | `201` | Non-executable fallback run was accepted and completed | `2026-03-15T18:06:06Z` | `../evidence/api/w6-live-04-s3-2-create-ack-request.json`, `../evidence/api/w6-live-04-s3-2-create-ack-response.json` |
| 5 | `GET` | `/api/remediation-runs/cd5a4eb4-4ecb-4aa5-9367-6876a8c7c834` | none | `200` | Canonical resolution persisted `support_tier=manual_guidance_only` | `2026-03-15T18:06:06Z` | `../evidence/api/w6-live-04-s3-2-run-detail.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `fail` — no deterministic executable S3.2 branch could be proven on this live action because the runtime only surfaced the downgrade path.
- Negative path: `pass` — the fallback branch downgraded explicitly to `manual_guidance_only` and emitted a non-executable `decision.json` bundle.
- Auth boundary: `not exercised in this test`
- Contract shape: `pass` — the explicit risk-ack gate and the canonical persisted downgrade decision were both present.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — the preview, both create responses, run detail, and extracted non-executable bundle were saved.

## Result

- Status: `BLOCKED`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 6 / W6-LIVE-04`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- Current `master` emitted a guidance-only bundle under `../evidence/bundles/w6-live-04-s3-2/README.txt` and `decision.json`; no Terraform or CloudFormation files were emitted for this downgrade branch.
- No bucket-scoped executable S3.2 live action existed in this test account, so the family remains blocked for Wave 6 gate purposes.

