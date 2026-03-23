# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have server access logging enabled
- Action ID: `318c8b1d-0a93-43f0-9b32-24014b6dbf15`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-cloudtrail-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `6ba6522c-a1d9-48bd-ab96-b6129f4363b8`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-s311-review-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `770a4f18-3858-4efd-8973-a39d154fa919`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-s315-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `82072bfa-7707-411b-ab5a-4b8a75bef104`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-accesslogs-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `8499e226-d3e8-4031-b225-9f905160ef5f`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s311-manual-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `a8a06ade-67b9-4b5b-89df-1f4f430036a5`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s315-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `e97ffef8-f6f9-4417-ac99-0e83305df718`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-s311-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `ece8a96e-8e9c-44de-a715-d0b7caa061c1`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s311-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `f67a9064-2a5f-47fd-820c-15797f354c7c`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-config-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `f9535173-3de1-44d0-8583-ee937e1ad811`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s315-manual-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `8f64dd84-763c-4081-ad1e-9a36757b5c87`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket config-bucket-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `257bc11e-c522-4419-8af5-be24ae406691`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.9 --bucket-logging-status '{}'`
