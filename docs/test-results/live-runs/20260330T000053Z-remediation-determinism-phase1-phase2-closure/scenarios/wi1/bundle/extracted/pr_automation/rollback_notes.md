# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 bucket lifecycle rules configured
- Action ID: `8d9e8cc1-949a-412d-8db0-98923b513518`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::wi1-noncurrent-lifecycle-696505809372-20260330003655|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket wi1-noncurrent-lifecycle-696505809372-20260330003655`
