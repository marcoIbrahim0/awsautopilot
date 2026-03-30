# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should block public access
- Action ID: `0b87839b-28f5-4150-af26-74cf2b1af3a3`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-w6-envready-s315-exec-696505809372`
