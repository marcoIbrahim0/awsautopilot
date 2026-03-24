AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should require requests to use SSL
Action ID: 830944d9-30ad-432f-a84e-e09c0dde3d5d
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enforce_ssl_strict_deny
Profile: s3_enforce_ssl_strict_deny

Decision summary: Family resolver downgraded S3.5 strategy 's3_enforce_ssl_strict_deny' because merge-safe bucket policy preservation evidence is incomplete. Bucket policy preservation evidence is missing for merge-safe SSL enforcement. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
