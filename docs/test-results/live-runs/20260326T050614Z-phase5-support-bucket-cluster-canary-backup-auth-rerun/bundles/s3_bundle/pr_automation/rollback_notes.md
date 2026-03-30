# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have server access logging enabled
- Action ID: `5f5d8617-4da8-4830-a1dc-6b4e98f6b0b0`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-access-logs-696505809372 --bucket-logging-status '{}'`
