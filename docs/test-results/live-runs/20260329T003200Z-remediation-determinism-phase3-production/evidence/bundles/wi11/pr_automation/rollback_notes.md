# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `8ab29997-bb6c-41fe-ba0c-26f03523f0ed`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001|S3.11`
- Rollback command: `python3 ./rollback/s3_lifecycle_restore.py`
