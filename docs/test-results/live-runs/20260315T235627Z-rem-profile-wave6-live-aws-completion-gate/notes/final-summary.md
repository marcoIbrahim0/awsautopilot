# Remediation-profile Wave 6 final strict live AWS completion gate summary

- Wave: `Wave 6 strict completion gate`
- Date (UTC): `2026-03-16T13:10:00Z`
- Environment used: `local master against an isolated runtime plus a secondary root-key API instance on 127.0.0.1:18021`
- Branch tested: `master`
- Exact HEAD tested: `6278dfd6b22e5cec9f16753f076b5e6d417bd844`
- AWS accounts and regions:
  - SaaS queue/runtime account `029037611564` in `eu-north-1`
  - Isolated AWS test account `696505809372` in `eu-north-1`
- Shared production/customer AWS accounts used: `none`
- Supported execution model exercised: `customer-run PR bundles only`
- Archived public SaaS-managed execution exercised: `no`
- IAM.4 execution authority exercised: ``/api/root-key-remediation-runs`` only
- Retained seeded-resource note: `This run intentionally reused retained strict/environment-readiness fixtures in account 696505809372; each retained resource is called out in the per-test notes and cleanup summary.`

## Outcome Counts

- Pass: `4`
- Fail: `4`
- Partial: `3`
- Blocked before execution: `0`

## Highest-Severity Findings

| Test / Family | Severity | Issue | Evidence |
|---|---|---|---|
| `W6-LIVE-10` / `Config.1` | `HIGH` | The executable bundle changed AWS Config delivery state, but the documented rollback path deleted the pre-existing default recorder and delivery channel instead of restoring them. Manual recovery was required to return the account to its exact pre-state. | [`../tests/w6-live-10.md`](../tests/w6-live-10.md), [`../evidence/aws/w6-live-10-config-rollback-recorders.json`](../evidence/aws/w6-live-10-config-rollback-recorders.json), [`../evidence/aws/w6-live-10-config-cleanup-recorders.json`](../evidence/aws/w6-live-10-config-cleanup-recorders.json) |
| `W6-LIVE-11` / grouped runner | `HIGH` | Grouped `run_all.sh` embeds unquoted JSON callback templates. Every exercised grouped bundle emitted shell `command not found` plus `json.decoder.JSONDecodeError` before and after Terraform, and at least one group run remained stuck at `started` after a truthful AWS apply. | [`../tests/w6-live-11.md`](../tests/w6-live-11.md), [`../evidence/bundles/w6-live-04-s32-group/run_all-apply.log`](../evidence/bundles/w6-live-04-s32-group/run_all-apply.log), [`../evidence/bundles/w6-live-09-cloudtrail-group/run_all-apply.log`](../evidence/bundles/w6-live-09-cloudtrail-group/run_all-apply.log) |
| `W6-LIVE-03` / `IAM.4` | `BLOCKING` | Generic IAM.4 routes stayed metadata-only as intended, but the authoritative root-key route moved the live run to `needs_attention` with `self_cutoff_guard_not_guaranteed:observer_credentials_overlap_with_mutation_target` and left the root key active. | [`../tests/w6-live-03.md`](../tests/w6-live-03.md), [`../evidence/api/w6-live-03-iam4-artifact-metadata.tsv`](../evidence/api/w6-live-03-iam4-artifact-metadata.tsv) |
| `W6-LIVE-01` / `EC2.53` | `BLOCKING` | Standalone preview resolved the executable branch as `deterministic_bundle`, but the supported grouped customer-run bundle downgraded the same action to `review_required_bundle` with `runnable_action_count = 0`. | [`../tests/w6-live-01.md`](../tests/w6-live-01.md), [`../evidence/api/w6-live-01-ec253-bundle-contract-check.json`](../evidence/api/w6-live-01-ec253-bundle-contract-check.json) |

## Family-by-Family Validation Status

