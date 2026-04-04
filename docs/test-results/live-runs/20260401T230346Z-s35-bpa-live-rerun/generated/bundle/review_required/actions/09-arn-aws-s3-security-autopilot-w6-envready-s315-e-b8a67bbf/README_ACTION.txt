AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should require requests to use SSL
Action ID: b8a67bbf-1255-40f1-ab21-569689459a36
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enforce_ssl_strict_deny
Profile: s3_enforce_ssl_strict_deny

Decision summary: Family resolver downgraded S3.5 strategy 's3_enforce_ssl_strict_deny' because merge-safe bucket policy preservation evidence is incomplete. Target bucket 'security-autopilot-w6-envready-s315-exec-696505809372' existence could not be verified from this account context (403). Do not keep the existing-bucket remediation path executable until bucket existence is proven. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
