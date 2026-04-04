# Failed Executable Bundle Fix Handoff

This handoff covers the `5` executable grouped PR-bundle families that still failed after the April 1, 2026 rerun with repaired AWS root credentials for account `696505809372`.

Primary retained summary:

- [Follow-up executable bundle rerun on April 1, 2026 UTC](./final-summary.md)

Supporting retained evidence:

- [Initial all-groups live run summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T004147Z-all-groups-pr-bundle-live/notes/final-summary.md)
- [Rerun-10 partial results](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/)
- [Isolated S3 block-public-access rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T020706Z-rerun-3-isolated/)
- [Streamed S3 lifecycle/KMS rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T022058Z-rerun-2-stream/)

## What changed after root-cred repair

The earlier blocker is gone. The local AWS mutation profile `test28-root` now resolves correctly to account `696505809372`, so the remaining failures are not download/auth problems. They are current generator/runtime/state-drift issues against live AWS.

Successful executable families after rerun:

- `aws_config_enabled`
- `ebs_snapshot_block_public_access`
- `s3_block_public_access`
- `sg_restrict_public_ports`
- `ebs_default_encryption`

Still failing:

- `s3_bucket_access_logging`
- `s3_bucket_require_ssl`
- `s3_bucket_block_public_access`
- `s3_bucket_encryption_kms`
- `s3_bucket_lifecycle_configuration`

## Failed bundle details

### `s3_bucket_access_logging` (`S3.9`)

- Final status: `failed`
- Bundle count: `2/14` successful, `12/14` failed
- Retained result: [result.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/05-eu-north-1-s3-bucket-access-logging/result.json)
- Retained transcript: [rerun_bundle_execution_transcript.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/05-eu-north-1-s3-bucket-access-logging/rerun_bundle_execution_transcript.json)
- Concrete errors:
  - repeated `BucketAlreadyOwnedByYou` while creating `*-access-logs` destination buckets
  - `NoSuchBucket` on `PutBucketLogging` when the source bucket no longer existed
- Current source generator:
  - [pr_bundle.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py)
  - function `_terraform_s3_bucket_access_logging_content`
- Likely fix scope: `medium`
- Why:
  - the bundle still tries to create destination buckets that already exist and are already owned
  - the generator/runtime path does not fail closed early when the source bucket is gone
  - the runner already has partial duplicate tolerance in [run_all_template.sh](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/jobs/run_all_template.sh), but the generated resource shape still leaves many bucket-create and source-missing cases as hard failures

### `s3_bucket_require_ssl` (`S3.5`)

- Final status: `failed`
- Bundle count: `7/15` successful, `8/15` failed
- Retained result: [result.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/12-eu-north-1-s3-bucket-require-ssl/result.json)
- Retained transcript: [rerun_bundle_execution_transcript.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/12-eu-north-1-s3-bucket-require-ssl/rerun_bundle_execution_transcript.json)
- Concrete errors:
  - apply-time `AccessDenied` on `PutBucketPolicy` because `BlockPublicPolicy` in S3 Block Public Access rejected the generated policy
  - repeated plan-time `reading S3 Bucket ... Policy: couldn't find resource`
- Current source generator:
  - [pr_bundle.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py)
  - functions `_terraform_s3_bucket_require_ssl_content` and `_terraform_s3_bucket_require_ssl_apply_time_merge_content`
- Likely fix scope: `medium`
- Why:
  - this is not a core architecture problem, but the generator assumes the policy path is writable and that every target bucket policy is readable
  - deleted/stale buckets should fail closed earlier
  - Block Public Access-aware handling is needed before attempting `PutBucketPolicy`

### `s3_bucket_block_public_access` (`S3.2` family path via `s3_migrate_cloudfront_oac_private`)

- Final status: `failed`
- Bundle count: `7/14` successful, `7/14` failed
- Retained result: [result.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T020706Z-rerun-3-isolated/14-eu-north-1-s3-bucket-block-public-access/result.json)
- Retained transcript: [rerun_bundle_execution_transcript.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T020706Z-rerun-3-isolated/14-eu-north-1-s3-bucket-block-public-access/rerun_bundle_execution_transcript.json)
- Concrete errors:
  - `OriginAccessControlAlreadyExists` while creating CloudFront OAC
  - plan failures reading target buckets and existing bucket policies that no longer exist
- Current source generator:
  - [pr_bundle.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py)
  - strategy path `s3_migrate_cloudfront_oac_private`
- Likely fix scope: `medium` to `medium-high`
- Why:
  - duplicate OAC handling is probably patchable
  - if the desired behavior is true adopt/reuse/import of existing OACs and distributions, the fix is heavier than a simple retry wrapper
  - missing-bucket/policy prechecks should still be a contained fix

### `s3_bucket_encryption_kms` (`S3.15`)

