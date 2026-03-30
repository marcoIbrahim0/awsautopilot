# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `e6b552a4-4461-4de5-9a7b-15ff0a1b4485`
- Control ID: `S3.11`
- Target: `696505809372|us-east-1|arn:aws:s3:::security-autopilot-config-696505809372-us-east-1|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-config-696505809372-us-east-1`
