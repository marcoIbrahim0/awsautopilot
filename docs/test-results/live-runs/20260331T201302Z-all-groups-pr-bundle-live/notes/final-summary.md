# Final Summary

## Scope

- Run ID: `20260331T201302Z-all-groups-pr-bundle-live`
- Date: March 31, 2026 UTC
- Tenant: `Marco`
- Account: `696505809372`
- Region exercised: `eu-north-1`
- Live group inventory at capture time: `14`
- Execution split:
  - grouped PR-bundle families: `13`
  - dedicated IAM.4 root-key family: `1`

## Outcome

- All `13` grouped families were created and downloaded from live SaaS.
- The grouped execution sweep was run from AWS CloudShell, but CloudShell storage filled during Terraform provider bootstrap under `~/.aws-security-autopilot/terraform/provider-mirror/`, so the executable-tier runs did not complete cleanly.
- Post-run grouped status projection on live SaaS ended at:
  - `3` groups in `run_finished_metadata_only`
  - `10` groups in `run_not_successful`
- The dedicated IAM.4 family remained `open` / `not_run_yet`.

## Grouped Family Status

- Metadata-only truthful terminal groups:
  - `enable_guardduty`
  - `s3_bucket_access_logging`
  - `ssm_block_public_sharing`
- Groups left in `run_not_successful` after CloudShell execution pressure:
  - `aws_config_enabled`
  - `cloudtrail_enabled`
  - `ebs_default_encryption`
  - `ebs_snapshot_block_public_access`
  - `s3_block_public_access`
  - `s3_bucket_block_public_access`
  - `s3_bucket_encryption_kms`
  - `s3_bucket_lifecycle_configuration`
  - `s3_bucket_require_ssl`
  - `sg_restrict_public_ports`

## IAM.4 Dedicated Route Result

- Generic remediation options still expose IAM.4 as metadata only and explicitly point execution to `/api/root-key-remediation-runs`.
- Live production currently returns `404 feature_disabled` on `POST /api/root-key-remediation-runs`.
- Current live root-key group state therefore remains:
  - action group `549cd627-4bab-4e34-a15a-d9d50d11b3d9`
  - action `a3a48276-ee2e-4625-a42d-dadfdf5e0ea4`
  - member `action_status=open`
  - member `status_bucket=not_run_yet`

## Blocking Conditions

- CloudShell home storage is too small for the current grouped runner/provider-cache behavior. The failing terminal trace shows `no space left on device` while downloading `hashicorp/aws 5.100.0` into `~/.aws-security-autopilot/terraform/provider-mirror/...`.
- The authoritative live IAM.4 execution route is disabled in production, so "no rule left out" is not currently achievable on live SaaS even with operator auth.

## Evidence Pointers

- Grouped execution manifest: [grouped_execution_manifest.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260331T201302Z-all-groups-pr-bundle-live/grouped_execution_manifest.json)
- Post-run grouped statuses: [post_lean_grouped_run_group_status.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260331T201302Z-all-groups-pr-bundle-live/post_lean_grouped_run_group_status.json)
- CloudShell terminal tail: [cloudshell_lean_grouped_terminal_tail.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260331T201302Z-all-groups-pr-bundle-live/cloudshell_lean_grouped_terminal_tail.txt)
- IAM.4 live route probe: [create_run.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260331T201302Z-all-groups-pr-bundle-live/06-eu-north-1-iam_root_access_key_absent/root-key-route/create_run.json)
- IAM.4 latest group detail: [group_detail_latest.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260331T201302Z-all-groups-pr-bundle-live/06-eu-north-1-iam_root_access_key_absent/root-key-route/group_detail_latest.json)
- IAM.4 latest remediation options: [remediation_options_latest.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260331T201302Z-all-groups-pr-bundle-live/06-eu-north-1-iam_root_access_key_absent/root-key-route/remediation_options_latest.json)

## Follow-Up Fresh Signature Reruns

- April 1, 2026 follow-up reruns forced fresh grouped signature changes for `S3.9` and `SSM.7` using unique `repo_target` values.
- Result:
  - `S3.9` fresh rerun produced a mixed-tier bundle with `14` executable action folders and `2` review-required folders, proving the earlier retained March 31 metadata-only bundle was stale/reused rather than the only current live outcome.
  - `SSM.7` fresh rerun still produced a metadata-only bundle with `0` executable action folders and `1` review-required folder, proving this family remains review-required on the current live grouped surface.
- Follow-up evidence: [fresh signature rerun summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260331T201302Z-all-groups-pr-bundle-live/fresh-reruns-20260401/notes/final-summary.md)
