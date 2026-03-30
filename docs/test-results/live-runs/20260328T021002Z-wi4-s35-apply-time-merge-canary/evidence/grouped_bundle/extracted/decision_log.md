# Decision Log

## 1. S3 general purpose buckets should require requests to use SSL
- Action ID: 29f0d788-90f3-48e4-96d7-8ed0657924a6
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_enforce_ssl_strict_deny / s3_enforce_ssl_strict_deny
- Summary: Family resolver kept S3.5 strategy 's3_enforce_ssl_strict_deny' executable because Terraform can merge the current bucket policy at apply time. Runtime capture failed (AccessDenied), so the customer-run Terraform bundle must fetch the live policy. Run creation did not require additional risk-only acceptance.

## 2. S3 general purpose buckets should require requests to use SSL
- Action ID: 424d65bb-5bd8-4ba3-a5ca-9785fbb41bb9
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_enforce_ssl_strict_deny / s3_enforce_ssl_strict_deny
- Summary: Family resolver kept S3.5 strategy 's3_enforce_ssl_strict_deny' executable because Terraform can merge the current bucket policy at apply time. Runtime capture failed (AccessDenied), so the customer-run Terraform bundle must fetch the live policy. Run creation did not require additional risk-only acceptance.

## 3. S3 general purpose buckets should require requests to use SSL
- Action ID: 7a438b0e-37e8-444e-a211-04a906891a69
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_enforce_ssl_strict_deny / s3_enforce_ssl_strict_deny
- Summary: Family resolver kept S3.5 strategy 's3_enforce_ssl_strict_deny' executable because Terraform can merge the current bucket policy at apply time. Runtime capture failed (AccessDenied), so the customer-run Terraform bundle must fetch the live policy. Run creation did not require additional risk-only acceptance.

## 4. S3 general purpose buckets should require requests to use SSL
- Action ID: 251b980d-17a9-4fae-8e5f-e2ca38d389ed
- Tier: review_required/actions
- Outcome: review_required_metadata_only
- Strategy/Profile: s3_enforce_ssl_strict_deny / s3_enforce_ssl_strict_deny
- Summary: Family resolver downgraded S3.5 strategy 's3_enforce_ssl_strict_deny' because merge-safe bucket policy preservation evidence is incomplete. Bucket policy preservation evidence is missing for merge-safe SSL enforcement. Run creation did not require additional risk-only acceptance.

