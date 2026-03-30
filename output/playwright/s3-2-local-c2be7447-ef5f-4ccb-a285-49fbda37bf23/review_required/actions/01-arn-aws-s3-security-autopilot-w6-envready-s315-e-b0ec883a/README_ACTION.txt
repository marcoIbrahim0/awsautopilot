AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should block public access
Action ID: b0ec883a-f08d-4480-a5f6-807446f9ad8b
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_bucket_block_public_access_standard
Profile: s3_bucket_block_public_access_review_state_verification

Decision summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to review-required S3.2 profile 's3_bucket_block_public_access_review_state_verification'. Runtime evidence could not prove the bucket is private and website hosting is disabled. An error occurred (AccessDenied) when calling the AssumeRole operation: Access denied. Check role ARN and trust policy. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
