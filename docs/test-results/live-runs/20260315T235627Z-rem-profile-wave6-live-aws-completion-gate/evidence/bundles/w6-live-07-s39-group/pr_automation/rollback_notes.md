# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have server access logging enabled
- Action ID: `09eedbef-47fc-4a0c-b056-576a3aafb5d1`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s311-manual-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `3e9757c6-c289-46cc-9b0b-8db375175959`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-s311-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `700311d6-efc6-45a3-b4e4-09782339d3a2`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s315-manual-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `78964522-d996-4c82-9fa5-437ab7f031c7`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-s311-review-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `843e358f-1224-41f0-96f4-01c4626d9fae`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket config-bucket-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `855e6ab2-1daf-4241-a154-21e376b3448a`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-s315-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `8dd30872-a0f9-46ff-84bd-70491c45ac40`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s315-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `e2696a99-0285-4e32-9212-4412c179e4fa`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-accesslogs-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `eabe460f-fe71-44d0-a055-4cff617b4062`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-config-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `f040f00b-5016-409a-9a73-616b6478c688`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s311-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `f291cce1-9732-4f95-a48e-d98a1d5613ea`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-cloudtrail-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `19a73839-da61-4fcc-8fa9-8e29e4d1114b`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.9 --bucket-logging-status '{}'`
