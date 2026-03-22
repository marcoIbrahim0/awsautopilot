# Decision Log

## 1. S3 general purpose buckets should block public access
- Action ID: a5bbba51-b5a8-4176-8f93-e9d0c376ade5
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_manual_preservation
- Summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access. Run creation did not require additional risk-only acceptance.

## 2. S3 general purpose buckets should block public access
- Action ID: b32b4a18-4da2-4f94-acf3-0ec4f2e555db
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_standard
- Summary: Family resolver kept executable S3.2 profile 's3_bucket_block_public_access_standard' for strategy 's3_bucket_block_public_access_standard'. Run creation did not require additional risk-only acceptance.

## 3. S3 general purpose buckets should block public write access
- Action ID: 0d206e57-2a9a-4d7e-abda-da73a5e93695
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_manual_preservation
- Summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Runtime evidence could not prove the bucket is private and website hosting is disabled. Missing bucket identifier for access-path validation. Run creation did not require additional risk-only acceptance.

