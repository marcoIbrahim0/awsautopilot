# Decision Log

## 1. S3 general purpose buckets should require requests to use SSL
- Action ID: 4fc6db43-ea06-4afc-a670-2ca8d0495070
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_enforce_ssl_strict_deny / s3_enforce_ssl_strict_deny
- Summary: Family resolver kept S3.5 strategy 's3_enforce_ssl_strict_deny' executable because merge-safe policy preservation evidence is available. Run creation did not require additional risk-only acceptance.

## 2. S3 general purpose buckets should require requests to use SSL
- Action ID: b9d3ffd9-6193-48ba-a02d-5835b1c120ad
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_enforce_ssl_strict_deny / s3_enforce_ssl_strict_deny
- Summary: Family resolver kept S3.5 strategy 's3_enforce_ssl_strict_deny' executable because merge-safe policy preservation evidence is available. Run creation did not require additional risk-only acceptance.

## 3. S3 general purpose buckets should require requests to use SSL
- Action ID: 1e453177-31da-47ec-bfce-796fcebc9e4b
- Tier: review_required/actions
- Outcome: review_required_metadata_only
- Strategy/Profile: s3_enforce_ssl_strict_deny / s3_enforce_ssl_strict_deny
- Summary: Family resolver downgraded S3.5 strategy 's3_enforce_ssl_strict_deny' because merge-safe bucket policy preservation evidence is incomplete. Bucket policy preservation evidence is missing for merge-safe SSL enforcement. Run creation did not require additional risk-only acceptance.

