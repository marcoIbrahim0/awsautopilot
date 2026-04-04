# Follow-up executable bundle rerun on April 1, 2026 UTC

This note summarizes the follow-up rerun of the `10` previously `APPLY NOT SUCCESSFUL` grouped PR bundles for account `696505809372` after repairing local AWS profile `test28-root` to valid root credentials for the target account.

Retained evidence is split across these run folders:

- [`20260401T015217Z-rerun-10-executable-bundles`](../)
- [`20260401T020706Z-rerun-3-isolated`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T020706Z-rerun-3-isolated/)
- [`20260401T022058Z-rerun-2-stream`](./)

## Outcome

- `5/10` executable families now completed successfully end to end:
  - `aws_config_enabled`
  - `ebs_snapshot_block_public_access`
  - `s3_block_public_access`
  - `sg_restrict_public_ports`
  - `ebs_default_encryption`
- `5/10` executable families still failed, but now for concrete AWS-state reasons rather than local credential failure:
  - `s3_bucket_access_logging`
  - `s3_bucket_require_ssl`
  - `s3_bucket_block_public_access`
  - `s3_bucket_encryption_kms`
  - `s3_bucket_lifecycle_configuration`

## Per-bundle feedback

### Success

- `aws_config_enabled`
  - Result: `success`
  - Evidence: `All action folders completed successfully.`
  - Retained file: [`01-eu-north-1-aws-config-enabled/result.json`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/01-eu-north-1-aws-config-enabled/result.json)
- `ebs_snapshot_block_public_access`
  - Result: `success`
  - Evidence: `All action folders completed successfully.`
  - Retained file: [`07-eu-north-1-ebs-snapshot-block-public-access/result.json`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/07-eu-north-1-ebs-snapshot-block-public-access/result.json)
- `s3_block_public_access`
  - Result: `success`
  - Evidence: `All action folders completed successfully.`
  - Retained file: [`08-eu-north-1-s3-block-public-access/result.json`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/08-eu-north-1-s3-block-public-access/result.json)
- `sg_restrict_public_ports`
  - Result: `success`
  - Evidence: `All action folders completed successfully.`
  - Retained file: [`09-eu-north-1-sg-restrict-public-ports/result.json`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/09-eu-north-1-sg-restrict-public-ports/result.json)
- `ebs_default_encryption`
  - Result: `success`
  - Evidence: `All action folders completed successfully.`
  - Retained file: [`11-eu-north-1-ebs-default-encryption/result.json`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/11-eu-north-1-ebs-default-encryption/result.json)

### Failed

- `s3_bucket_access_logging`
  - Result: `failed`
  - Bundle summary: `2/14` action folders succeeded, `12/14` failed
  - Primary failure reasons:
    - repeated `BucketAlreadyOwnedByYou` on access-log destination bucket creation for pre-existing `*-access-logs` buckets
    - `NoSuchBucket` on `PutBucketLogging` when the source bucket itself no longer existed
  - Retained files:
    - [`05-eu-north-1-s3-bucket-access-logging/result.json`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/05-eu-north-1-s3-bucket-access-logging/result.json)
    - [`05-eu-north-1-s3-bucket-access-logging/rerun_bundle_execution_transcript.json`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/05-eu-north-1-s3-bucket-access-logging/rerun_bundle_execution_transcript.json)
- `s3_bucket_require_ssl`
  - Result: `failed`
  - Bundle summary: `7/15` action folders succeeded, `8/15` failed
  - Primary failure reasons:
    - one apply failed with `AccessDenied` on `PutBucketPolicy` because S3 Block Public Access prevented the generated policy write
    - the remaining failed members hit plan-time `reading S3 Bucket ... Policy: couldn't find resource`
  - Retained files:
    - [`12-eu-north-1-s3-bucket-require-ssl/result.json`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/12-eu-north-1-s3-bucket-require-ssl/result.json)
    - [`12-eu-north-1-s3-bucket-require-ssl/rerun_bundle_execution_transcript.json`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T015217Z-rerun-10-executable-bundles/12-eu-north-1-s3-bucket-require-ssl/rerun_bundle_execution_transcript.json)
- `s3_bucket_block_public_access`
  - Result: `failed`
  - Bundle summary: `7/14` action folders succeeded, `7/14` failed
  - Primary failure reasons:
    - `OriginAccessControlAlreadyExists` on at least one CloudFront OAC create
    - plan failures on members whose source buckets and policies could not be read (`couldn't find resource`)
  - Retained files:
    - [`14-eu-north-1-s3-bucket-block-public-access/result.json`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T020706Z-rerun-3-isolated/14-eu-north-1-s3-bucket-block-public-access/result.json)
    - [`14-eu-north-1-s3-bucket-block-public-access/rerun_bundle_execution_transcript.json`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T020706Z-rerun-3-isolated/14-eu-north-1-s3-bucket-block-public-access/rerun_bundle_execution_transcript.json)
- `s3_bucket_encryption_kms`
  - Result: `failed`
  - Bundle summary: `8/15` action folders succeeded, `7/15` failed
  - Primary failure reason: repeated `NoSuchBucket` on `PutBucketEncryption` for missing target buckets
  - Retained files:
    - [`06-eu-north-1-s3-bucket-encryption-kms/bundle/run.log`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T022058Z-rerun-2-stream/06-eu-north-1-s3-bucket-encryption-kms/bundle/run.log)
    - [`06-eu-north-1-s3-bucket-encryption-kms/bundle/exit_code`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T022058Z-rerun-2-stream/06-eu-north-1-s3-bucket-encryption-kms/bundle/exit_code)
- `s3_bucket_lifecycle_configuration`
  - Result: `failed`
  - Bundle summary: `17/23` action folders succeeded, `6/23` failed
  - Primary failure reason: repeated `NoSuchBucket` during the local merge/apply path when `s3_lifecycle_merge.py` attempted `GetBucketLifecycleConfiguration` against missing buckets
  - Retained files:
    - [`04-eu-north-1-s3-bucket-lifecycle-configuration/bundle/run.log`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T022058Z-rerun-2-stream/04-eu-north-1-s3-bucket-lifecycle-configuration/bundle/run.log)
    - [`04-eu-north-1-s3-bucket-lifecycle-configuration/bundle/exit_code`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T022058Z-rerun-2-stream/04-eu-north-1-s3-bucket-lifecycle-configuration/bundle/exit_code)
