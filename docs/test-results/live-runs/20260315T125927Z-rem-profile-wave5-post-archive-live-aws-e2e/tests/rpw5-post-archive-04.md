# Test 04 - callback replay protection and auth boundaries

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T13:10:07Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18008`
- Branch tested: `master`

## Preconditions

- Primary tenant: `3f392e92-069a-47f7-884e-985d5e5ed035`
- Secondary tenant: `e63b300c-faa4-4254-a8d3-2bff64869a0f`
- AWS Account: `target=696505809372`, `isolated runtime queues/caller identity=029037611564`
- Region(s): `eu-north-1`
- Required prior artifacts:
  - primary group `75cd4f50-97c9-4aa0-911b-eb3b17ffd804`
  - primary remediation run `7a7f38cb-10f4-4166-9fa8-03d0e169fcd1`
  - primary reporting token from the live grouped run

## Steps Executed

1. Signed up a second isolated tenant/admin user in the same runtime.
2. Posted an invalid callback token to `/api/internal/group-runs/report`.
3. Used the second tenant token against the first tenant’s group detail, group runs, remediation run detail, and bundle-run create surfaces.
4. Replayed the same valid mixed `finished` callback payload against the already-finalized group run.

## API Evidence

| # | Method | Endpoint | HTTP | Observed | Artifact Path |
|---|---|---|---|---|---|
| 1 | `POST` | `/api/auth/signup` | `201` | Second tenant/admin created successfully | [../evidence/api/signup-second-tenant-request.json](../evidence/api/signup-second-tenant-request.json), [../evidence/api/signup-second-tenant-response.json](../evidence/api/signup-second-tenant-response.json) |
| 2 | `POST` | `/api/internal/group-runs/report` | `401` | Invalid reporting token denied | [../evidence/api/rpw5-post-archive-04-invalid-token-request.json](../evidence/api/rpw5-post-archive-04-invalid-token-request.json), [../evidence/api/rpw5-post-archive-04-invalid-token-response.json](../evidence/api/rpw5-post-archive-04-invalid-token-response.json) |
| 3 | `GET` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804` | `404` | Wrong-tenant direct group detail access denied | [../evidence/api/rpw5-post-archive-04-wrong-tenant-group-detail.json](../evidence/api/rpw5-post-archive-04-wrong-tenant-group-detail.json) |
| 4 | `GET` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804/runs` | `200` | Wrong-tenant group-run list returned an empty set only | [../evidence/api/rpw5-post-archive-04-wrong-tenant-group-runs.json](../evidence/api/rpw5-post-archive-04-wrong-tenant-group-runs.json) |
| 5 | `GET` | `/api/remediation-runs/7a7f38cb-10f4-4166-9fa8-03d0e169fcd1` | `404` | Wrong-tenant remediation run detail access denied | [../evidence/api/rpw5-post-archive-04-wrong-tenant-run-detail.json](../evidence/api/rpw5-post-archive-04-wrong-tenant-run-detail.json) |
| 6 | `POST` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804/bundle-run` | `404` | Wrong-tenant bundle-run creation denied | [../evidence/api/rpw5-post-archive-04-wrong-tenant-bundle-run-create.json](../evidence/api/rpw5-post-archive-04-wrong-tenant-bundle-run-create.json) |
| 7 | `POST` | `/api/internal/group-runs/report` | `409` | Replayed valid mixed `finished` callback rejected with `reason=group_run_report_replay` | [../evidence/api/rpw5-post-archive-04-replay-request.json](../evidence/api/rpw5-post-archive-04-replay-request.json), [../evidence/api/rpw5-post-archive-04-replay-response.json](../evidence/api/rpw5-post-archive-04-replay-response.json) |
| 8 | `summary` | auth/replay probe rollup | `N/A` | Collected exact status codes for invalid token, wrong-tenant surfaces, and replay rejection | [../evidence/api/rpw5-post-archive-03-04-status-summary.json](../evidence/api/rpw5-post-archive-03-04-status-summary.json) |

## Assertions

- Invalid callback token returns `401`: `pass`
- Wrong-tenant access is denied: `pass`
- Replayed valid finished callback is rejected with a non-200 response: `pass`
- No cross-tenant leakage occurs in tested surfaces: `pass`

## Result

- Status: `PASS`
- Severity (if issue found): `n/a`
- Primary tracker mapping: `Wave 5 / RPW5-POST-ARCHIVE-04`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- The wrong-tenant `group-runs` list denied access by returning `{"items":[],"total":0}` rather than leaking the first tenant’s row.
- This auth/replay proof does not close `RPW5-POST-ARCHIVE-03`; the replay guard works deny-closed, but the customer-run mixed `finished` callback still cannot land after bundle generation on current `master`.
