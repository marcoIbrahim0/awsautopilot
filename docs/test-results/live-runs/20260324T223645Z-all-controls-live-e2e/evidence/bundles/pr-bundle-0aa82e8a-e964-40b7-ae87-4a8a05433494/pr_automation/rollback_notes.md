# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `ebc71992-6c74-415e-9637-4ec1984c5322`
- Control ID: `S3.5`
- Target: `696505809372|us-east-1|arn:aws:s3:::security-autopilot-config-696505809372-us-east-1|S3.5`
- Rollback command: `python3 ./executable/actions/01-arn-aws-s3-security-autopilot-config-69650580937-ebc71992/rollback/s3_policy_restore.py`
