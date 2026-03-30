# Decision Log

## 1. S3 general purpose buckets should block public access
- Action ID: 688f5ed0-9594-4df1-9883-cc17feca62f8
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_standard
- Summary: Family resolver kept executable S3.2 profile 's3_bucket_block_public_access_standard' for strategy 's3_bucket_block_public_access_standard'. Run creation did not require additional risk-only acceptance.

## 2. S3 general purpose buckets should block public access
- Action ID: 0b87839b-28f5-4150-af26-74cf2b1af3a3
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver preserved explicit S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 3. S3 general purpose buckets should block public access
- Action ID: 352ac9b2-d343-40ac-b427-4c4f285615ef
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_manual_preservation
- Summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access. Run creation did not require additional risk-only acceptance.

## 4. S3 general purpose buckets should block public write access
- Action ID: 08a9f629-3bfa-46a1-bd88-e22027f7e133
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_manual_preservation
- Summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Runtime evidence could not prove the bucket is private and website hosting is disabled. Missing bucket identifier for access-path validation. Run creation did not require additional risk-only acceptance.

## 5. S3 general purpose buckets should block public read access
- Action ID: e88846fa-71d2-4291-ae12-2c13b1b49544
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_manual_preservation
- Summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Runtime evidence could not prove the bucket is private and website hosting is disabled. Run creation did not require additional risk-only acceptance.

## 6. S3 general purpose buckets should block public read access
- Action ID: 7522bc9f-5cab-4bad-908b-a382045f8d87
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_manual_preservation
- Summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Runtime evidence could not prove the bucket is private and website hosting is disabled. Run creation did not require additional risk-only acceptance.

## 7. S3 general purpose buckets should block public access
- Action ID: 4a965fac-c139-46e3-8594-11058b1dfe24
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_manual_preservation
- Summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Runtime evidence could not prove the bucket is private and website hosting is disabled. Run creation did not require additional risk-only acceptance.

## 8. S3 general purpose buckets should block public write access
- Action ID: cdb53f5c-8701-497d-a866-4256cddd9d66
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_manual_preservation
- Summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Runtime evidence could not prove the bucket is private and website hosting is disabled. Run creation did not require additional risk-only acceptance.

## 9. S3 general purpose buckets should block public access
- Action ID: 5571e909-6491-4077-818e-5441ae0dc95d
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_manual_preservation
- Summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Runtime evidence could not prove the bucket is private and website hosting is disabled. Run creation did not require additional risk-only acceptance.

## 10. S3 general purpose buckets should block public access
- Action ID: bdfa85bc-b3a3-4456-b8d9-9ed1dd895ad3
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_bucket_block_public_access_standard / s3_bucket_block_public_access_manual_preservation
- Summary: Family resolver downgraded strategy 's3_bucket_block_public_access_standard' to manual S3.2 preservation profile 's3_bucket_block_public_access_manual_preservation'. Runtime evidence could not prove the bucket is private and website hosting is disabled. Run creation did not require additional risk-only acceptance.

