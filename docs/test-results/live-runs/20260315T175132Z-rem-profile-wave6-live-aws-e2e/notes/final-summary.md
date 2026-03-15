# Remediation-profile Wave 6 live AWS validation gate summary

- Wave: `Wave 6 control-family migration live AWS validation`
- Date (UTC): `2026-03-15T18:21:43Z`
- Environment used: `local master against isolated runtime`
- Branch tested: `master`
- Exact HEAD tested: `d7ac0cc648dea696fb384e98d77245e66fff94e5`
- AWS accounts and regions:
  - SaaS queue/runtime account `029037611564` in `eu-north-1`
  - Isolated AWS test account `696505809372` in `eu-north-1` and `us-east-1`
- Fresh/live data note: `Fresh ingest was used for this run; no restored live records were used.`
- Supported execution model exercised: `customer-run PR bundles only; archived public SaaS-managed plan/apply routes remained archived`

## Outcome Counts

- Pass: `0`
- Fail: `1`
- Partial: `2`
- Blocked: `8`

## Highest-Severity Findings

| Test | Severity | Issue | Evidence |
|---|---|---|---|
| `W6-LIVE-07` | `HIGH` | Grouped `POST /api/action-groups/{id}/bundle-run` returned `500` when the request depended on top-level-only `strategy_inputs` instead of failing closed with a validation response. | [`tests/w6-live-07.md`](../tests/w6-live-07.md), [`evidence/worker/api.log`](../evidence/worker/api.log) |
| `W6-LIVE-03` | `BLOCKING` | IAM.4 generic surfaces stayed metadata-only as intended, but the only authoritative execution route `/api/root-key-remediation-runs` was disabled in this isolated runtime. | [`tests/w6-live-03.md`](../tests/w6-live-03.md), [`evidence/api/w6-live-03-root-key-create-response.json`](../evidence/api/w6-live-03-root-key-create-response.json) |
| `W6-LIVE-01`, `W6-LIVE-06`, `W6-LIVE-08` | `BLOCKING` | Fresh live ingest produced no actionable EC2.53, S3.11, or S3.15 family records, so neither executable nor downgrade branches could be validated for those families. | [`evidence/aws/wave6-family-finding-counts.json`](../evidence/aws/wave6-family-finding-counts.json), [`evidence/api/wave6-action-inventory.txt`](../evidence/api/wave6-action-inventory.txt) |
| `W6-LIVE-10` | `BLOCKING` | Config.1 proved deterministic plus review branching product-side, but no operator-owned/test-account write credentials and no connected `role_write_arn` existed for manual bundle apply plus rollback proof. | [`tests/w6-live-10.md`](../tests/w6-live-10.md), [`evidence/api/accounts-list.json`](../evidence/api/accounts-list.json) |
| `W6-LIVE-04`, `W6-LIVE-05`, `W6-LIVE-09` | `BLOCKING` | S3.2, S3.5, and CloudTrail.1 only reached downgrade/manual or review tiers in the live isolated account; no family reached the required live executable proof bar. | [`tests/w6-live-04.md`](../tests/w6-live-04.md), [`tests/w6-live-05.md`](../tests/w6-live-05.md), [`tests/w6-live-09.md`](../tests/w6-live-09.md) |

## Family-by-Family Validation Status

| Family | Executable case proven | Downgrade/manual case proven | Status | Exact reason |
|---|---|---|---|---|
| `EC2.53` | `No` | `No` | `BLOCKED` | Fresh ingest produced no EC2.53 findings or remediation actions. |
| `IAM.4` | `No` | `Yes` | `BLOCKED` | Generic routes proved `manual_guidance_only`, but the authoritative root-key route was disabled, so no safe isolated execution case existed. |
| `S3.2` | `No` | `Yes` | `BLOCKED` | Manual-preservation downgrade branch was proven; no live executable branch was available in this account. |
| `S3.5` | `No` | `Yes` | `BLOCKED` | Review-required preservation gating was proven; executable output stayed blocked by missing preservation evidence and `AccessDenied`. |
| `S3.11` | `No` | `No` | `BLOCKED` | Fresh ingest produced no S3.11 findings or remediation actions. |
| `S3.9` | `No` | `Yes` | `FAIL` | Review-tier grouped output was proven, but the grouped-create route threw a real `500`, and no destination-safe executable branch was available. |
| `S3.15` | `No` | `No` | `BLOCKED` | Fresh ingest produced no S3.15 findings or remediation actions. |
| `CloudTrail.1` | `No` | `Yes` | `BLOCKED` | Tenant defaults were consumed, but the live case still downgraded to review tier because bucket verification returned `403`. |
| `Config.1` | `No` | `Yes` | `BLOCKED` | Deterministic plus downgrade branching was proven product-side, but manual apply and rollback were impossible without target-account write credentials. |

