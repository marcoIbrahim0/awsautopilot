# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `0a562f26-7ce8-4719-8c3f-d28bef4e543c`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket config-bucket-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `2b020c20-95a0-4e29-b388-7b764938ad15`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-strict-s311-manual-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `332a7d6f-cdad-47e4-ab8b-6d8459248940`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-envready-cloudtrail-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `4ca36a85-06a1-48f4-ac75-8df356c01eb9`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-envready-s315-exec-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `61c4ed80-2778-42a0-b0f2-4ff1095f9037`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-strict-s315-manual-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `64650bcf-00f3-47d2-be39-3cf770e4e26b`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-envready-s311-exec-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `8e4a902d-b01d-4fea-9e84-fefe33831ec9`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-envready-config-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `8f1b6cf5-9eca-45e5-be35-b5851d345a38`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-strict-s311-exec-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `9c99cd7e-07c5-4ebe-9989-5c172053b64f`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-strict-s315-exec-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `eabfe19e-7403-49db-a944-a0b236107554`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-envready-accesslogs-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `f3110269-c964-4b9d-9db2-380977476c39`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-envready-s311-review-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `c89e2c01-cda1-4d35-8945-cca8096b8b60`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.5 --policy file://pre-remediation-policy.json`
