AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should block public access
Action ID: 39d7ad12-7981-4614-9a6b-8ec3f7a7b5c1
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_migrate_cloudfront_oac_private
Profile: s3_migrate_cloudfront_oac_private

Decision summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' because Terraform can merge the current bucket policy at apply time. Runtime capture failed (NoSuchBucket), so the customer-run Terraform bundle must fetch the live bucket policy. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
