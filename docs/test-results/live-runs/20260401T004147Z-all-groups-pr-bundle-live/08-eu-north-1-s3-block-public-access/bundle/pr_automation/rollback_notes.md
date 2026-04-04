# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have block public access settings enabled
- Action ID: `18e459b1-3bc2-47b4-a520-c955e921c75f`
- Control ID: `S3.1`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.1`
- Rollback command: `aws s3control delete-public-access-block --account-id 696505809372`
