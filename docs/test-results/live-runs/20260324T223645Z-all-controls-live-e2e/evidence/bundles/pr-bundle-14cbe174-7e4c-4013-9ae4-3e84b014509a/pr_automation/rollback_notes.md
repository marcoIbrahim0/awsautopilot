# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `53cda243-1815-4864-8cc3-f3e1535a4ff1`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260323162333-eu-north-1|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket ocypheris-live-ct-20260323162333-eu-north-1`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `a57bd4fc-c54f-4965-baa9-a675d386a043`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-config-696505809372-eu-north-1|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-config-696505809372-eu-north-1`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `7be937c3-8b96-413e-881b-94118a699913`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.11`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `0361bcde-869c-4b55-913d-ed8bea424a7e`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-s315-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `42eef23b-f9ba-4381-b8af-028529231a84`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-s311-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `4e5dc9e9-0763-45f4-a601-1bfd54c83038`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s315-manual-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `50b7681f-6f96-45f7-bb75-06cb8bb9074d`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s315-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `6a75c127-7fcb-4320-b54b-dbe856f727c6`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-accesslogs-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `88c01f62-9a6b-4bd6-9e1f-eb7592845ce2`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s311-manual-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `c81bf06a-bf7a-42d6-b154-8c1a97739781`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-cloudtrail-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `cbb438f0-4e9a-489e-b7cf-2ef5dd95edf3`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s311-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `d42826b3-0611-4b29-a27a-726c53c00a50`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-config-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `d5f1fd68-4ae6-46b1-8ddf-33f168eeed8c`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket config-bucket-696505809372`
