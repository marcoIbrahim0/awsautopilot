# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `82ed26b1-d9ac-469b-8008-a2acdc89bd38`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s311-manual-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `a1d8f3bf-e381-47d6-9818-1a3096292381`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s315-manual-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `c533dff3-a0f0-4d76-8dd3-19315fb3e47d`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s315-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `e55dca93-6467-4dce-ba6c-16444f259760`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket config-bucket-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `4a5a765e-cf7d-40bf-91c2-19a361d242ae`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.11`
