AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have server access logging enabled
Action ID: 257bc11e-c522-4419-8af5-be24ae406691
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enable_access_logging_guided
Profile: s3_enable_access_logging_review_destination_safety

Decision summary: Family resolver downgraded S3.9 to destination-safety review. Source bucket scope could not be proven for S3 access logging; review the affected bucket relationship manually. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
