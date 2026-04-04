AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should have server access logging enabled
Action ID: f9535173-3de1-44d0-8583-ee937e1ad811
Tier: review_required
Tier root: review_required/actions
Outcome: review_required_metadata_only
Strategy: s3_enable_access_logging_guided
Profile: s3_enable_access_logging_review_destination_safety

Decision summary: Family resolver downgraded S3.9 to destination-safety review. Destination log bucket 'security-autopilot-w6-strict-s315-manual-6965058093-access-logs' could not be verified from this account context (403). Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
