AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have server access logging enabled
Action ID: d74e91e3-3b34-408b-b330-018d5eee4e3e
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_enable_access_logging_guided
Profile: s3_enable_access_logging_guided

Decision summary: Family resolver kept S3.9 executable because bucket scope and destination safety are proven. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
