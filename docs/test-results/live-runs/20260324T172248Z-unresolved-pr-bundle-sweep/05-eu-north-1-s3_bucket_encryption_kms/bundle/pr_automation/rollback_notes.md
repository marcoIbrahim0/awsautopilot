# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `42356c4a-b399-4e15-b055-3870a370da3d`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260323162333-eu-north-1|S3.15`
- Rollback command: `python3 ./executable/actions/01-arn-aws-s3-ocypheris-live-ct-20260323162333-eu-n-42356c4a/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `88e42d27-d1ed-4efe-9bf8-6b6d7b6b6c2c`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-config-696505809372-eu-north-1|S3.15`
- Rollback command: `python3 ./executable/actions/02-arn-aws-s3-security-autopilot-config-69650580937-88e42d27/rollback/s3_encryption_restore.py`
