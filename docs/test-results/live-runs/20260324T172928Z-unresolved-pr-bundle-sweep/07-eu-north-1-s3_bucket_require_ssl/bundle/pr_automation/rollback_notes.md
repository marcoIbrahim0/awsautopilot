# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `1b7e11a5-3b38-4701-8938-a3986235a53a`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-config-696505809372-eu-north-1|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-config-696505809372-eu-north-1 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `9444f510-d008-4009-8a13-ff4ecc8d3ff8`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260323162333-eu-north-1|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket ocypheris-live-ct-20260323162333-eu-north-1 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `2ac461ec-b4c1-4fcd-8ae1-a6d18f53c8d4`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.5 --policy file://pre-remediation-policy.json`
