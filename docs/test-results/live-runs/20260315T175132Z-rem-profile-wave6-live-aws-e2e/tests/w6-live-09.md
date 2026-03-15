# Test 09 - CloudTrail.1 migration boundaries

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
- Required prior artifacts: `action_id=4c4f4b3b-90d5-4682-a94a-1cfdc673bdc6`

## Steps Executed

1. Read tenant remediation settings, then patched `cloudtrail.default_bucket_name=config-bucket-696505809372`.
2. Re-fetched CloudTrail options and confirmed the resolver consumed the tenant default, changing the blocker from missing default to bucket verification `403`.
3. Previewed `cloudtrail_enable_guided`.
4. Attempted create without `risk_acknowledged`, then re-ran the same request with `risk_acknowledged=true`.
5. Fetched run detail and inspected the generated bundle.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `GET` | `/api/users/me/remediation-settings` | none | `200` | Baseline remediation settings captured before default injection | `2026-03-15T18:04:55Z` | `../evidence/api/remediation-settings-before.json` |
| 2 | `PATCH` | `/api/users/me/remediation-settings` | set `cloudtrail.default_bucket_name=config-bucket-696505809372` | `200` | Tenant defaults updated successfully | `2026-03-15T18:05:00Z` | `../evidence/api/remediation-settings-update-request.json`, `../evidence/api/remediation-settings-update-response.json` |
| 3 | `GET` | `/api/actions/4c4f4b3b-90d5-4682-a94a-1cfdc673bdc6/remediation-options` | none | `200` | Options now used the tenant default and downgraded on bucket verification `403` instead of missing-defaults | `2026-03-15T18:05:02Z` | `../evidence/api/4c4f4b3b-90d5-4682-a94a-1cfdc673bdc6-options-after-settings.json` |
| 4 | `GET` | `/api/actions/4c4f4b3b-90d5-4682-a94a-1cfdc673bdc6/remediation-preview` | guided preview | `200` | Preview resolution stayed `review_required_bundle` with explicit `403` blocker | `2026-03-15T18:05:08Z` | `../evidence/api/w6-live-09-cloudtrail-preview.json` |
| 5 | `POST` | `/api/remediation-runs` | create without risk acknowledgement | `400` | Explicit `Risk acknowledgement required` gate fired | `2026-03-15T18:05:08Z` | `../evidence/api/w6-live-09-cloudtrail-create-request.json`, `../evidence/api/w6-live-09-cloudtrail-create-response.json` |
| 6 | `POST` | `/api/remediation-runs` | create with `risk_acknowledged=true` | `201` | Review-tier CloudTrail run was accepted | `2026-03-15T18:06:05Z` | `../evidence/api/w6-live-09-cloudtrail-create-ack-request.json`, `../evidence/api/w6-live-09-cloudtrail-create-ack-response.json` |
| 7 | `GET` | `/api/remediation-runs/cb6a9e54-3660-4bc5-9a63-452fa7934362` | none | `200` | Canonical resolution persisted `review_required_bundle` with the `403` blocker | `2026-03-15T18:06:05Z` | `../evidence/api/w6-live-09-cloudtrail-run-detail.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `fail` — no safe executable CloudTrail branch was proven because the selected log bucket could not be verified from this account context.
- Negative path: `pass` — tenant defaults were consumed when available, and the branch downgraded explicitly instead of being reported executable.
- Auth boundary: `not exercised in this test`
- Contract shape: `pass` — the public strategy ID `cloudtrail_enable_guided` stayed unchanged, and create persisted the canonical review-tier resolution.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — settings before/update, options-after-settings, preview, create responses, run detail, and the generated bundle were saved.

## Result

- Status: `BLOCKED`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 6 / W6-LIVE-09`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- Current `master` uses the tenant default correctly, but the branch stays review-only because the import-role credential set cannot prove bucket reachability safely.
- The current single-run CloudTrail review bundle under `../evidence/bundles/w6-live-09-cloudtrail/` still emits Terraform files plus README guidance; the canonical resolution remains `review_required_bundle`.

