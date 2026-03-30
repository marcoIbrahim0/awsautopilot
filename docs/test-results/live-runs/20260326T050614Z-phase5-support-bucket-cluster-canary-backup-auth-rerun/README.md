# Phase 5 Support-Bucket Cluster Canary Via Backup Auth Rerun

- Run ID: `20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun`
- Date (UTC): `2026-03-26`
- Frontend: `https://ocypheris.com`
- API: `https://api.ocypheris.com`
- Auth path: isolated authenticated browser/API session for `Valens Local Backup`
- Live tenant/account used: tenant `Valens Local Backup`, account `696505809372`, region `eu-north-1`
- Outcome: `PARTIAL`
- Remaining blocker bucket: `config_source_of_truth_confirmation_pending`

## Summary

This retained rerun exercised the implemented Phase 5 closure plan on the backup tenant after restoring live API access through the serverless runtime fallback DB path.

The rerun proved:
- `Config.1`, `S3.9`, and `CloudTrail.1` all now generate `support_tier=deterministic_bundle`
- `Config.1` accepts explicit `recording_scope=all_resources`, applies successfully, and fixes the AWS Config recorder state in the target account
- `S3.9` now keeps the managed create-destination branch executable and emits the shared support-bucket baseline in the live bundle
- `CloudTrail.1` now keeps the managed create-if-missing branch executable, but the first live bundle from this rerun still emitted the stale family-local bucket fragment and required the focused postdeploy recheck at [20260326T052354Z-phase5-cloudtrail-postdeploy-recheck](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T052354Z-phase5-cloudtrail-postdeploy-recheck/README.md)

## Family Outcomes

- `Config.1`
  - remediation run `63fd9b08-8d5c-41ea-9ca8-7905a61f94dd`
  - result: deterministic executable bundle generated and applied locally with `AWS_PROFILE=test28-root`
  - resolved inputs: `recording_scope=all_resources`, `delivery_bucket=security-autopilot-config-696505809372-eu-north-1`
  - post-apply AWS state:
    - recorder `allSupported=true`
    - `includeGlobalResourceTypes=true`
    - no remaining inclusion or exclusion resource-type lists
    - recorder status `recording=true`, `lastStatus=SUCCESS`
  - live gap: as of `2026-03-26T05:32:45Z`, the finding still remained `NEW` and `pending_confirmation=true` because Security Hub had not reevaluated since `UpdatedAt=2026-03-26T00:45:44.902Z`

- `S3.9`
  - remediation run `7fe2766d-7c8e-41de-b0ab-bc616b53978a`
  - result: deterministic executable bundle generated
  - resolved inputs: `create_log_bucket=true`, `log_bucket_name=security-autopilot-phase5-access-logs-696505809372-050614`
  - live bundle proof:
    - created destination bucket resource present
    - public access block enabled
    - `kms_master_key_id = "alias/aws/s3"`
    - multipart-abort lifecycle rule present
    - `DenyInsecureTransport` present

- `CloudTrail.1`
  - remediation run `adb3a9c6-5a17-4a9a-bc7b-05830bc46953`
  - result: deterministic executable bundle generated
  - resolved inputs: `create_bucket_if_missing=true`, `trail_bucket_name=security-autopilot-phase5-cloudtrail-696505809372-050614`
  - remaining live gap in this rerun:
    - the bundle still emitted `resource "aws_s3_bucket_policy" "cloudtrail_managed"`
    - the bundle still emitted `sse_algorithm = "AES256"`
    - this artifact mismatch was closed in the focused postdeploy recheck at [20260326T052354Z-phase5-cloudtrail-postdeploy-recheck](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T052354Z-phase5-cloudtrail-postdeploy-recheck/README.md)

## Rollout Decision

- Code implementation status: complete for the remaining Phase 5 families
- Live executable bundle proof:
  - `Config.1`: yes, but source-of-truth confirmation still pending
  - `S3.9`: yes
  - `CloudTrail.1`: yes after the focused postdeploy recheck
- Rollout decision: keep Phase 5 `in progress` until the live `Config.1` finding reevaluates or a separate source-of-truth refresh path is captured

## Key Artifacts

- [Run metadata](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun/00-run-metadata.md)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun/notes/final-summary.md)
- [Structured summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun/summary.json)
- [Focused CloudTrail postdeploy recheck](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T052354Z-phase5-cloudtrail-postdeploy-recheck/README.md)
- [Superseded initial backup-auth canary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T031724Z-phase5-support-bucket-cluster-canary-backup-auth/README.md)