| Family | Live executable proof | Live downgrade/manual proof | Family status | Exact reason |
|---|---|---|---|---|
| `EC2.53` | `No` | `Yes` | `FAIL` | Supported grouped bundle unexpectedly downgraded the executable branch to `review_required_bundle`, so no truthful supported-path executable proof exists. |
| `IAM.4` | `No` | `Yes` | `FAIL` | Generic surfaces correctly stayed metadata-only, but the authoritative root-key disable path stopped at the self-cutoff guard and did not mutate the root key. |
| `S3.2` | `Yes` | `Yes` | `PASS` | Executable grouped bundle changed bucket public-access-block state and cleanup was manually restored to the exact pre-state; manual/downgrade branches also stayed truthful. |
| `S3.5` | `No` | `Yes` | `PARTIAL` | Review/preservation gating is proven, but no live executable apply plus rollback was completed in this final gate. |
| `S3.11` | `No` | `Yes` | `PARTIAL` | Manual guidance plus grouped executable contract are proven, but the attempted live bundle execution was stopped during Terraform init before the first AWS mutation. |
| `S3.9` | `Yes` | `Yes` | `PASS` | Destination-safe executable branch applied and destroyed cleanly, and the review-required destination-safety branch stayed metadata-only. |
| `S3.15` | `No` | `Yes` | `PARTIAL` | AWS-managed vs customer-managed KMS branching is proven, but no live executable apply plus rollback was completed in this final gate. |
| `CloudTrail.1` | `Yes` | `Yes` | `PASS` | Executable grouped bundle created and removed the trail cleanly, and the incompatible-default branch stayed `review_required_bundle`. |
| `Config.1` | `No` | `Yes` | `FAIL` | Executable apply was truthful, but rollback was not safe or exact; the account had to be manually repaired after the bundle path removed pre-existing Config state. |

## Exact Executable Cases Proven

- `S3.2`
  - Executable action `638c6b43-32ab-4104-a1da-29be5cd9a35a`
  - Target bucket `security-autopilot-w6-envready-s315-exec-696505809372`
  - Apply produced truthful AWS change; exact pre-state was restored with explicit AWS CLI cleanup after bundle destroy removed the public-access-block object.
- `S3.9`
  - Executable action `eabe460f-fe71-44d0-a055-4cff617b4062`
  - Target bucket `security-autopilot-w6-envready-config-696505809372`
  - Apply enabled access logging to `security-autopilot-w6-envready-accesslogs-696505809372`; destroy returned the bucket to no logging configuration.
- `CloudTrail.1`
  - Executable action `0bd41810-447a-4b57-bd09-d729f291b4ad`
  - Apply created trail `security-autopilot-trail`; destroy removed it and left the retained bucket policy unchanged.
- `Config.1`
  - Executable action `0e4108d7-3985-416d-b6cd-7659e8e45113`
  - Apply redirected the existing default delivery channel to `security-autopilot-w6-envready-config-696505809372`
  - The bundle/manual rollback then deleted the default recorder and delivery channel; manual recovery recreated them and restarted recording.

## Exact Downgrade / Review / Manual Cases Proven

- `EC2.53`
  - Manual action `baa158fa-53f5-4a61-a226-e25779c49fa7`
  - `ssm_only` stayed `manual_guidance_only`
- `IAM.4`
  - Generic `remediation-options` and `remediation-preview` both remained `manual_guidance_only`
  - Execution authority stayed limited to ``/api/root-key-remediation-runs``
- `S3.2`
  - Manual action `4b9462e5-2391-4d1d-9d8f-425e124ac9cf`
  - Website-hosting preservation branch stayed manual/non-executable
- `S3.5`
  - Account-level action `0242a107-32fa-44f3-bca8-820d14c20aff`
  - Review bundle remained non-executable because preservation evidence was incomplete
- `S3.11`
  - Manual action `d6eb9cb9-3325-4a5e-a250-760c0026ff10`
  - Manual guidance remained non-executable because lifecycle preservation evidence was incomplete
- `S3.9`
  - Eleven non-executable actions stayed `review_required_bundle` under the review-destination-safety profile
- `S3.15`
  - Manual action `31381d3c-04f9-4613-a897-ba95ddbdc0bd`
  - Customer-managed KMS path stayed `review_required_bundle`
