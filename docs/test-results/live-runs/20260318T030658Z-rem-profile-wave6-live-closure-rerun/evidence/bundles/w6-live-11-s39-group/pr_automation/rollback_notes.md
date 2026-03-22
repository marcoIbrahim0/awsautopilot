# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have server access logging enabled
- Action ID: `153ff5f9-68f3-422b-908d-60ffaa2551df`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s311-manual-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `26a3f7f0-39fd-493c-b1c0-12ded95ac297`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s311-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `63b65b24-7dcb-4c95-a781-97dd727cd6a6`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-s315-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `6476e319-0eb7-4ac3-8b94-68416dc77680`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket config-bucket-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `73e55a5b-53c9-436e-b31e-6c6df14ee70c`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s315-manual-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `c3c57258-48ac-4cf2-a1ff-8107046e170e`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-strict-s315-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `cb4e035c-2b67-4f78-98fe-d4bc9f02ee96`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-accesslogs-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `cf808204-b046-4705-bbaf-7e9ed55af535`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-cloudtrail-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `d74e91e3-3b34-408b-b330-018d5eee4e3e`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-config-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `ea1fda0c-4427-413e-b768-4b1a13c1e479`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-s311-review-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `f90e7d9d-8944-4f39-bce8-0659a3635e8d`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-w6-envready-s311-exec-696505809372 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `3d31d678-fd39-4ceb-8804-dc8796ab27f5`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.9 --bucket-logging-status '{}'`
