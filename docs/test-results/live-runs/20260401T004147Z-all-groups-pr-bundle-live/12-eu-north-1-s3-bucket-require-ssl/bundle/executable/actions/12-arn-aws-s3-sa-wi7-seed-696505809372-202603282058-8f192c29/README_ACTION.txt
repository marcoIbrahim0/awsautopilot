AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should require requests to use SSL
Action ID: 8f192c29-8cfc-4e0e-a9a4-b5a427bc80ba
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_enforce_ssl_strict_deny
Profile: s3_enforce_ssl_strict_deny

Decision summary: Family resolver kept S3.5 strategy 's3_enforce_ssl_strict_deny' executable because Terraform can merge the current bucket policy at apply time. Runtime capture failed (NoSuchBucket), so the customer-run Terraform bundle must fetch the live policy. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
