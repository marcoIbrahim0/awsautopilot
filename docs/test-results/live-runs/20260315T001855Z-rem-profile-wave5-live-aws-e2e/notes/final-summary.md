# Wave 5 Summary

- Wave: `Remediation-profile Wave 5 live AWS validation`
- Date (UTC): `2026-03-15T00:44:30Z`
- Tests in wave: `RPW5-LIVE-01` through `RPW5-LIVE-08`
- Environment used: `local master against an isolated local runtime (backend/worker on http://127.0.0.1:18004 with isolated Postgres + isolated SQS) and a real isolated AWS account`
- Branch tested: `master`
- AWS account used: `696505809372`
- Regions used: `eu-north-1` for grouped Wave 5 bundle generation and runtime-risk probes; `us-east-1` plus `eu-north-1` for the real ingest proof

## Outcome Counts

- Pass: `2`
- Fail: `1`
- Partial: `1`
- Blocked: `4`

## Highest Severity Findings

| Test | Severity | Issue | Tracker Section/Row |
|---|---|---|---|
| `RPW5-LIVE-01` | `🔴 BLOCKING` | No real grouped family in the isolated live dataset produced the required mixed-tier split (`deterministic_bundle` plus `review_required_bundle` or `manual_guidance_only`). The available grouped families were all-review or hard-blocked. | `Wave 5 / RPW5-LIVE-01` |
| `RPW5-LIVE-03` / `RPW5-LIVE-04` / `RPW5-LIVE-06` | `🔴 BLOCKING` | The only connected AWS test account exposed `role_write_arn: null` in the isolated runtime, and the inferred standard `SecurityAutopilotWriteRole` was not assumable from the SaaS account. No SaaS plan/apply or live AWS mutation proof could be completed. | `Wave 5 / RPW5-LIVE-03-04-06` |
| `RPW5-LIVE-08` | `🟠 HIGH` | `POST /api/internal/group-runs/report` accepted a replay of the same valid finished callback token instead of rejecting it. Unauthorized and wrong-tenant probes denied correctly, but callback replay protection is missing. | `Wave 5 / RPW5-LIVE-08` |
| `Setup-only observation` | `🟡 MEDIUM` | Fresh isolated DB bootstrap hit an Alembic ordering bug at revision `0034_remediation_runs_active_unique_guard`, and `/api/aws/accounts/{id}/validate` returned `500` on current `master` because the AWS Config probe sends an invalid `Limit` parameter. | `Wave 5 setup` |

## Exact Wave 5 Contracts Proven

- Real AWS-backed ingest works in the isolated local runtime with the connected ReadRole.
  - `1010` Security Hub findings were ingested from the real AWS account (`371` in `eu-north-1`, `639` in `us-east-1`).
- Mixed-tier layout semantics are present in generated grouped bundles.
  - The generated grouped bundle used `layout_version = grouped_bundle_mixed_tier/v1`.
  - `bundle_manifest.json` declared `execution_root = executable/actions`.
  - `run_all.sh` delegated only to `run_actions.sh`, and `run_actions.sh` only searched `executable/actions`.
  - Review-only folders were emitted under `review_required/actions/...` and were not treated as Terraform execution roots.
- Zero-executable grouped behavior is explicit and non-500.
  - A real AWS-backed EBS grouped run generated a zero-executable mixed-tier layout with `review_required/actions/...` metadata only.
  - `POST /api/remediation-runs/{run_id}/execute-pr-bundle` returned a precise `400` with `reason = no_executable_bundle`, not a `500`.
- Grouped callback additive reporting accepts `non_executable_results[]`.
  - A live callback using the generated reporting token accepted `started` and `finished` events.
  - `action_group_run_results` rows persisted `raw_result.result_type = non_executable` for both review-only actions.
  - The group run finished with `reporting_source = bundle_callback`.

## Not Proven

- No real mixed-tier executable grouped bundle was found in this isolated live dataset.
- No SaaS plan/apply execution on a mixed-tier executable grouped bundle was possible.
- No all-executable grouped live-AWS path was available.
- No live AWS mutation plus AWS-side rollback proof was possible.
- Callback handling with both `action_results[]` and `non_executable_results[]` in the same live grouped run was not provable because no executable grouped family existed.

## Real AWS Account Findings That Blocked The Gate

- `ebs_snapshot_block_public_access`
  - With `risk_acknowledged=true`, both actions resolved to `review_required_bundle`, producing a zero-executable grouped bundle.
  - With `risk_acknowledged=false`, run creation returned `Risk acknowledgement required`.
- `s3_bucket_access_logging`
  - Both live actions exposed `risk_evaluation_not_specialized = unknown` in execution guidance, so the family is review-only when acknowledged.
  - One member is account-scoped (`AWS::::Account:696505809372`) rather than bucket-scoped.
- `s3_bucket_require_ssl`
  - The bucket-scoped action required review.
  - The account-scoped action failed live runtime checks with `Could not derive bucket name from action target` and `Missing bucket identifier for SSL policy analysis`.

## Exact AWS Mutations Verified

- No target AWS resources were mutated in account `696505809372`.
- Live AWS operations performed were read-only:
  - `sts:GetCallerIdentity` on the SaaS/operator account
  - `sts:AssumeRole` into `arn:aws:iam::696505809372:role/SecurityAutopilotReadRole`
  - Security Hub ingest reads in `eu-north-1` and `us-east-1`
  - Runtime risk probes through the ReadRole during grouped-run creation

## Rollback / Cleanup Status

- Target-account rollback required: `none`
- Target-account rollback executed: `none`
- Target-account final state: `no live AWS mutations were applied`
- Isolated runtime cleanup:
  - deleted temporary SQS queues `security-autopilot-rpw5-20260315t001855z-ingest` and `security-autopilot-rpw5-20260315t001855z-contract-quarantine`
  - stopped the isolated backend and worker
  - stopped and removed the disposable Postgres cluster at `/tmp/rpw5-pg-20260315T001855Z`
- Intentionally retained resources: `none`

## Tracker Maintenance

- Quick Status Board updated: `no`
- Section 8 go-live blocker checkboxes updated: `no`
- Section 9 changelog entries added for retests: `no`

## Wave Exit Decision

- `Stop for fixes`
- Rationale:
  - `RPW5-LIVE-08` failed because callback replay tokens were accepted.
  - `RPW5-LIVE-01`, `RPW5-LIVE-03`, `RPW5-LIVE-04`, and `RPW5-LIVE-06` were blocked by the current isolated AWS account and data shape: no true mixed-tier executable grouped family existed, and no connected WriteRole was available for executor plan/apply.
  - Wave 5 is not ready for Wave 6 on the basis of this run.