## Exact Executable Cases Proven

- None met the Wave 6 live-AWS executable proof bar.
- Product-side deterministic-only case observed but not counted as live executable proof:
  - `Config.1` `config_enable_account_local_delivery` on action `d0daa0c3-4a22-4dfc-9db2-aef91ab9c27c`
  - Preview/create/run detail persisted `deterministic_bundle`
  - The generated customer-run bundle was downloaded and inspected
  - Manual operator-run apply plus rollback could not be executed because the isolated account was connected read-only (`role_write_arn = null`)

## Exact Downgrade / Review / Manual Cases Proven

- `IAM.4` action `207c4d45-bd8e-49ba-b4d5-9f2f860e1696`
  - `iam_root_key_disable` stayed `manual_guidance_only`
  - Generic create failed closed with `reason=root_key_execution_authority`
- `S3.2` action `f081ae21-1114-4a0e-8af3-e5a308615d34`
  - `s3_bucket_block_public_access_manual_preservation` resolved `manual_guidance_only`
  - Run `cd5a4eb4-4ecb-4aa5-9367-6876a8c7c834` persisted the manual tier
- `S3.5` action `e6ee1990-bf42-4134-a2ed-cfa0d2287577`
  - Resolver/create persisted `review_required_bundle`
  - Run `dfd14fde-5744-4b05-81af-7248c6a5d466` generated a non-executable guidance bundle
- `S3.9` group `a02f5fa8-4b27-4e2d-8c4b-70621ea557a3`
  - Actions `d7f868c5-9a64-4aca-bff0-aabb06b3c104` and `bee5888e-8c14-43f2-87f6-77b9fcd8c4aa`
  - Group run `19c522c0-9256-4124-8b39-42b707bdd812` / remediation run `837fccdc-a51e-4b1f-a8d0-ed7cc6eea3a3`
  - Grouped bundle persisted `review_required_metadata_only` with `runnable_action_count = 0`
- `CloudTrail.1` action `4c4f4b3b-90d5-4682-a94a-1cfdc673bdc6`
  - `cloudtrail_enable_guided` consumed the tenant default bucket but still downgraded to `review_required_bundle`
  - Run `cb6a9e54-3660-4bc5-9a63-452fa7934362` persisted the review tier
- `Config.1` action `d0daa0c3-4a22-4dfc-9db2-aef91ab9c27c`
  - `config_enable_centralized_delivery` consumed the tenant default bucket and downgraded to `review_required_bundle`
  - Run `e1a04e3f-d39e-47d5-b6ab-1539af58a2f5` persisted the review tier

## Observed Runtime vs Planned Validation Contract

- The grouped S3.9 bundle emitted the expected grouped-manifest contract:
  - `bundle_manifest.json`
  - `decision_log.md`
  - `finding_coverage.json`
  - `README_GROUP.txt`
  - `run_all.sh`
- Single-run bundles on current `master` did not emit that grouped-manifest file set.
- Instead, single-run bundles emitted the observed legacy shapes:
  - executable/review Terraform bundles with `README.txt` plus Terraform files
  - manual-guidance bundles with `README.txt`, `decision.json`, and `pr_automation/*`
- This summary treats observed runtime behavior as authoritative over the prior validation expectation.

## Rollback and Cleanup Status

- Target-account AWS mutation status: `none`
- AWS rollback commands used for target-account resources: `none`
- Local cleanup completed:
  - backend session stopped
  - worker session stopped
  - disposable Postgres stopped
  - five temporary SQS queues deleted from SaaS account `029037611564`
  - queue deletion verified with `NonExistentQueue` probes
- Final cleanup summary: [`notes/aws-cleanup-summary.md`](./aws-cleanup-summary.md)
- Intentionally retained AWS resources: `none`

## Recommended Gate Decision

- Recommended gate decision: `stop for fixes`
- Wave 6 complete: `no`
- Ready for post-validation docs/claim updates: `no`
- Rationale:
  - no migrated family satisfied both required proofs: one live executable case plus one live downgrade/manual case
  - `IAM.4` is explicitly blocked by the disabled authoritative root-key route
  - `EC2.53`, `S3.11`, and `S3.15` had no live family scenarios in the fresh isolated ingest
  - `S3.9` exposed a real `500` on the grouped-create path
  - `Config.1` lacked the operator-owned/test-account write path needed for manual apply plus rollback proof
  - no executable case changed AWS state, so no family can be claimed shipped on live AWS from this run
