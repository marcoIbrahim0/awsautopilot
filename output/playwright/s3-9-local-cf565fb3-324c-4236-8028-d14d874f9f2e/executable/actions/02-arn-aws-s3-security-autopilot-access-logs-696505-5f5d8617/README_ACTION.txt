AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have server access logging enabled
Action ID: 5f5d8617-4da8-4830-a1dc-6b4e98f6b0b0
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_enable_access_logging_guided
Profile: s3_enable_access_logging_create_destination_bucket

Decision summary: Family resolver kept S3.9 executable by switching to dedicated destination-bucket creation with secure defaults. An error occurred (AccessDenied) when calling the AssumeRole operation: Access denied. Check role ARN and trust policy. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
