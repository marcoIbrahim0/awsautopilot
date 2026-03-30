# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `78237cc2-e47f-4f0f-80de-22b08d8725c7`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi13-14-nopolicy-696505809372-20260328201935|S3.5`
- Rollback command: `python3 ./rollback/s3_policy_restore.py`
