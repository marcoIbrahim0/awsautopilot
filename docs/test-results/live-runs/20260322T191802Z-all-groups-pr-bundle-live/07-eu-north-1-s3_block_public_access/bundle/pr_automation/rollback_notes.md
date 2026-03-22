# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have block public access settings enabled
- Action ID: `62e7ff0d-5dd5-4ccd-a2d8-f62b4f0d7e8b`
- Control ID: `S3.1`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.1`
- Rollback command: `aws s3control delete-public-access-block --account-id 696505809372`
