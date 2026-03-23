AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have Lifecycle configurations
Action ID: c533dff3-a0f0-4d76-8dd3-19315fb3e47d
Tier: manual_guidance
Tier root: manual_guidance/actions
Outcome: manual_guidance_metadata_only
Strategy: s3_enable_abort_incomplete_uploads
Profile: s3_enable_abort_incomplete_uploads

Decision summary: Family resolver downgraded S3.11 strategy 's3_enable_abort_incomplete_uploads' because additive lifecycle preservation is under-proven. An error occurred (AccessDenied) when calling the AssumeRole operation: Access denied. Check role ARN and trust policy. Lifecycle preservation evidence is missing for additive merge review. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
