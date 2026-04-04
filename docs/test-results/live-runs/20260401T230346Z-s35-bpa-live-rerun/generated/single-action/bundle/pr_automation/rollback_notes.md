# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `53b7b063-8531-4829-9b23-f03b1796b23d`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-website-a1-696505809372-eu-north-1|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket arch1-bucket-website-a1-696505809372-eu-north-1 --policy file://pre-remediation-policy.json`
