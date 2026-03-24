AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should block public access
Action ID: abf5eb48-ea9b-48d0-a534-236cf8818bf9
Tier: manual_guidance
Tier root: manual_guidance/actions
Outcome: manual_guidance_metadata_only
Strategy: s3_migrate_cloudfront_oac_private
Profile: s3_migrate_cloudfront_oac_private_manual_preservation

Decision summary: Family resolver preserved explicit S3.2 profile 's3_migrate_cloudfront_oac_private_manual_preservation' but downgraded it to non-executable guidance. Existing bucket policy preservation evidence is missing for CloudFront + OAC migration. An error occurred (AccessDenied) when calling the AssumeRole operation: Access denied. Check role ARN and trust policy. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
