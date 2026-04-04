AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have server access logging enabled
Action ID: cc3ba387-feb0-42a6-a6b6-6e18f2a1dc65
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_enable_access_logging_guided
Profile: s3_enable_access_logging_guided

Decision summary: Family resolver kept S3.9 executable because bucket scope and destination safety are proven. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
