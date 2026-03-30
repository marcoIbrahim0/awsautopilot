# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should block public access
- Action ID: `688f5ed0-9594-4df1-9883-cc17feca62f8`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi13-14-nopolicy-696505809372-20260328201935|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket sa-wi13-14-nopolicy-696505809372-20260328201935`
