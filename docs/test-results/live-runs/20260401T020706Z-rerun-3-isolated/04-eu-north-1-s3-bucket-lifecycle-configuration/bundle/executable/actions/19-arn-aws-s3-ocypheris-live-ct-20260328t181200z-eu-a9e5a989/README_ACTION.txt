AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have Lifecycle configurations
Action ID: a9e5a989-3dba-4114-aeaf-2ddac120ac0c
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: s3_enable_abort_incomplete_uploads
Profile: s3_enable_abort_incomplete_uploads

Decision summary: Family resolver kept S3.11 strategy 's3_enable_abort_incomplete_uploads' executable with abort_days=7 because Terraform can fetch and merge the current lifecycle configuration at apply time. Runtime capture failed (NoSuchBucket), so the customer-run Terraform bundle must fetch and merge the live lifecycle configuration. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
