# Decision Log

## 1. S3 general purpose buckets should block public access
- Action ID: 4b9462e5-2391-4d1d-9d8f-425e124ac9cf
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_manual_preservation
- Summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access. Run creation did not require additional risk-only acceptance.

## 2. S3 general purpose buckets should block public access
- Action ID: 638c6b43-32ab-4104-a1da-29be5cd9a35a
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_standard
- Summary: Family resolver kept executable S3.2 profile 's3_bucket_block_public_access_standard' for strategy 's3_bucket_block_public_access_standard'. Run creation did not require additional risk-only acceptance.

## 3. S3 general purpose buckets should block public write access
- Action ID: 02a1f4a9-2ae6-4e42-bd0e-7ac659b3c0e5
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_manual_preservation
- Summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Runtime evidence could not prove the bucket is private and website hosting is disabled. Missing bucket identifier for access-path validation. Run creation did not require additional risk-only acceptance.

