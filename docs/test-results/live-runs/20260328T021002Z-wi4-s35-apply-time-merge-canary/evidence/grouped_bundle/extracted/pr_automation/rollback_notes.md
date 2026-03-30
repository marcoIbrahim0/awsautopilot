# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `29f0d788-90f3-48e4-96d7-8ed0657924a6`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r222018|S3.5`
- Rollback command: `python3 ./executable/actions/01-arn-aws-s3-security-autopilot-access-logs-696505-29f0d788/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `424d65bb-5bd8-4ba3-a5ca-9785fbb41bb9`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r94854|S3.5`
- Rollback command: `python3 ./executable/actions/02-arn-aws-s3-security-autopilot-access-logs-696505-424d65bb/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `7a438b0e-37e8-444e-a211-04a906891a69`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001|S3.5`
- Rollback command: `python3 ./executable/actions/03-arn-aws-s3-security-autopilot-access-logs-696505-7a438b0e/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `251b980d-17a9-4fae-8e5f-e2ca38d389ed`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.5 --policy file://pre-remediation-policy.json`