- `CloudTrail.1`
  - Manual preview with intentionally bad default bucket stayed `review_required_bundle`
- `Config.1`
  - Manual preview with intentionally bad default bucket stayed `review_required_bundle`

## Supported-Path Execution Model Findings

- All executable AWS mutations in this run were performed by downloaded customer-run PR bundles or by the authoritative IAM.4 API route.
- No archived SaaS-managed plan/apply execution route was used.
- Grouped bundle callback reporting is currently defective on current `master`:
  - `run_all.sh` embeds raw JSON into shell assignments without quoting
  - `STARTED_TEMPLATE`, `FINISHED_SUCCESS_TEMPLATE`, and `FINISHED_FAILED_TEMPLATE` are not parse-safe shell values
  - Terraform can still run, but callback posting breaks and group-run terminal state can remain stale
- Because this regression exists in the supported customer-run bundle path, Wave 6 cannot be declared complete even for the families that reached truthful AWS apply plus cleanup.

## Rollback and Cleanup Status

- Target-account cleanup:
  - `S3.2` restored to exact pre-state with explicit `put-public-access-block` after bundle destroy removed the object
  - `S3.9` rolled back cleanly to no logging configuration
  - `CloudTrail.1` rolled back cleanly to no trail and unchanged retained bucket policy
  - `Config.1` required manual recovery to restore the pre-existing default recorder and default delivery channel after rollback removed them
- Retained seeded resources left in place intentionally:
  - `security-autopilot-w6-envready-accesslogs-696505809372`
  - `security-autopilot-w6-envready-cloudtrail-696505809372`
  - `security-autopilot-w6-envready-config-696505809372`
  - `security-autopilot-w6-envready-s311-exec-696505809372`
  - `security-autopilot-w6-envready-s311-review-696505809372`
  - `security-autopilot-w6-envready-s315-exec-696505809372`
  - `security-autopilot-w6-strict-s311-exec-696505809372`
  - `security-autopilot-w6-strict-s311-manual-696505809372`
  - `security-autopilot-w6-strict-s315-exec-696505809372`
  - `security-autopilot-w6-strict-s315-manual-696505809372`
  - security groups `sg-06f6252fa8a95b61d`, `sg-0ef32ca8805a55a8b`
  - customer-managed KMS key `arn:aws:kms:eu-north-1:696505809372:key/ef0cca31-8328-41e6-ab28-64cbedc1a44c`
- Local disposable runtime cleanup:
  - root-key API on `18021` stopped
  - disposable Postgres stopped
  - temporary SQS queues deleted and verified `NonExistentQueue`
  - see [`aws-cleanup-summary.md`](./aws-cleanup-summary.md)

## Environment Notes

- The repository was on `master`, but the worktree was not fully clean before this gate:
  - `backend/routers/remediation_runs.py`
  - `tests/test_remediation_runs_api.py`
- Focused regression evidence from the current workspace:
  - `./venv/bin/pytest tests/test_control_scope.py tests/test_action_engine_merge.py tests/test_worker_ingest.py tests/test_grouped_remediation_run_service.py tests/test_action_groups_bundle_run.py tests/test_grouped_remediation_run_routes.py tests/test_remediation_runs_api.py -q`
  - Result: `184 passed, 11 failed`
  - All `11` failures were in `tests/test_remediation_runs_api.py`
- Those existing failures did not change this documentation-only evidence package, but they are relevant environment context for any follow-up fix branch.

## Recommended Gate Decision

- Recommended gate decision: `Wave 6 complete = NO`
- Overall verdict: `FAIL`
- Rationale:
  - `EC2.53`, `IAM.4`, and `Config.1` each failed the strict executable-proof bar on current `master`
  - `S3.5`, `S3.11`, and `S3.15` still lack a truthful live executable proof in this final gate run
  - `W6-LIVE-11` found a high-severity grouped-runner regression in the supported customer-run bundle path
  - only `S3.2`, `S3.9`, and `CloudTrail.1` reached both truthful proof types in this run
