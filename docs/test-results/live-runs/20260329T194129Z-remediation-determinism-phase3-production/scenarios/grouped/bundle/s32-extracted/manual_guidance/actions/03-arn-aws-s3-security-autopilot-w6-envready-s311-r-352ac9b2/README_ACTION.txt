AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should block public access
Action ID: 352ac9b2-d343-40ac-b427-4c4f285615ef
Tier: manual_guidance
Tier root: manual_guidance/actions
Outcome: manual_guidance_metadata_only
Strategy: s3_bucket_block_public_access_standard
Profile: s3_bucket_block_public_access_manual_preservation

Decision summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
