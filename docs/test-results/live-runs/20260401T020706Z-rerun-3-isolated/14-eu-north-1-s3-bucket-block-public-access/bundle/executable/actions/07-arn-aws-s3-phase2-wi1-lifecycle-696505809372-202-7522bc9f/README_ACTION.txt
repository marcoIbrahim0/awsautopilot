AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should block public read access
Action ID: 7522bc9f-5cab-4bad-908b-a382045f8d87
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_migrate_cloudfront_oac_private
Profile: s3_migrate_cloudfront_oac_private

Decision summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' because Terraform can merge the current bucket policy at apply time. Runtime capture failed (NoSuchBucket), so the customer-run Terraform bundle must fetch the live bucket policy. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
