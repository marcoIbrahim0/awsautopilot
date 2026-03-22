# Final Summary

## Scope

- Run ID: `20260322T191802Z-all-groups-pr-bundle-live`
- Date: March 22, 2026 UTC
- Tenant: `Valens`
- Account: `696505809372`
- Regions exercised: `eu-north-1`, `us-east-1`
- Local execution identity: `AWS_PROFILE=test28-root`

## Outcome

- Total live action groups at start: `22`
- Grouped bundle generation + local execution + grouped status `finished`: `15`
- Bundle generation succeeded but grouped execution recorded `failed`: `1`
- Bundle generation failed before execution: `6`

## Notable Findings

- `sg_restrict_public_ports` in `eu-north-1` generated successfully, but local execution exited `1` and the grouped run recorded `failed`.
  - Two action folders failed at Terraform `plan`.
  - The retained local execution log also shows duplicate-rule tolerance in one folder and Terraform state-lock acquisition failures in stderr.
- `cloudtrail_enabled` failed bundle creation with live `500 Internal Server Error` in both `eu-north-1` and `us-east-1`.
- `ebs_default_encryption` failed bundle creation with live `500 Internal Server Error` in `us-east-1`.
- `iam_root_access_key_absent` failed bundle creation with live `400` in both regions because the grouped generic route correctly denied the request and pointed to the dedicated `/api/root-key-remediation-runs` authority.
- `s3_bucket_access_logging` failed bundle creation with live `400 invalid_strategy_inputs` because `strategy_inputs.log_bucket_name` was required and not supplied by the grouped flow.
- The generated `run_all.sh` callback path can hang client-side even when the backend has already persisted the grouped run. The run for `s3_bucket_encryption_kms` in `eu-north-1` was recorded as `finished` in `action_group_runs` at `2026-03-22 19:22:28 UTC` even though the bundled `curl` never returned cleanly.

## Successful Groups

- `aws_config_enabled` in `eu-north-1`
- `ebs_default_encryption` in `eu-north-1`
- `ebs_snapshot_block_public_access` in `eu-north-1`
- `enable_guardduty` in `eu-north-1`
- `s3_block_public_access` in `eu-north-1`
- `s3_bucket_block_public_access` in `eu-north-1`
- `s3_bucket_encryption_kms` in `eu-north-1`
- `s3_bucket_lifecycle_configuration` in `eu-north-1`
- `s3_bucket_require_ssl` in `eu-north-1`
- `ssm_block_public_sharing` in `eu-north-1`
- `aws_config_enabled` in `us-east-1`
- `ebs_snapshot_block_public_access` in `us-east-1`
- `enable_guardduty` in `us-east-1`
- `s3_block_public_access` in `us-east-1`
- `ssm_block_public_sharing` in `us-east-1`

## Immediate Status Semantics Observed

- Successful bundle generation moved `remediation_runs.status` to `success` quickly.
- Successful local bundle execution plus callback reporting moved `action_group_runs.status` to `finished`.
- Failed local execution moved `action_group_runs.status` to `failed`.
- These grouped execution outcomes did not, by themselves, prove that the underlying action was already closed. Reconcile/compute was triggered for both regions at the end of the run, but action closure still depends on later authoritative AWS confirmation.

## Evidence Pointers

- Consolidated summary: [summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T191802Z-all-groups-pr-bundle-live/summary.json)
- API transcript: [api_transcript.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T191802Z-all-groups-pr-bundle-live/api_transcript.json)
- Failing grouped execution details: [13-eu-north-1-sg_restrict_public_ports/result.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T191802Z-all-groups-pr-bundle-live/13-eu-north-1-sg_restrict_public_ports/result.json)
