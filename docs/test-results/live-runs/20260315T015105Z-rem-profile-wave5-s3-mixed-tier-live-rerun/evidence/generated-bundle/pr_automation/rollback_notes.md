# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have server access logging enabled
- Action ID: `bb487cfd-2d28-41a6-8ec3-5f685e4eaa26`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket config-bucket-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `47c023ae-945c-42bf-9b44-018d276046fa`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.9 --bucket-logging-status '{}'`
