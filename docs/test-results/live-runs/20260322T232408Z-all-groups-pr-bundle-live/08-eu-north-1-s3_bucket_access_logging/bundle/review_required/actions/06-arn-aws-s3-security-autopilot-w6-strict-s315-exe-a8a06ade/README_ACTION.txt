AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have server access logging enabled
Action ID: a8a06ade-67b9-4b5b-89df-1f4f430036a5
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enable_access_logging_guided
Profile: s3_enable_access_logging_review_destination_safety

Decision summary: Family resolver downgraded S3.9 to destination-safety review. Destination log bucket 'security-autopilot-access-logs-696505809372' could not be verified from this account context (404). Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
