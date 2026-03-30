# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have server access logging enabled
- Action ID: `19a9b0f0-de47-4a5b-982f-8d3c876c2064`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-access-logs-696505809372-r221001 --bucket-logging-status '{}'`
