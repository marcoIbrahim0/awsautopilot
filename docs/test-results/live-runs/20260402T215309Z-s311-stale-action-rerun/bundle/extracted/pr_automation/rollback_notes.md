# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `06464919-c27d-4ade-9a70-3569e87706a6`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329004157|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket phase2-wi1-lifecycle-696505809372-20260329004157`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `14ffeb41-201d-4c56-b29e-1d6fabb53ef9`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi7-seed-696505809372-20260328205857|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket sa-wi7-seed-696505809372-20260328205857`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `3bab593b-c8b3-449b-9f85-209831976292`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260328t181200z-eu-north-1|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket ocypheris-live-ct-20260328t181200z-eu-north-1`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `63f91a78-96e9-49be-b4d7-d05e69730fdf`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329002042|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket phase2-wi1-lifecycle-696505809372-20260329002042`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `d8b98d62-2940-4504-a750-f0f50c11a75c`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::wi1-noncurrent-lifecycle-696505809372-20260330003655|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket wi1-noncurrent-lifecycle-696505809372-20260330003655`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `e4bf59d8-72fd-48b8-a4dc-47cccbfd7fed`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi5-site-696505809372-20260328t164043z|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket sa-wi5-site-696505809372-20260328t164043z`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `e65afccb-8104-471c-88a4-fab226a07413`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260328224331|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket phase2-wi1-lifecycle-696505809372-20260328224331`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `4a5a765e-cf7d-40bf-91c2-19a361d242ae`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.11`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `0ebbf82c-ff48-45a1-8fd7-3a4688788ced`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001-access-logs|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-access-logs-696505809372-r221001-access-logs`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `3b58320d-f3a4-4ccc-b1ff-474f6b822aa8`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s311-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `46d8436f-47e7-4518-9c40-dc187c73a567`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-s315-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `7c75dd09-67b0-4e58-9000-6e570fea8369`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-config-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `838f4503-7869-438b-a52a-88548b0ed727`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-cloudtrail-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `b8506dba-9edb-4774-8446-4baedc8fa189`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-accesslogs-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `ea2b71a1-80df-4dd7-8510-a300fec9dfec`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-s311-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `03bbb5fd-0d45-472e-91f7-b0dc98d8091f`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260323162333-eu-north-1|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket ocypheris-live-ct-20260323162333-eu-north-1`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `bc116f71-a480-40ab-8b97-b1217eec9a65`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-config-696505809372-eu-north-1|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-config-696505809372-eu-north-1`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `82ed26b1-d9ac-469b-8008-a2acdc89bd38`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s311-manual-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `a1d8f3bf-e381-47d6-9818-1a3096292381`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s315-manual-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `c533dff3-a0f0-4d76-8dd3-19315fb3e47d`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s315-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `e55dca93-6467-4dce-ba6c-16444f259760`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket config-bucket-696505809372`
