AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should block public access
Action ID: da0d429e-6f16-461e-be2f-09ea7997e30a
Tier: manual_guidance
Tier root: manual_guidance/actions
Outcome: manual_guidance_metadata_only
Strategy: s3_migrate_cloudfront_oac_private
Profile: s3_migrate_cloudfront_oac_private_manual_preservation

Decision summary: Family resolver downgraded strategy 's3_migrate_cloudfront_oac_private' to manual S3.2 preservation profile 's3_migrate_cloudfront_oac_private_manual_preservation'. Bucket is still configured for S3 website hosting with a public website-read policy, and BlockPublicPolicy would reject preserving that public statement. Use the website-specific CloudFront cutover path or manual review instead of the generic CloudFront + OAC migration. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
