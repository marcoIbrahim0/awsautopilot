# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `4fc6db43-ea06-4afc-a670-2ca8d0495070`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260323162333-eu-north-1|S3.5`
- Rollback command: `python3 ./executable/actions/01-arn-aws-s3-ocypheris-live-ct-20260323162333-eu-n-4fc6db43/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `b9d3ffd9-6193-48ba-a02d-5835b1c120ad`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-config-696505809372-eu-north-1|S3.5`
- Rollback command: `python3 ./executable/actions/02-arn-aws-s3-security-autopilot-config-69650580937-b9d3ffd9/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `1e453177-31da-47ec-bfce-796fcebc9e4b`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.5 --policy file://pre-remediation-policy.json`
