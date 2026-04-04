AWS Security Autopilot — Group action artifact

Action: S3 bucket enforces SSL requests
Action ID: 329b2b93-2959-430e-8a83-6d963ddce512
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_enforce_ssl_strict_deny
Profile: s3_enforce_ssl_strict_deny

Decision summary: Family resolver kept S3.5 strategy 's3_enforce_ssl_strict_deny' executable because Terraform can merge the current bucket policy at apply time. Runtime capture failed (NoSuchBucket), so the customer-run Terraform bundle must fetch the live policy. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
