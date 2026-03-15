# Test 03 - grouped callback mixed executable plus non-executable reporting

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T13:42:32Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18010`
- Branch tested: `master`
- Commit / HEAD: `7eee3cbb57ee99fa9866d811aa5f1bdf5f428a73`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `fbdc7dfe-4aad-4cf3-b6ba-078aa4d8476a`
- AWS Account: `target=696505809372`, `isolated runtime queues/caller identity=029037611564`
- Region(s): `eu-north-1`
- Required prior artifacts:
  - group run `f31c9c99-f24f-4536-8774-abff4a765eab`
  - remediation run `75379cc5-6322-4735-b86f-e6b3719fe4d4`
  - reporting callback URL `http://127.0.0.1:18010/api/internal/group-runs/report`
  - mixed payload containing `action_results[]` for `bb487cfd-2d28-41a6-8ec3-5f685e4eaa26` and `non_executable_results[]` for `47c023ae-945c-42bf-9b44-018d276046fa`

## Steps Executed

1. Queried the grouped run list after bundle generation but before any callback finalization attempt.
2. Posted a real `started` callback using the live reporting token returned from the grouped bundle response.
3. Posted a real mixed `finished` callback containing both executable `action_results[]` and review-required `non_executable_results[]`.
4. Queried the grouped run list again after callback finalization and fetched the remediation-run detail.
5. Queried `action_group_run_results` directly in the isolated database for the same `group_run_id`.

## API Evidence

| # | Method | Endpoint | HTTP | Observed | Artifact Path |
|---|---|---|---|---|---|
| 1 | `GET` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804/runs` | `200` | Before the mixed `finished` callback, the latest `download_bundle` run was `started` with `finished_at=null` and `reporting_source=system` | [../evidence/api/rpw5-post-archive-group-runs-before-callback-finish.json](../evidence/api/rpw5-post-archive-group-runs-before-callback-finish.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 2 | `POST` | `/api/internal/group-runs/report` | `200` | `started` callback accepted on the callback-managed group run | [../evidence/api/rpw5-post-archive-03-callback-started-request.json](../evidence/api/rpw5-post-archive-03-callback-started-request.json), [../evidence/api/rpw5-post-archive-03-callback-started-response.json](../evidence/api/rpw5-post-archive-03-callback-started-response.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 3 | `POST` | `/api/internal/group-runs/report` | `200` | First valid mixed `finished` callback accepted; no replay rejection occurred on the first finish | [../evidence/api/rpw5-post-archive-03-callback-finished-request.json](../evidence/api/rpw5-post-archive-03-callback-finished-request.json), [../evidence/api/rpw5-post-archive-03-callback-finished-response.json](../evidence/api/rpw5-post-archive-03-callback-finished-response.json), [../evidence/api/rpw5-post-archive-03-status-summary.json](../evidence/api/rpw5-post-archive-03-status-summary.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 4 | `GET` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804/runs` | `200` | After the callback, the run finalized as `finished` with `reporting_source=bundle_callback` | [../evidence/api/rpw5-post-archive-group-runs-after-callback.json](../evidence/api/rpw5-post-archive-group-runs-after-callback.json) |
| 5 | `GET` | `/api/remediation-runs/75379cc5-6322-4735-b86f-e6b3719fe4d4` | `200` | Remediation run stayed `success`; grouped reporting metadata remained attached | [../evidence/api/rpw5-post-archive-remediation-run-after-callback.json](../evidence/api/rpw5-post-archive-remediation-run-after-callback.json) |
| 6 | `SQL` | `action_group_run_results` for `group_run_id=f31c9c99-f24f-4536-8774-abff4a765eab` | `N/A` | Persisted one executable `success` result and one non-executable `unknown` row with `raw_result.result_type=non_executable` | [../evidence/api/rpw5-post-archive-group-run-results.json](../evidence/api/rpw5-post-archive-group-run-results.json) |

## Assertions

- First valid callback flow succeeds: `pass`
- ActionGroupRun is not prematurely terminal before the callback: `pass`
- Customer-run `started` callback is accepted: `pass`
- Executable actions persist through `action_results[]`: `pass`
- Review/manual actions persist through `non_executable_results[]`: `pass`
- Final callback finalizes the group run exactly once: `pass`
- No replay rejection occurs on the first valid finished callback: `pass`

## Result

- Status: `PASS`
- Severity (if issue found): `n/a`
- Primary tracker mapping: `Wave 5 / RPW5-POST-ARCHIVE-03`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- This rerun closes the remaining archived-SaaS Wave 5 blocker: callback-managed `download_bundle` runs now stay non-terminal after bundle generation, which lets the real customer mixed `finished` callback land exactly once.
- The persisted SQL evidence shows the expected split: executable action `bb487cfd-2d28-41a6-8ec3-5f685e4eaa26` recorded `execution_status=success`, while review-required action `47c023ae-945c-42bf-9b44-018d276046fa` recorded `execution_status=unknown` plus `raw_result.result_type=non_executable`.
