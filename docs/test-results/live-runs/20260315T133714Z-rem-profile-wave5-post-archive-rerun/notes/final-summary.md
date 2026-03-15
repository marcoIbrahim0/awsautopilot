# Wave 5 Post-Archive Rerun Summary

- Wave: `Remediation-profile Wave 5 post-archive narrowed rerun`
- Date (UTC): `2026-03-15T13:45:21Z`
- Tests in wave: `RPW5-POST-ARCHIVE-01` through `RPW5-POST-ARCHIVE-05`
- Environment used: `local master HEAD 7eee3cbb57ee99fa9866d811aa5f1bdf5f428a73 against an isolated local runtime (backend http://127.0.0.1:18010, isolated Postgres on 127.0.0.1:55435, isolated SQS queues in account 029037611564) plus restored March 15, 2026 AWS-backed S3.9 records for the isolated target AWS account`
- Branch tested: `master`
- Exact rerun commit / HEAD: `7eee3cbb57ee99fa9866d811aa5f1bdf5f428a73`
- AWS account used: `target=696505809372`, `isolated runtime queues/caller identity=029037611564`
- Regions used: `eu-north-1`

## Outcome Counts

- Pass: `5`
- Fail: `0`
- Partial: `0`
- Blocked: `0`

## Highest Severity Findings

- `none`

## Exact Wave 5 Contracts Proven Under The Archived-SaaS Model

- `RPW5-POST-ARCHIVE-01` passed.
  - A real mixed-tier executable grouped bundle was generated on current `master` using restored March 15, 2026 AWS-backed S3.9 records.
  - `bundle_manifest.json` declared one runnable executable action plus one review-required non-executable action.
  - The on-disk bundle contained both `executable/actions/...` and `review_required/actions/...`.
- `RPW5-POST-ARCHIVE-02` passed.
  - `run_all.sh` remained the customer-run/reporting wrapper.
  - `run_actions.sh` hardcoded `EXECUTION_ROOT="executable/actions"`.
  - Review-required output stayed metadata only.
  - `bundle_manifest.json`, `decision_log.md`, `finding_coverage.json`, and `README_GROUP.txt` all remained present.
- `RPW5-POST-ARCHIVE-03` passed.
  - Successful bundle generation no longer marked the callback-managed `ActionGroupRun` terminal immediately.
  - Before callback finalization, the latest grouped `download_bundle` run stayed `started` with `finished_at=null`.
  - The first valid `started` callback returned `200`.
  - The first valid mixed `finished` callback returned `200`, persisted executable `action_results[]` plus review-required `non_executable_results[]`, and finalized the group run exactly once.
  - `action_group_run_results` persisted one executable `success` row and one non-executable `unknown` row with `raw_result.result_type=non_executable`.
- `RPW5-POST-ARCHIVE-04` passed.
  - Invalid reporting tokens returned `401`.
  - Wrong-tenant access to the first tenant’s group detail, remediation run detail, and bundle-run create route was denied.
  - Wrong-tenant list access returned empty results only and leaked no foreign data.
  - Replayed valid mixed `finished` callback payloads were rejected with `409 reason=group_run_report_replay` after the first successful finalization.
- `RPW5-POST-ARCHIVE-05` passed.
  - All four archived public SaaS PR-bundle execution routes returned the explicit `410` archived response.
  - Current API behavior and the generated bundle still point operators to the customer-run path instead of SaaS-managed execution.

## Remaining Non-Gate Caveats

- Fresh isolated ingest against account `696505809372` is still blocked by target-account IAM trust.
  - `arn:aws:iam::696505809372:role/SecurityAutopilotReadRole` continues to reject the SaaS account with `AccessDenied`.
  - This did not block the narrowed archived-SaaS proof because the exact March 15, 2026 AWS-backed S3.9 records were restored into the isolated runtime and the current API/worker path was re-exercised end to end.
- The historical pre-fix package remains unchanged:
  - [20260315T125927Z-rem-profile-wave5-post-archive-live-aws-e2e](../../20260315T125927Z-rem-profile-wave5-post-archive-live-aws-e2e/notes/final-summary.md)

## Recommended Gate Decision

- `Wave 5 complete under the archived-SaaS product model`
- Rationale:
  - `RPW5-POST-ARCHIVE-01` through `RPW5-POST-ARCHIVE-05` all passed on current `master`.
  - The remaining product blocker from the earlier narrowed gate, `RPW5-POST-ARCHIVE-03`, now passes end to end with fresh live callback evidence and persisted mixed result rows.

## Run Package

- Test records:
  - [../tests/rpw5-post-archive-01.md](../tests/rpw5-post-archive-01.md)
  - [../tests/rpw5-post-archive-02.md](../tests/rpw5-post-archive-02.md)
  - [../tests/rpw5-post-archive-03.md](../tests/rpw5-post-archive-03.md)
  - [../tests/rpw5-post-archive-04.md](../tests/rpw5-post-archive-04.md)
  - [../tests/rpw5-post-archive-05.md](../tests/rpw5-post-archive-05.md)
- Cleanup:
  - [aws-cleanup-summary.md](aws-cleanup-summary.md)
