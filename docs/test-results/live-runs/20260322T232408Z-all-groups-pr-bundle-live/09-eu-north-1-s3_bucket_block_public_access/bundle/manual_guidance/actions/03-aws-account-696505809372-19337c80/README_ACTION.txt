AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should block public write access
Action ID: 19337c80-843c-40fb-b35c-fd561406009f
Tier: manual_guidance
Tier root: manual_guidance/actions
Outcome: manual_guidance_metadata_only
Strategy: s3_migrate_cloudfront_oac_private
Profile: s3_migrate_cloudfront_oac_private_manual_preservation

Decision summary: Family resolver downgraded strategy 's3_migrate_cloudfront_oac_private' to manual S3.2 preservation profile 's3_migrate_cloudfront_oac_private_manual_preservation'. Existing bucket policy preservation evidence is missing for CloudFront + OAC migration. Missing bucket identifier for access-path validation. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
