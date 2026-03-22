# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `33bd3255-47a8-423b-b6c6-c6363891c9d6`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/01-arn-aws-s3-config-bucket-696505809372-33bd3255/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `3575f46f-a5ca-4c3d-987d-ff74e103b397`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/02-arn-aws-s3-security-autopilot-w6-envready-cloudt-3575f46f/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `44f6df0a-6a2c-442b-b328-b90cb153794d`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/03-arn-aws-s3-security-autopilot-w6-strict-s315-exe-44f6df0a/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `478ebc2f-d253-4454-9e47-667493f7057a`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/04-arn-aws-s3-security-autopilot-w6-envready-access-478ebc2f/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `52947557-0b35-4c03-99d6-4fdf77c86a24`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.15`
- Rollback command: `if [ -f pre-remediation-encryption.json ]; then aws s3api put-bucket-encryption --bucket security-autopilot-w6-strict-s315-manual-696505809372 --server-side-encryption-configuration file://pre-remediation-encryption.json; else aws s3api delete-bucket-encryption --bucket security-autopilot-w6-strict-s315-manual-696505809372; fi`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `66a5dd43-b001-4519-b072-4acf8d7514dd`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/06-arn-aws-s3-security-autopilot-w6-strict-s311-man-66a5dd43/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `7a0e2c57-1ff4-47ae-a4a8-4b26efe6a3d6`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/07-arn-aws-s3-security-autopilot-w6-strict-s311-exe-7a0e2c57/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `7b9ca8b1-6e78-41ed-96b9-34af5d4a782a`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/08-arn-aws-s3-security-autopilot-w6-envready-s315-e-7b9ca8b1/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `7bf8c034-522a-491a-a23a-72554632d485`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/09-arn-aws-s3-security-autopilot-w6-envready-s311-e-7bf8c034/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `7f85a353-5965-4663-b5ea-9a2016cfe495`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/10-arn-aws-s3-security-autopilot-w6-envready-s311-r-7f85a353/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `d5646c71-f765-4bef-92d6-cfb25502aa85`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.15`
- Rollback command: `python3 ./executable/actions/11-arn-aws-s3-security-autopilot-w6-envready-config-d5646c71/rollback/s3_encryption_restore.py`
