# Test 03 - grouped callback mixed executable plus non-executable reporting

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T13:05:43Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18008`
- Branch tested: `master`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `3f392e92-069a-47f7-884e-985d5e5ed035`
- AWS Account: `target=696505809372`, `isolated runtime queues/caller identity=029037611564`
- Region(s): `eu-north-1`
- Required prior artifacts:
  - group run `6de0f03c-58c2-4c5f-8739-dfdd9ee51eff`
  - reporting token/callback URL returned from `bundle-run`
  - mixed payload containing `action_results[]` for `bb487cfd-2d28-41a6-8ec3-5f685e4eaa26` and `non_executable_results[]` for `47c023ae-945c-42bf-9b44-018d276046fa`

## Steps Executed

1. Posted a real `started` callback using the live reporting token from the generated bundle.
2. Queried the group-run list before attempting the mixed `finished` callback.
3. Posted a real mixed `finished` callback containing both:
   - executable `action_results[]`
   - review-required `non_executable_results[]`
4. Queried the group-run list again after the callback attempt.
5. Queried `action_group_run_results` directly in the isolated database for the same `group_run_id`.

## API Evidence

| # | Method | Endpoint | HTTP | Observed | Artifact Path |
|---|---|---|---|---|---|
| 1 | `POST` | `/api/internal/group-runs/report` | `200` | `started` callback accepted | [../evidence/api/rpw5-post-archive-03-callback-started-request.json](../evidence/api/rpw5-post-archive-03-callback-started-request.json), [../evidence/api/rpw5-post-archive-03-callback-started-response.json](../evidence/api/rpw5-post-archive-03-callback-started-response.json) |
| 2 | `GET` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804/runs` | `200` | Before the mixed `finished` callback, the latest `download_bundle` run was already `finished` with `reporting_source=system` | [../evidence/api/rpw5-post-archive-group-runs-before-callback-finish.json](../evidence/api/rpw5-post-archive-group-runs-before-callback-finish.json) |
| 3 | `POST` | `/api/internal/group-runs/report` | `409` | Mixed `finished` callback was rejected as `group_run_report_replay` | [../evidence/api/rpw5-post-archive-03-callback-finished-request.json](../evidence/api/rpw5-post-archive-03-callback-finished-request.json), [../evidence/api/rpw5-post-archive-03-callback-finished-response.json](../evidence/api/rpw5-post-archive-03-callback-finished-response.json) |
| 4 | `GET` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804/runs` | `200` | Run remained `finished`; `reporting_source` changed to `bundle_callback`, but no per-action finish results were stored | [../evidence/api/rpw5-post-archive-group-runs-after-callback.json](../evidence/api/rpw5-post-archive-group-runs-after-callback.json) |
| 5 | `SQL` | `action_group_run_results` for `group_run_id=6de0f03c-58c2-4c5f-8739-dfdd9ee51eff` | `N/A` | Persisted results were empty | [../evidence/api/rpw5-post-archive-group-run-results.json](../evidence/api/rpw5-post-archive-group-run-results.json) |

## Assertions

- First valid callback flow succeeds: `fail` — only the `started` event succeeded; the first mixed `finished` event was replay-rejected because the worker had already finalized the run.
- Executable actions report through `action_results[]`: `fail`
- Review/manual actions report through `non_executable_results[]`: `fail`
- Persisted results distinguish executable vs non-executable correctly: `fail`
- Overall group result is not failed solely because non-executable actions exist: `pass`

## Result

- Status: `FAIL`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 5 / RPW5-POST-ARCHIVE-03`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- Current `master` still auto-finalizes `download_bundle` `ActionGroupRun` rows at bundle-generation time through worker-side lifecycle sync. That consumes the real customer-run mixed `finished` callback path before executable and non-executable results can persist.
- This is the remaining narrowed Wave 5 blocker under the archived-SaaS model.
