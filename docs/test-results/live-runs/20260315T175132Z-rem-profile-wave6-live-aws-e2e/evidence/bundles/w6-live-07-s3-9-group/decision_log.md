# Decision Log

## 1. S3 general purpose buckets should have server access logging enabled
- Action ID: bee5888e-8c14-43f2-87f6-77b9fcd8c4aa
- Tier: review_required/actions
- Outcome: review_required_metadata_only
- Strategy/Profile: s3_enable_access_logging_guided / s3_enable_access_logging_review_destination_safety
- Summary: Family resolver downgraded S3.9 to destination-safety review. Log destination must be a dedicated bucket and cannot match the source bucket. Run creation did not require additional risk-only acceptance.

## 2. S3 general purpose buckets should have server access logging enabled
- Action ID: d7f868c5-9a64-4aca-bff0-aabb06b3c104
- Tier: review_required/actions
- Outcome: review_required_metadata_only
- Strategy/Profile: s3_enable_access_logging_guided / s3_enable_access_logging_review_destination_safety
- Summary: Family resolver downgraded S3.9 to destination-safety review. Destination log bucket 'config-bucket-696505809372' could not be verified from this account context (403). Run creation did not require additional risk-only acceptance.

