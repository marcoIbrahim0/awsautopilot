# Final Summary

## Scope

- Run ID: `20260322T232408Z-all-groups-pr-bundle-live`
- Date: March 22, 2026 UTC
- Tenant: `Valens`
- Account: `696505809372`
- Regions exercised: `eu-north-1`, `us-east-1`
- Local execution identity: `AWS_PROFILE=test28-root`

## Outcome

- Total live action groups at start: `22`
- Grouped bundle generation + local execution + grouped status `finished`: `11`
- Bundle generation succeeded but grouped execution did not finish cleanly: `6`
- Bundle generation failed before execution: `5`

## Notable Findings

- `s3_bucket_access_logging` in `eu-north-1` no longer failed at bundle creation. With safe-default strategy input resolution, bundle generation succeeded and the bundle executed locally, but the grouped run remained `started` instead of finalizing.
- `s3_bucket_encryption_kms` and `s3_bucket_require_ssl` in `eu-north-1` showed the same pattern: bundle generation succeeded, local execution ran, but grouped status remained `started`.
- `ebs_default_encryption` in `eu-north-1`, `s3_bucket_lifecycle_configuration` in `eu-north-1`, and `sg_restrict_public_ports` in `eu-north-1` all generated successfully but recorded grouped execution `failed`.
- `sg_restrict_public_ports` remains the clearest repeated live execution failure. The grouped run again reached `failed` after local execution.
- `cloudtrail_enabled` still failed bundle creation with live `500 Internal Server Error` in both `eu-north-1` and `us-east-1`.
- `ebs_default_encryption` failed earlier at bundle creation with live `500 Internal Server Error` in `us-east-1`.
- `iam_root_access_key_absent` still failed bundle creation with live `400` in both regions because the grouped generic route correctly denied the request and pointed to the dedicated `/api/root-key-remediation-runs` authority.
- The live edge remained unstable for some authenticated reads during this run. Direct authenticated `curl` requests intermittently returned `Recv failure: Connection reset by peer`, so later polling was resumed and completed from retained artifacts plus the grouped-runs list route.

## Successful Groups

- `aws_config_enabled` in `eu-north-1`
- `ebs_snapshot_block_public_access` in `eu-north-1`
- `enable_guardduty` in `eu-north-1`
- `s3_block_public_access` in `eu-north-1`
- `s3_bucket_block_public_access` in `eu-north-1`
- `ssm_block_public_sharing` in `eu-north-1`
- `aws_config_enabled` in `us-east-1`
- `ebs_snapshot_block_public_access` in `us-east-1`
- `enable_guardduty` in `us-east-1`
- `s3_block_public_access` in `us-east-1`
- `ssm_block_public_sharing` in `us-east-1`

## Groups Requiring Follow-Up

- Grouped status `started` after successful bundle generation and local execution:
  - `s3_bucket_access_logging` in `eu-north-1`
  - `s3_bucket_encryption_kms` in `eu-north-1`
  - `s3_bucket_require_ssl` in `eu-north-1`
- Grouped status `failed` after successful bundle generation and local execution:
  - `ebs_default_encryption` in `eu-north-1`
  - `s3_bucket_lifecycle_configuration` in `eu-north-1`
  - `sg_restrict_public_ports` in `eu-north-1`
- Bundle generation failed before execution:
  - `cloudtrail_enabled` in `eu-north-1`
  - `iam_root_access_key_absent` in `eu-north-1`
  - `cloudtrail_enabled` in `us-east-1`
  - `ebs_default_encryption` in `us-east-1`
  - `iam_root_access_key_absent` in `us-east-1`

## Immediate Status Semantics Observed

- Successful bundle generation still moved `remediation_runs.status` to `success` quickly.
- Some successful local bundle executions did not finalize the corresponding grouped run and remained `started`.
- Other successful bundle generations reached grouped `failed`, so grouped callback/reporting semantics still need investigation even after the isolated Terraform-workspace runner hardening.
- These grouped execution outcomes do not, by themselves, prove that the underlying actions are already closed. Reconcile/compute and later authoritative AWS confirmation remain separate steps.

## Evidence Pointers

- Consolidated summary: [summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T232408Z-all-groups-pr-bundle-live/summary.json)
- Stuck grouped run example: [08-eu-north-1-s3_bucket_access_logging/result.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T232408Z-all-groups-pr-bundle-live/08-eu-north-1-s3_bucket_access_logging/result.json)
- Repeated grouped failure example: [13-eu-north-1-sg_restrict_public_ports/result.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T232408Z-all-groups-pr-bundle-live/13-eu-north-1-sg_restrict_public_ports/result.json)
- CloudTrail bundle-generation failure example: [16-us-east-1-cloudtrail_enabled/result.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T232408Z-all-groups-pr-bundle-live/16-us-east-1-cloudtrail_enabled/result.json)
