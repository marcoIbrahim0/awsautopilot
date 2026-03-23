AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should be encrypted at rest with AWS KMS keys
Action ID: 6bfdbc7b-1a54-4bb1-b366-ab99ee59a677
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_enable_sse_kms_guided
Profile: s3_enable_sse_kms_guided

Decision summary: Family resolver kept S3.15 branch 's3_enable_sse_kms_guided' executable with key_mode=aws_managed. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
