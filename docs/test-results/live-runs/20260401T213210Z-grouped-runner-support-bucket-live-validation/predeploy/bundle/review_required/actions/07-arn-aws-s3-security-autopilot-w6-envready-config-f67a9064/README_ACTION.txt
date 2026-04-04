AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have server access logging enabled
Action ID: f67a9064-2a5f-47fd-820c-15797f354c7c
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enable_access_logging_guided
Profile: s3_enable_access_logging_review_destination_safety

Decision summary: Family resolver downgraded S3.9 to destination-safety review. Destination log bucket 'security-autopilot-w6-envready-config-696505809372-access-logs' could not be verified from this account context (403). Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
