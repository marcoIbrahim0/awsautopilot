# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have server access logging enabled
- Action ID: `9482c713-7184-4e01-8452-9a55e9c82b73`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-s9fix1|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-access-logs-696505809372-s9fix1 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `5f5d8617-4da8-4830-a1dc-6b4e98f6b0b0`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-access-logs-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `01557e04-8980-4554-8c32-5a7e78d3cbf3`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket config-bucket-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `0b75c532-0a94-407b-8174-0ae8c85f23f5`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s311-manual-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `1dc612d8-1930-4920-bb11-6ad8ba4fe26b`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-accesslogs-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `4d6a1520-3ed5-4f47-857e-e6bb8ce61606`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-config-696505809372-eu-north-1|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-config-696505809372-eu-north-1 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `4d81e63b-04e6-4909-978a-e779d63ae721`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-config-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `501021f0-ee39-4692-95c1-1d7c07134c71`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-s311-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `dcd9aac0-3205-4c1f-a360-8be492ac384f`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-cloudtrail-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `e03f9f63-e895-46a3-93b3-76c16a0a6ee5`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260323162333-eu-north-1|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket ocypheris-live-ct-20260323162333-eu-north-1 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `e7eb463d-7108-4dff-ba5a-7ba8f2266142`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-s315-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `e8ae2a41-9a3f-43c0-8d89-e574311bf148`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s311-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `e9ca4a12-90e8-4312-82ec-fadfea82a7ce`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-s311-review-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `0c490240-f3b5-42b2-94ce-010ae67bd79f`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.9 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `3dd66962-2bef-4caa-9627-2f056ebabbd7`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s315-manual-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `6069ec49-a8b1-47df-ace8-153c110cd984`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s315-exec-696505809372 --bucket-logging-status '{}'`
