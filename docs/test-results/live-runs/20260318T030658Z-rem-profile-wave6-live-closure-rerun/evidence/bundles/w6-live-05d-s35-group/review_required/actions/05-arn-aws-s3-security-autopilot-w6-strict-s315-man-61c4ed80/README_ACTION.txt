AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should require requests to use SSL
Action ID: 61c4ed80-2778-42a0-b0f2-4ff1095f9037
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enforce_ssl_strict_deny
Profile: s3_enforce_ssl_strict_deny

Decision summary: Family resolver downgraded S3.5 strategy 's3_enforce_ssl_strict_deny' because merge-safe bucket policy preservation evidence is incomplete. AccessDenied Bucket policy preservation evidence is missing for merge-safe SSL enforcement. Existing bucket policy capture failed (AccessDenied). Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
