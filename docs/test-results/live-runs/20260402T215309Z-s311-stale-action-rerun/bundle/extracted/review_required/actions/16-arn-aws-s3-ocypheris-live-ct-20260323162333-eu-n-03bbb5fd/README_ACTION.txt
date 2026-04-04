AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have Lifecycle configurations
Action ID: 03bbb5fd-0d45-472e-91f7-b0dc98d8091f
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enable_abort_incomplete_uploads
Profile: s3_enable_abort_incomplete_uploads

Decision summary: Family resolver downgraded S3.11 strategy 's3_enable_abort_incomplete_uploads' because additive lifecycle preservation is under-proven. Target bucket 'ocypheris-live-ct-20260323162333-eu-north-1' existence could not be verified from this account context (403). Do not keep the existing-bucket remediation path executable until bucket existence is proven. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
