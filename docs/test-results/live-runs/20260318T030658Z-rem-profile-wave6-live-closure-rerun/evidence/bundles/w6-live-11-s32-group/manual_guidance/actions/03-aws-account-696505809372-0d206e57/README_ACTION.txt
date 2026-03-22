AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should block public write access
Action ID: 0d206e57-2a9a-4d7e-abda-da73a5e93695
Tier: manual_guidance
Tier root: manual_guidance/actions
Outcome: manual_guidance_metadata_only
Strategy: s3_bucket_block_public_access_standard
Profile: s3_bucket_block_public_access_manual_preservation

Decision summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Runtime evidence could not prove the bucket is private and website hosting is disabled. Missing bucket identifier for access-path validation. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
