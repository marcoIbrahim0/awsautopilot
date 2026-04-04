AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should block public write access
Action ID: fb27abe2-d234-4627-9ee2-6227b8447efd
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_migrate_cloudfront_oac_private
Profile: s3_migrate_cloudfront_oac_private_create_missing_bucket

Decision summary: Family resolver selected the create-missing-bucket CloudFront/OAC branch because the target bucket no longer exists and the new bucket can start from a zero-policy private baseline. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
