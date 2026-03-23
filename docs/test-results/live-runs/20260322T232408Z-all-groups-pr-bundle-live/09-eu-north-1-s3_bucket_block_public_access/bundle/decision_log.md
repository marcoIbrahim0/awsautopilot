# Decision Log

## 1. S3 general purpose buckets should block public access
- Action ID: abf5eb48-ea9b-48d0-a534-236cf8818bf9
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private_manual_preservation
- Summary: Family resolver downgraded strategy 's3_migrate_cloudfront_oac_private' to manual S3.2 preservation profile 's3_migrate_cloudfront_oac_private_manual_preservation'. Unable to inspect bucket website configuration (AccessDenied). Run creation did not require additional risk-only acceptance.

## 2. S3 general purpose buckets should block public access
- Action ID: f497bc0c-ddcb-4191-8fa5-c6ed21bbe134
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private_manual_preservation
- Summary: Family resolver downgraded strategy 's3_migrate_cloudfront_oac_private' to manual S3.2 preservation profile 's3_migrate_cloudfront_oac_private_manual_preservation'. Unable to inspect bucket website configuration (AccessDenied). Run creation did not require additional risk-only acceptance.

## 3. S3 general purpose buckets should block public write access
- Action ID: 19337c80-843c-40fb-b35c-fd561406009f
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private_manual_preservation
- Summary: Family resolver downgraded strategy 's3_migrate_cloudfront_oac_private' to manual S3.2 preservation profile 's3_migrate_cloudfront_oac_private_manual_preservation'. Existing bucket policy preservation evidence is missing for CloudFront + OAC migration. Missing bucket identifier for access-path validation. Run creation did not require additional risk-only acceptance.

