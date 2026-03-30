# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should block public access
- Action ID: `b0ec883a-f08d-4480-a5f6-807446f9ad8b`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-w6-envready-s315-exec-696505809372`

## S3 general purpose buckets should block public access
- Action ID: `c1a8dbfb-67f0-4656-bf8e-6f95b3bc04a0`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-w6-envready-s311-review-696505809372`

## S3 general purpose buckets should block public write access
- Action ID: `fb0b3cc7-2dd7-4c4c-8cac-26caaaec29b5`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.2`
