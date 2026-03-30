# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `7a438b0e-37e8-444e-a211-04a906891a69`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001|S3.5`
- Rollback command: `python3 ./rollback/s3_policy_restore.py`
