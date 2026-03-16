# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `006b6ba6-a9f5-4b15-97c1-2616b7d9b2c8`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket config-bucket-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `00b8c39c-69a4-4557-8c73-7d96e4d72c19`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s315-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `1df0126d-d424-41cd-b05f-c3079742e4b4`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s311-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `3f68cef8-5029-43d9-ad41-ee0bb78e8815`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-config-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `7df28662-2e76-467c-af12-9128c94f31d9`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-s315-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `7f624e07-61ea-4cf1-ba9f-93b51899dc7c`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-accesslogs-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `81625b6a-51fe-4d25-8869-b010421919a3`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-s311-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `92f5f5a3-d6c0-4cc4-b349-e90940a1e78a`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s315-manual-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `9c62231f-8f9f-4972-bbcd-4260f5d5dc02`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-cloudtrail-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `d6eb9cb9-3325-4a5e-a250-760c0026ff10`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s311-manual-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `c9716eb3-ee4d-4a92-af2f-464fdabb994e`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.11`
