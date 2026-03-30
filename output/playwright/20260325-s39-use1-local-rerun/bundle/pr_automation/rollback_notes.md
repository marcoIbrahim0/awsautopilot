# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have server access logging enabled
- Action ID: `c6c920fd-b9f6-4015-8ede-a072d5ad22c5`
- Control ID: `S3.9`
- Target: `696505809372|us-east-1|arn:aws:s3:::security-autopilot-config-696505809372-us-east-1|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-config-696505809372-us-east-1 --bucket-logging-status '{}'`
