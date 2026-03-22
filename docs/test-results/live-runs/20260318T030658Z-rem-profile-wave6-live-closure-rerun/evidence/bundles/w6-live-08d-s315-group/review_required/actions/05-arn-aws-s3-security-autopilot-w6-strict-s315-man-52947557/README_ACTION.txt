AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should be encrypted at rest with AWS KMS keys
Action ID: 52947557-0b35-4c03-99d6-4fdf77c86a24
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enable_sse_kms_guided
Profile: s3_enable_sse_kms_customer_managed

Decision summary: Family resolver downgraded S3.15 branch 's3_enable_sse_kms_customer_managed' because KMS safety is under-proven. AccessDeniedException Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
