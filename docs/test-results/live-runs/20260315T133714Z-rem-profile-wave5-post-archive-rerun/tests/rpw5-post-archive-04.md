# Test 04 - callback replay protection and auth boundaries regression

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T13:43:15Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18010`
- Branch tested: `master`
- Commit / HEAD: `7eee3cbb57ee99fa9866d811aa5f1bdf5f428a73`

## Preconditions

- Primary tenant: `fbdc7dfe-4aad-4cf3-b6ba-078aa4d8476a`
- Secondary tenant: `5a9d3b3a-8989-4953-a271-e4703447498f`
- AWS Account: `target=696505809372`, `isolated runtime queues/caller identity=029037611564`
- Region(s): `eu-north-1`
- Required prior artifacts:
  - primary group `75cd4f50-97c9-4aa0-911b-eb3b17ffd804`
  - primary remediation run `75379cc5-6322-4735-b86f-e6b3719fe4d4`
  - primary reporting token from the live grouped run

## Steps Executed

1. Signed up a second isolated tenant/admin user in the same runtime.
2. Posted an invalid callback token to `/api/internal/group-runs/report`.
3. Used the second tenant token against the first tenant’s group detail, group runs, remediation run detail, group list, and bundle-run create surfaces.
4. Replayed the same valid mixed `finished` callback payload after the first successful finalization from Test 03.

## API Evidence

| # | Method | Endpoint | HTTP | Observed | Artifact Path |
|---|---|---|---|---|---|
| 1 | `POST` | `/api/auth/signup` | `201` | Second tenant/admin created successfully | [../evidence/api/signup-second-tenant-request.json](../evidence/api/signup-second-tenant-request.json), [../evidence/api/signup-second-tenant-response.json](../evidence/api/signup-second-tenant-response.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 2 | `POST` | `/api/internal/group-runs/report` | `401` | Invalid reporting token denied | [../evidence/api/rpw5-post-archive-04-invalid-token-request.json](../evidence/api/rpw5-post-archive-04-invalid-token-request.json), [../evidence/api/rpw5-post-archive-04-invalid-token-response.json](../evidence/api/rpw5-post-archive-04-invalid-token-response.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 3 | `GET` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804` | `404` | Wrong-tenant direct group detail access denied | [../evidence/api/rpw5-post-archive-04-wrong-tenant-group-detail.json](../evidence/api/rpw5-post-archive-04-wrong-tenant-group-detail.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 4 | `GET` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804/runs` | `200` | Wrong-tenant group-run list returned an empty set only | [../evidence/api/rpw5-post-archive-04-wrong-tenant-group-runs.json](../evidence/api/rpw5-post-archive-04-wrong-tenant-group-runs.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 5 | `GET` | `/api/remediation-runs/75379cc5-6322-4735-b86f-e6b3719fe4d4` | `404` | Wrong-tenant remediation run detail access denied | [../evidence/api/rpw5-post-archive-04-wrong-tenant-run-detail.json](../evidence/api/rpw5-post-archive-04-wrong-tenant-run-detail.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 6 | `GET` | `/api/action-groups` | `200` | Second-tenant group list stayed empty and leaked no foreign data | [../evidence/api/rpw5-post-archive-04-second-tenant-group-list.json](../evidence/api/rpw5-post-archive-04-second-tenant-group-list.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 7 | `POST` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804/bundle-run` | `404` | Wrong-tenant bundle-run creation denied | [../evidence/api/rpw5-post-archive-04-wrong-tenant-bundle-run-create.json](../evidence/api/rpw5-post-archive-04-wrong-tenant-bundle-run-create.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 8 | `POST` | `/api/internal/group-runs/report` | `409` | Replayed valid mixed `finished` callback rejected with `reason=group_run_report_replay` after the first real finalization | [../evidence/api/rpw5-post-archive-04-replay-request.json](../evidence/api/rpw5-post-archive-04-replay-request.json), [../evidence/api/rpw5-post-archive-04-replay-response.json](../evidence/api/rpw5-post-archive-04-replay-response.json), [../evidence/api/rpw5-post-archive-03-04-status-summary.json](../evidence/api/rpw5-post-archive-03-04-status-summary.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |

## Assertions

- Invalid callback token returns `401`: `pass`
- Wrong-tenant access is denied on direct detail and create routes: `pass`
- Wrong-tenant list access returns empty results only: `pass`
- Replayed valid finished callback is rejected after true finalization: `pass`
- No cross-tenant leakage occurs in the tested surfaces: `pass`

## Result

- Status: `PASS`
- Severity (if issue found): `n/a`
- Primary tracker mapping: `Wave 5 / RPW5-POST-ARCHIVE-04`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- The replay guard is still deny-closed, but it now triggers only after the first valid mixed `finished` callback has already persisted results and finalized the group run.
- The wrong-tenant `group-runs` and `action-groups` list surfaces returned empty payloads instead of leaking any foreign rows.
