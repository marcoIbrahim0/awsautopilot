AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should require requests to use SSL
Action ID: bcd7f695-772d-418b-921b-a2f9ca3eaa47
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_enforce_ssl_strict_deny
Profile: s3_enforce_ssl_strict_deny

Decision summary: Family resolver kept S3.5 strategy 's3_enforce_ssl_strict_deny' executable because Terraform can merge the current bucket policy at apply time. Runtime capture failed (NoSuchBucket), so the customer-run Terraform bundle must fetch the live policy. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