- Final status: `failed`
- Bundle count: `8/15` successful, `7/15` failed
- Retained run log: [run.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T022058Z-rerun-2-stream/06-eu-north-1-s3-bucket-encryption-kms/bundle/run.log)
- Concrete errors:
  - repeated `PutBucketEncryption` `NoSuchBucket`
- Current source generator:
  - [pr_bundle.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py)
  - function `_terraform_s3_bucket_encryption_kms_content`
- Likely fix scope: `minor` to `medium`
- Why:
  - the generator currently writes a direct `aws_s3_bucket_server_side_encryption_configuration` against a fixed bucket name
  - missing-bucket detection should happen before execution or at generation/runtime-check time
  - this does not look like a large redesign

### `s3_bucket_lifecycle_configuration` (`S3.11`)

- Final status: `failed`
- Bundle count: `17/23` successful, `6/23` failed
- Retained run log: [run.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T022058Z-rerun-2-stream/04-eu-north-1-s3-bucket-lifecycle-configuration/bundle/run.log)
- Concrete errors:
  - repeated `GetBucketLifecycleConfiguration` `NoSuchBucket` inside `s3_lifecycle_merge.py`
- Current source generator:
  - [pr_bundle.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py)
  - function `_terraform_s3_bucket_lifecycle_configuration_apply_time_content`
  - generated helper `scripts/s3_lifecycle_merge.py`
- Likely fix scope: `minor` to `medium`
- Why:
  - this is mostly stale-target handling for the apply-time merge path
  - the helper should detect missing buckets and fail closed with a clearer stale/deleted-target outcome instead of hard-failing mid-apply

## Recommended follow-up tasks

These are the concrete tasks to hand to future agents. Count: `6`.

### Task 1: shared stale-target preflight for S3 bucket families

- Scope:
  - `s3_bucket_encryption_kms`
  - `s3_bucket_lifecycle_configuration`
  - `s3_bucket_require_ssl`
  - `s3_bucket_access_logging`
  - `s3_migrate_cloudfront_oac_private`
- Candidate source files:
  - [remediation_runtime_checks.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_runtime_checks.py)
  - [s3_family_resolution_adapter.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/s3_family_resolution_adapter.py)
  - [pr_bundle.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py)
- Goal:
  - if the target bucket no longer exists, do not produce an executable bundle path that hard-fails during apply
  - prefer stale/deleted-target downgrade, fail-closed generation error, or refreshed action resolution before bundle creation

### Task 2: `S3.9` adopt/reuse already-owned access-log destination buckets

- Candidate source files:
  - [pr_bundle.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py)
  - [run_all_template.sh](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/jobs/run_all_template.sh)
- Goal:
  - treat `BucketAlreadyOwnedByYou` on intended support buckets as adopt/reuse, not bundle failure
  - decide whether that should happen in Terraform shape, generated manifest metadata, or runner tolerance

### Task 3: `S3.9` missing source-bucket handling

- Candidate source files:
  - [pr_bundle.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py)
  - [remediation_runtime_checks.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_runtime_checks.py)
- Goal:
  - when the source bucket is gone, do not attempt `PutBucketLogging`
  - close or downgrade the action instead of producing a doomed executable member

### Task 4: `S3.5` Block Public Access-aware SSL enforcement

- Candidate source files:
  - [pr_bundle.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py)
  - [s3_family_resolution_adapter.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/s3_family_resolution_adapter.py)
- Goal:
  - avoid generating/applying a bucket policy write that S3 Block Public Access will reject
  - clarify whether the current generated policy shape is being interpreted as public and should instead use a different merge/order/statement form

### Task 5: `S3.2` duplicate CloudFront OAC handling

- Candidate source files:
  - [pr_bundle.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py)
  - [run_all_template.sh](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/jobs/run_all_template.sh)
- Goal:
  - when the OAC already exists, do not fail the bundle if the desired state is already satisfied or safely reusable
  - decide between duplicate-tolerant runner handling, deterministic naming fix, or import/adopt behavior

### Task 6: shared stale-action reconciliation after bucket deletion/drift

- Candidate source files:
  - [ingest_findings.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/jobs/ingest_findings.py)
  - [recompute_account_actions.py](/Users/marcomaher/AWS%20Security%20Autopilot/scripts/recompute_account_actions.py)
  - [s3_family_resolution_adapter.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/s3_family_resolution_adapter.py)
- Goal:
  - prevent repeated bundle generation for actions whose underlying buckets are already deleted
  - the April 1 failures show several executable members are now stale against live AWS and should likely be reprojected or resolved rather than retried forever

## Suggested execution order

1. Task 1
2. Task 6
3. Task 2
4. Task 3
5. Task 4
6. Task 5

Rationale:

- Tasks `1` and `6` reduce wasted reruns across multiple S3 families.
- Tasks `2` and `3` isolate the two concrete `S3.9` failure classes.
- Task `4` isolates the `S3.5` policy-vs-BPA behavior.
- Task `5` is the heaviest remaining targeted fix and should be tackled after the simpler stale-target and idempotency fixes land.
