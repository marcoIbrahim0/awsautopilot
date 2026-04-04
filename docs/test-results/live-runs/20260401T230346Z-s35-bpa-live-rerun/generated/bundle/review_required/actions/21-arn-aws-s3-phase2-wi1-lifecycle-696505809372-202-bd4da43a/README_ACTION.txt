AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should require requests to use SSL
Action ID: bd4da43a-91bc-4b0b-84d7-9ca776af9210
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enforce_ssl_strict_deny
Profile: s3_enforce_ssl_strict_deny

Decision summary: Family resolver downgraded S3.5 strategy 's3_enforce_ssl_strict_deny' because merge-safe bucket policy preservation evidence is incomplete. Target bucket 'phase2-wi1-lifecycle-696505809372-20260329004157' no longer exists. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
