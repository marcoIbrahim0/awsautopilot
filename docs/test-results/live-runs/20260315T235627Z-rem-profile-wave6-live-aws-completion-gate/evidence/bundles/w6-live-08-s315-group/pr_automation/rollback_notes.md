# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `023e8b64-4ff6-4f0a-a074-d8ed4e6a31ff`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.15`
- Rollback command: `aws s3api put-bucket-encryption --bucket security-autopilot-w6-envready-cloudtrail-696505809372 --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `080ad0ec-b379-4cb5-9f7a-aecdd997ab11`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.15`
- Rollback command: `aws s3api put-bucket-encryption --bucket security-autopilot-w6-strict-s315-exec-696505809372 --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `216bc880-fda0-40ec-bf75-caf45d820645`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.15`
- Rollback command: `aws s3api put-bucket-encryption --bucket config-bucket-696505809372 --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `2e5d6e74-73e1-47e6-9c00-32c290f1d198`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.15`
- Rollback command: `aws s3api put-bucket-encryption --bucket security-autopilot-w6-envready-s311-exec-696505809372 --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `31381d3c-04f9-4613-a897-ba95ddbdc0bd`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.15`
- Rollback command: `aws s3api put-bucket-encryption --bucket security-autopilot-w6-strict-s315-manual-696505809372 --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `3cea24eb-54ca-412e-aa04-f0d0da1d9d9b`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.15`
- Rollback command: `aws s3api put-bucket-encryption --bucket security-autopilot-w6-envready-accesslogs-696505809372 --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `44196b82-644c-4451-8539-519a81796192`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.15`
- Rollback command: `aws s3api put-bucket-encryption --bucket security-autopilot-w6-strict-s311-exec-696505809372 --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `6ed02911-7dfc-46f8-96dc-320c25f5793a`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.15`
- Rollback command: `aws s3api put-bucket-encryption --bucket security-autopilot-w6-strict-s311-manual-696505809372 --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `777749c0-1137-475b-a102-b128b791beaa`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.15`
- Rollback command: `aws s3api put-bucket-encryption --bucket security-autopilot-w6-envready-config-696505809372 --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `94253f6e-4bd3-40f5-97e3-7bdc9530fbbf`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.15`
- Rollback command: `aws s3api put-bucket-encryption --bucket security-autopilot-w6-envready-s311-review-696505809372 --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `be206765-a453-475d-a722-95adea63dd53`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.15`
- Rollback command: `aws s3api put-bucket-encryption --bucket security-autopilot-w6-envready-s315-exec-696505809372 --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'`
