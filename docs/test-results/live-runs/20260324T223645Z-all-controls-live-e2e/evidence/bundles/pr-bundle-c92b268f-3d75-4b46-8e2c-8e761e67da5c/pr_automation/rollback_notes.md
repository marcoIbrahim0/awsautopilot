# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have block public access settings enabled
- Action ID: `4736ed63-fa17-45ea-ab33-5b7c514b31f4`
- Control ID: `S3.1`
- Target: `696505809372|us-east-1|AWS::::Account:696505809372|S3.1`
- Rollback command: `aws s3control delete-public-access-block --account-id 696505809372`
