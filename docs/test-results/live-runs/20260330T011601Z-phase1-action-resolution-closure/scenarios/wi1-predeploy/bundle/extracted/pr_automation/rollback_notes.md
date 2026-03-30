# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `54b0d584-d60a-409d-86e3-5458bd8054b1`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-s311-exec-696505809372`
