AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should require requests to use SSL
Action ID: dd64810c-7d83-4b46-9c8e-5f3b400be8d2
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enforce_ssl_strict_deny
Profile: s3_enforce_ssl_strict_deny

Decision summary: Family resolver downgraded S3.5 strategy 's3_enforce_ssl_strict_deny' because merge-safe bucket policy preservation evidence is incomplete. AccessDenied Bucket policy preservation evidence is missing for merge-safe SSL enforcement. Existing bucket policy capture failed (AccessDenied). Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
