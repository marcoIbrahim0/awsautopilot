AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should require requests to use SSL
Action ID: ceb048a5-805e-4a13-978b-e8ed9e3c82ea
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enforce_ssl_strict_deny
Profile: s3_enforce_ssl_strict_deny

Decision summary: Family resolver downgraded S3.5 strategy 's3_enforce_ssl_strict_deny' because merge-safe bucket policy preservation evidence is incomplete. Target bucket 'phase2-wi1-lifecycle-696505809372-20260328224331' no longer exists. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
