# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have server access logging enabled
- Action ID: `0c490240-f3b5-42b2-94ce-010ae67bd79f`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.9 --bucket-logging-status '{}'`
