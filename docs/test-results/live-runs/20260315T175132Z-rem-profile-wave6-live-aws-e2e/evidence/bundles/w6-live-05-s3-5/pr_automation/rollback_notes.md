# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `dc64daaa-a4d4-4352-be62-edfaee3e459a`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket config-bucket-696505809372`
