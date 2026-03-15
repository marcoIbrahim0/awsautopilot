# Test 03 - IAM.4 additive metadata and authority boundary

- Wave: `Wave 6`
- Date (UTC): `2026-03-15T18:06:46Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18012`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `a2805c66-3117-430d-9ab5-699835441dda`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`, `us-east-1`
- Required prior artifacts: `action_id=207c4d45-bd8e-49ba-b4d5-9f2f860e1696`

## Steps Executed

1. Fetched generic IAM.4 remediation options and preview metadata from `/api/actions/{id}` surfaces.
2. Attempted generic `POST /api/remediation-runs` creation for `iam_root_key_disable`.
3. Attempted the dedicated `/api/root-key-remediation-runs` create path with the required contract and idempotency headers.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `GET` | `/api/actions/207c4d45-bd8e-49ba-b4d5-9f2f860e1696/remediation-options` | none | `200` | Generic IAM.4 surfaces exposed metadata only and kept all profiles at `manual_guidance_only` | `2026-03-15T18:04:50Z` | `../evidence/api/207c4d45-bd8e-49ba-b4d5-9f2f860e1696-options.json` |
| 2 | `GET` | `/api/actions/207c4d45-bd8e-49ba-b4d5-9f2f860e1696/remediation-preview` | `mode=pr_only`, `strategy_id=iam_root_key_disable`, `profile_id=iam_root_key_disable` | `200` | Preview resolution stayed `manual_guidance_only` and pointed to `/api/root-key-remediation-runs` | `2026-03-15T18:05:02Z` | `../evidence/api/w6-live-03-iam4-preview.json` |
| 3 | `POST` | `/api/remediation-runs` | `iam_root_key_disable` generic create | `400` | Generic execution failed closed with `reason=root_key_execution_authority` | `2026-03-15T18:06:46Z` | `../evidence/api/w6-live-03-iam4-generic-create-request.json`, `../evidence/api/w6-live-03-iam4-generic-create-response.json` |
| 4 | `POST` | `/api/root-key-remediation-runs` | dedicated root-key create | `404` | Dedicated authority route returned `feature_disabled` in this runtime | `2026-03-15T18:06:46Z` | `../evidence/api/w6-live-03-root-key-create-request.json`, `../evidence/api/w6-live-03-root-key-create-response.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `pass` — generic IAM.4 read surfaces remained additive metadata only and did not advertise generic execution.
- Negative path: `pass` — generic create rejected with the explicit dedicated-authority error instead of creating a second execution path.
- Auth boundary: `not exercised in this test`
- Contract shape: `pass` — the dedicated authority was named explicitly, but the authoritative route itself was disabled in this deployment.
- Idempotency/retry: `not exercised` — the dedicated route never created a run because the feature flag was off.
- Auditability: `pass` — request/response payloads for both generic and dedicated paths were saved.

## Result

- Status: `BLOCKED`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 6 / W6-LIVE-03`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- The generic boundary behavior is correct on current `master`.
- IAM.4 still cannot be claimed validated because the only authoritative execution route was disabled in the isolated runtime, and no safe root-key execution scenario could be completed.

