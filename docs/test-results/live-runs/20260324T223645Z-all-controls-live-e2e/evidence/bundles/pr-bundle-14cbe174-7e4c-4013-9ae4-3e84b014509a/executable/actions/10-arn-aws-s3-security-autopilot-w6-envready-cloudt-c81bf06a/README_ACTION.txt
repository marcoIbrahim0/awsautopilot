AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have Lifecycle configurations
Action ID: c81bf06a-bf7a-42d6-b154-8c1a97739781
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_enable_abort_incomplete_uploads
Profile: s3_enable_abort_incomplete_uploads

Decision summary: Family resolver kept S3.11 strategy 's3_enable_abort_incomplete_uploads' executable with abort_days=7 because lifecycle preservation is already safe. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
