# Decision Log

## 1. S3 general purpose buckets should block public access
- Action ID: b0ec883a-f08d-4480-a5f6-807446f9ad8b
- Tier: review_required/actions
- Outcome: review_required_metadata_only
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private_review_state_verification
- Summary: Family resolver downgraded strategy 's3_migrate_cloudfront_oac_private' to review-required S3.2 profile 's3_migrate_cloudfront_oac_private_review_state_verification'. Unable to inspect bucket website configuration (AccessDenied). Run creation did not require additional risk-only acceptance.

## 2. S3 general purpose buckets should block public access
- Action ID: c1a8dbfb-67f0-4656-bf8e-6f95b3bc04a0
- Tier: review_required/actions
- Outcome: review_required_metadata_only
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private_review_state_verification
- Summary: Family resolver downgraded strategy 's3_migrate_cloudfront_oac_private' to review-required S3.2 profile 's3_migrate_cloudfront_oac_private_review_state_verification'. Unable to inspect bucket website configuration (AccessDenied). Run creation did not require additional risk-only acceptance.

## 3. S3 general purpose buckets should block public write access
- Action ID: fb0b3cc7-2dd7-4c4c-8cac-26caaaec29b5
- Tier: review_required/actions
- Outcome: review_required_metadata_only
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private_review_state_verification
- Summary: Family resolver downgraded strategy 's3_migrate_cloudfront_oac_private' to review-required S3.2 profile 's3_migrate_cloudfront_oac_private_review_state_verification'. Existing bucket policy preservation evidence is missing for CloudFront + OAC migration. Missing bucket identifier for access-path validation. Run creation did not require additional risk-only acceptance.

