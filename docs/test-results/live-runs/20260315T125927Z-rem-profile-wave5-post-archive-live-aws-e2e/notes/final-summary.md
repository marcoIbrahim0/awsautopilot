# Wave 5 Post-Archive Summary

- Wave: `Remediation-profile Wave 5 post-archive live AWS validation`
- Date (UTC): `2026-03-15T13:13:39Z`
- Tests in wave: `RPW5-POST-ARCHIVE-01` through `RPW5-POST-ARCHIVE-05`
- Environment used: `local master HEAD 4f676b932139 against an isolated local runtime (backend http://127.0.0.1:18008, isolated Postgres on 127.0.0.1:55434, isolated SQS queues in account 029037611564) plus restored March 15, 2026 AWS-backed S3.9 records for the isolated target AWS account`
- Branch tested: `master`
- AWS account used: `target=696505809372`, `isolated runtime queues/caller identity=029037611564`
- Regions used: `eu-north-1`

## Outcome Counts

- Pass: `4`
- Fail: `1`
- Partial: `0`
- Blocked: `0`

## Highest Severity Findings

| Test | Severity | Issue |
|---|---|---|
| `RPW5-POST-ARCHIVE-03` | `🔴 BLOCKING` | The worker still finalizes `download_bundle` `ActionGroupRun` rows at bundle-generation time, so a later mixed `finished` callback from the customer-run bundle is replay-rejected before executable and non-executable results can persist. |

## Exact Wave 5 Contracts Proven Under The Archived-SaaS Model

- `RPW5-POST-ARCHIVE-01` passed.
  - A real mixed-tier executable grouped bundle was generated on current `master` using restored March 15, 2026 AWS-backed S3.9 records.
  - `bundle_manifest.json` existed and declared one runnable executable action plus one review-required non-executable action.
  - The on-disk bundle contained both `executable/actions/...` and `review_required/actions/...`.
- `RPW5-POST-ARCHIVE-02` passed.
  - `run_all.sh` was a reporting wrapper and `run_actions.sh` hardcoded `EXECUTION_ROOT="executable/actions"`.
  - Review-required output was metadata only.
  - `decision_log.md`, `finding_coverage.json`, and `README_GROUP.txt` enumerated the full grouped action set.
- `RPW5-POST-ARCHIVE-04` passed.
  - Invalid reporting tokens returned `401`.
  - Wrong-tenant access to the first tenant’s group detail, remediation run detail, and bundle-run create route was denied.
  - Wrong-tenant list access returned empty results only and leaked no foreign data.
  - Replayed valid mixed `finished` callback payloads were rejected with `409 reason=group_run_report_replay`.
- `RPW5-POST-ARCHIVE-05` passed.
  - All four archived public SaaS PR-bundle execution routes returned the explicit `410` archived response.
  - Current docs and the generated bundle both point operators to the customer-run path instead of SaaS-managed execution.

## Not Proven / Remaining Blockers

- `RPW5-POST-ARCHIVE-03` failed.
  - The live `started` callback succeeded, but the first real mixed `finished` callback did not.
  - By the time the callback was posted, the latest `download_bundle` group run was already `finished` with `reporting_source=system`.
  - The mixed `finished` callback returned `409 reason=group_run_report_replay`.
  - `action_group_run_results` remained empty, so executable and non-executable persistence could not be proven on the supported customer-run ordering.
- Fresh isolated ingest against account `696505809372` remains blocked by target-account IAM trust.
  - `arn:aws:iam::696505809372:role/SecurityAutopilotReadRole` currently rejects the SaaS account with `AccessDenied`.
  - This did not block the narrowed product proof because the exact March 15, 2026 live-ingested S3.9 records were restored into the isolated runtime.

## Recommended Gate Decision

- `Stop for fixes`
- Rationale:
  - The narrowed post-archive gate requires `RPW5-POST-ARCHIVE-01` through `RPW5-POST-ARCHIVE-04` to pass.
  - `RPW5-POST-ARCHIVE-03` is a real product failure on current `master`, not a test-environment-only gap.
  - Wave 5 is therefore **not complete yet** under the archived-SaaS product model.

## Run Package

- Test records:
  - [../tests/rpw5-post-archive-01.md](../tests/rpw5-post-archive-01.md)
  - [../tests/rpw5-post-archive-02.md](../tests/rpw5-post-archive-02.md)
  - [../tests/rpw5-post-archive-03.md](../tests/rpw5-post-archive-03.md)
  - [../tests/rpw5-post-archive-04.md](../tests/rpw5-post-archive-04.md)
  - [../tests/rpw5-post-archive-05.md](../tests/rpw5-post-archive-05.md)
- Cleanup:
  - [aws-cleanup-summary.md](../notes/aws-cleanup-summary.md)
