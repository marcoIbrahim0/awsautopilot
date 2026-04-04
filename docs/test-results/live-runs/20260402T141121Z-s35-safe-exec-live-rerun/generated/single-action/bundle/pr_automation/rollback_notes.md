# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `3970aa2f-edc5-4870-87bd-fa986dad3d98`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-evidence-b1-696505809372-eu-north-1|S3.5`
- Rollback command: `python3 ./rollback/s3_policy_restore.py`
