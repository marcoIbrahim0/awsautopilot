# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should block public access
- Action ID: `abf5eb48-ea9b-48d0-a534-236cf8818bf9`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-w6-envready-s311-review-696505809372`

## S3 general purpose buckets should block public access
- Action ID: `f497bc0c-ddcb-4191-8fa5-c6ed21bbe134`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-w6-envready-s315-exec-696505809372`

## S3 general purpose buckets should block public write access
- Action ID: `19337c80-843c-40fb-b35c-fd561406009f`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.2`
