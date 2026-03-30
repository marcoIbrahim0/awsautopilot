AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have Lifecycle configurations
Action ID: cbb438f0-4e9a-489e-b7cf-2ef5dd95edf3
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_enable_abort_incomplete_uploads
Profile: s3_enable_abort_incomplete_uploads

Decision summary: Family resolver kept S3.11 strategy 's3_enable_abort_incomplete_uploads' executable with abort_days=7 because lifecycle preservation is already safe. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
