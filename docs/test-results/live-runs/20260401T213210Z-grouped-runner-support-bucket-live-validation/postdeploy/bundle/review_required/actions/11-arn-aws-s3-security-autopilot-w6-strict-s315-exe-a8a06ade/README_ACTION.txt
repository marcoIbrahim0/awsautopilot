AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have server access logging enabled
Action ID: a8a06ade-67b9-4b5b-89df-1f4f430036a5
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enable_access_logging_guided
Profile: s3_enable_access_logging_review_destination_safety

Decision summary: Family resolver downgraded S3.9 to destination-safety review. Target bucket 'security-autopilot-w6-strict-s315-exec-696505809372' existence could not be verified from this account context (403). Do not keep the existing-bucket remediation path executable until bucket existence is proven. Destination log bucket 'security-autopilot-w6-strict-s315-exec-696505809372-access-logs' could not be verified from this account context (403). Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
