AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should require requests to use SSL
Action ID: 53b7b063-8531-4829-9b23-f03b1796b23d
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enforce_ssl_strict_deny
Profile: s3_enforce_ssl_strict_deny

Decision summary: Family resolver downgraded S3.5 strategy 's3_enforce_ssl_strict_deny' because preserving the current public bucket policy would conflict with S3 Block Public Access. Current bucket policy is public and S3 Block Public Access prevents public policies, so merge-preserving SSL enforcement would be rejected by PutBucketPolicy. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
