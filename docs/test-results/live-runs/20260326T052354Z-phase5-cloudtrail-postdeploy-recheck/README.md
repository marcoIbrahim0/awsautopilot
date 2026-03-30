# Phase 5 CloudTrail Postdeploy Recheck

- Run ID: `20260326T052354Z-phase5-cloudtrail-postdeploy-recheck`
- Date (UTC): `2026-03-26`
- Frontend: `https://ocypheris.com`
- API: `https://api.ocypheris.com`
- Live tenant/account used: tenant `Valens Local Backup`, account `696505809372`, region `eu-north-1`
- Runtime deploy tag: `20260326T052354Z`
- Outcome: `PASS`
- Verification bucket: `cloudtrail_bundle_contract_fixed`

## Summary

This focused rerun revalidated the live `CloudTrail.1` managed create-if-missing path after a clean-snapshot serverless redeploy.

The recheck proved that production now emits the corrected shared support-bucket baseline in the live `cloudtrail_enabled.tf` bundle:
- `resource "aws_s3_bucket_policy" "cloudtrail_logs"`
- `kms_master_key_id = "alias/aws/s3"`
- `DenyInsecureTransport`
- no `resource "aws_s3_bucket_policy" "cloudtrail_managed"`
- no `sse_algorithm = "AES256"`

## Live Outcome

- remediation run: `0f0a0212-ba3c-40e8-a8b9-9730cc496264`
- action: `9074eb82-d359-4ce2-9155-1b71699fed8f`
- resolved inputs:
  - `trail_bucket_name=security-autopilot-phase5-cloudtrail-696505809372-052354`
  - `create_bucket_if_missing=true`
  - `create_bucket_policy=true`
  - `multi_region=true`
- final support tier: `deterministic_bundle`

## Key Artifacts

- [Run metadata](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T052354Z-phase5-cloudtrail-postdeploy-recheck/00-run-metadata.md)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T052354Z-phase5-cloudtrail-postdeploy-recheck/notes/final-summary.md)
- [Structured summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T052354Z-phase5-cloudtrail-postdeploy-recheck/summary.json)
- [Superseded initial CloudTrail artifact from the full rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun/README.md)
