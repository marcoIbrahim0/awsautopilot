AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have server access logging enabled
Action ID: e9ca4a12-90e8-4312-82ec-fadfea82a7ce
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_enable_access_logging_guided
Profile: s3_enable_access_logging_create_destination_bucket

Decision summary: Family resolver kept S3.9 executable by switching to dedicated destination-bucket creation with secure defaults. Destination log bucket 'security-autopilot-access-logs-696505809372' could not be verified from this account context (404). Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
