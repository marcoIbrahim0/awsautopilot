# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `26b6f037-9a55-41f4-9fd9-7b49b165ab5f`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/01-arn-aws-s3-security-autopilot-w6-envready-s315-e-26b6f037/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `27b03b08-f50c-4383-aefc-f291aaf8359b`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/02-arn-aws-s3-security-autopilot-w6-envready-cloudt-27b03b08/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `2a74e447-e770-48ed-902f-01c3de6e0074`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/03-arn-aws-s3-security-autopilot-w6-envready-s311-r-2a74e447/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `2aa81941-8053-4643-897e-97cc83c814e2`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/04-arn-aws-s3-security-autopilot-w6-strict-s315-man-2aa81941/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `5612223f-e4a6-449f-a8f0-10ad357c412f`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/05-arn-aws-s3-security-autopilot-w6-envready-access-5612223f/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `56ab9e32-ff18-466c-a572-d951db1a3900`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/06-arn-aws-s3-security-autopilot-w6-strict-s315-exe-56ab9e32/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `6bfdbc7b-1a54-4bb1-b366-ab99ee59a677`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/07-arn-aws-s3-security-autopilot-w6-envready-s311-e-6bfdbc7b/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `96d2e53b-eea0-476e-a73b-cdfd4c0c36fe`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/08-arn-aws-s3-security-autopilot-w6-envready-config-96d2e53b/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `cce5e3c4-1876-4302-b444-d30bd7f7cd8c`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/09-arn-aws-s3-security-autopilot-w6-strict-s311-man-cce5e3c4/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `cef91c15-800d-4d1d-9a25-f961a08779d3`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/10-arn-aws-s3-security-autopilot-w6-strict-s311-exe-cef91c15/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `d9e9b47f-3622-4725-ab20-5324c9e560c7`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/11-arn-aws-s3-config-bucket-696505809372-d9e9b47f/rollback/s3_encryption_restore.py`
