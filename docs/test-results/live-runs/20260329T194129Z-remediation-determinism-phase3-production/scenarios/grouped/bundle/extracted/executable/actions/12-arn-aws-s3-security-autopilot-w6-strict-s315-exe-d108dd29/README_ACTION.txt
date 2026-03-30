AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have Lifecycle configurations
Action ID: d108dd29-a89d-45d3-b2d5-9689d9699d5e
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_enable_abort_incomplete_uploads
Profile: s3_enable_abort_incomplete_uploads

Decision summary: Family resolver kept S3.11 strategy 's3_enable_abort_incomplete_uploads' executable with abort_days=7 because lifecycle preservation is already safe. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
