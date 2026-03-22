# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should block public access
- Action ID: `a5bbba51-b5a8-4176-8f93-e9d0c376ade5`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-w6-envready-s311-review-696505809372`

## S3 general purpose buckets should block public access
- Action ID: `b32b4a18-4da2-4f94-acf3-0ec4f2e555db`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-w6-envready-s315-exec-696505809372`

## S3 general purpose buckets should block public write access
- Action ID: `0d206e57-2a9a-4d7e-abda-da73a5e93695`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.2`
