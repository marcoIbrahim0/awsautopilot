AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have Lifecycle configurations
Action ID: e55dca93-6467-4dce-ba6c-16444f259760
Tier: manual_guidance
Tier root: manual_guidance/actions
Outcome: manual_guidance_metadata_only
Strategy: s3_enable_abort_incomplete_uploads
Profile: s3_enable_abort_incomplete_uploads

Decision summary: Family resolver downgraded S3.11 strategy 's3_enable_abort_incomplete_uploads' because additive lifecycle preservation is under-proven. An error occurred (AccessDenied) when calling the AssumeRole operation: Access denied. Check role ARN and trust policy. Lifecycle preservation evidence is missing for additive merge review. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
