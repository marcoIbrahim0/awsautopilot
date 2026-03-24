# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `03bbb5fd-0d45-472e-91f7-b0dc98d8091f`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260323162333-eu-north-1|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket ocypheris-live-ct-20260323162333-eu-north-1`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `bc116f71-a480-40ab-8b97-b1217eec9a65`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-config-696505809372-eu-north-1|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-config-696505809372-eu-north-1`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `4a5a765e-cf7d-40bf-91c2-19a361d242ae`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.11`
