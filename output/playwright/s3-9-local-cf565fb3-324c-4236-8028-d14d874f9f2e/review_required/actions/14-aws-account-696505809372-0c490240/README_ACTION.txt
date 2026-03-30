AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have server access logging enabled
Action ID: 0c490240-f3b5-42b2-94ce-010ae67bd79f
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enable_access_logging_guided
Profile: s3_enable_access_logging_create_destination_bucket

Decision summary: Family resolver kept S3.9 executable by switching to dedicated destination-bucket creation with secure defaults. An error occurred (AccessDenied) when calling the AssumeRole operation: Access denied. Check role ARN and trust policy. Run creation was accepted after risk_acknowledged=true satisfied review-required checks.
This folder is metadata only and does not contain runnable Terraform.
