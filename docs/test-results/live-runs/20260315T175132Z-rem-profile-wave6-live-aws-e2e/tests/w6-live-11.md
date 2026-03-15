# Test 11 - cross-family regression and archived-SaaS boundary

- Wave: `Wave 6`
- Date (UTC): `2026-03-15T18:08:00Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18012`

## Preconditions

- Identity: `isolated local admin user`, plus second isolated tenant `RPW6 Tenant Two`
- Tenant: `a2805c66-3117-430d-9ab5-699835441dda` and second tenant from `w6-live-11-tenant2-signup-response.json`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`, `us-east-1`
- Required prior artifacts: `run_id=49103000-1104-4a36-8757-8e243e883dc5`, `group_run_id=19c522c0-9256-4124-8b39-42b707bdd812`, `group remediation_run_id=837fccdc-a51e-4b1f-a8d0-ed7cc6eea3a3`

## Steps Executed

1. Fetched the connected-account list and confirmed the isolated runtime had only the read-only import role connected (`role_write_arn=null`).
2. Called all four archived public SaaS plan/apply endpoints and confirmed they return `410`.
3. Probed unauthorized read/execute access with no bearer token.
4. Created a second isolated tenant and probed wrong-tenant run detail, action options, grouped run list, and archived execute surfaces.
5. Reviewed single-run and grouped run details to confirm canonical single-run `artifacts.resolution` and grouped `group_bundle.action_resolutions[]` persistence.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `GET` | `/api/aws/accounts` | none | `200` | Connected account metadata showed `role_write_arn: null` and read-only import-role onboarding | `2026-03-15T18:08:20Z` | `../evidence/api/accounts-list.json` |
| 2 | `POST` | `/api/remediation-runs/49103000-1104-4a36-8757-8e243e883dc5/execute-pr-bundle` | `{}` | `410` | Archived SaaS plan route remained gone | `2026-03-15T18:08:20Z` | `../evidence/api/w6-live-11-execute-pr-bundle-response.json` |
| 3 | `POST` | `/api/remediation-runs/49103000-1104-4a36-8757-8e243e883dc5/approve-apply` | none | `410` | Archived SaaS apply route remained gone | `2026-03-15T18:08:20Z` | `../evidence/api/w6-live-11-approve-apply-response.json` |
| 4 | `POST` | `/api/remediation-runs/bulk-execute-pr-bundle` | none | `410` | Archived bulk plan route remained gone | `2026-03-15T18:08:20Z` | `../evidence/api/w6-live-11-bulk-execute-response.json` |
| 5 | `POST` | `/api/remediation-runs/bulk-approve-apply` | none | `410` | Archived bulk apply route remained gone | `2026-03-15T18:08:20Z` | `../evidence/api/w6-live-11-bulk-approve-response.json` |
| 6 | `GET` | `/api/remediation-runs/49103000-1104-4a36-8757-8e243e883dc5` | none without auth | `401` | Unauthorized run-detail access denied | `2026-03-15T18:08:30Z` | `../evidence/api/w6-live-11-unauthorized-run-detail-response.json` |
| 7 | `POST` | `/api/remediation-runs/49103000-1104-4a36-8757-8e243e883dc5/execute-pr-bundle` | `{}` without auth | `401` | Unauthorized execute denied | `2026-03-15T18:08:30Z` | `../evidence/api/w6-live-11-unauthorized-execute-response.json` |
| 8 | `POST` | `/api/auth/signup` | second-tenant signup | `201` | Second isolated tenant created | `2026-03-15T18:08:35Z` | `../evidence/api/w6-live-11-tenant2-signup-request.json`, `../evidence/api/w6-live-11-tenant2-signup-response.json` |
| 9 | `GET` | `/api/remediation-runs/49103000-1104-4a36-8757-8e243e883dc5` | none with second-tenant token | `404` | Wrong-tenant run detail denied | `2026-03-15T18:08:40Z` | `../evidence/api/w6-live-11-wrong-tenant-run-detail-response.json` |
| 10 | `GET` | `/api/action-groups/a02f5fa8-4b27-4e2d-8c4b-70621ea557a3/runs` | none with second-tenant token | `200` | Wrong-tenant group-run list returned an empty set rather than tenant-A data | `2026-03-15T18:08:40Z` | `../evidence/api/w6-live-11-wrong-tenant-group-runs-response.json` |
| 11 | `GET` | `/api/actions/d0daa0c3-4a22-4dfc-9db2-aef91ab9c27c/remediation-options` | none with second-tenant token | `404` | Wrong-tenant action options denied | `2026-03-15T18:08:40Z` | `../evidence/api/w6-live-11-wrong-tenant-options-response.json` |
| 12 | `GET` | `/api/remediation-runs/49103000-1104-4a36-8757-8e243e883dc5` and `/api/remediation-runs/837fccdc-a51e-4b1f-a8d0-ed7cc6eea3a3` | none | `200` | Single-run and grouped run details both persisted canonical resolution state | `2026-03-15T18:08:45Z` | `../evidence/api/w6-live-10-config-local-run-detail.json`, `../evidence/api/w6-live-07-s3-9-group-run-detail.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `pass` — archived SaaS PR-bundle plan/apply routes remained `410`, and customer-run bundle artifacts remained the supported path.
- Negative path: `pass` — sampled unauthorized and wrong-tenant read surfaces denied access; wrong-tenant archived execute stayed `410` because the route is archived before tenant scoping.
- Auth boundary: `pass` — no sampled Wave 6 read surface leaked first-tenant data to the second tenant.
- Contract shape: `pass` — single-run `artifacts.resolution` and grouped `group_bundle` canonical resolution fields persisted correctly.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — archived-route, auth-boundary, account-metadata, and resolution artifacts were all saved.

## Result

- Status: `PARTIAL`
- Severity (if issue found): `🟡 MEDIUM`
- Primary tracker mapping: `Wave 6 / W6-LIVE-11`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- `direct_fix` remained out of scope and unchanged for the sampled Wave 6 families: their `mode_options` stayed `['pr_only']`.
- The archived execute/apply routes do not tenant-scope before returning `410`, which is acceptable for the archived boundary but should not be confused with tenant-specific authorization logic.

