# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `16bf867f-5042-4cae-99d2-c406884b4c96`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket security-autopilot-w6-strict-s315-exec-696505809372`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `17efd185-198a-41c4-8454-10875aa89daa`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket config-bucket-696505809372`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `2cb83746-c068-4def-977b-fd4bfead2519`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket security-autopilot-w6-envready-s311-exec-696505809372`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `344850ee-796d-4fbc-9906-e745aafb2df6`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket security-autopilot-w6-envready-s311-review-696505809372`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `38a640b1-62eb-4deb-bd64-2d8aeb249982`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket security-autopilot-w6-envready-config-696505809372`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `4b0b3e4f-bbe8-4c58-b9c1-ca39c8683ca2`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket security-autopilot-w6-strict-s311-exec-696505809372`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `609bb8db-3bd6-4dbc-b562-e9430a4bdaeb`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket security-autopilot-w6-envready-s315-exec-696505809372`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `adc97f08-1aaf-4280-84f3-854f21361f66`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket security-autopilot-w6-envready-accesslogs-696505809372`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `bdcc1a33-8d37-4d01-8ac8-5bfa39b11a1d`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket security-autopilot-w6-envready-cloudtrail-696505809372`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `dd64810c-7d83-4b46-9c8e-5f3b400be8d2`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket security-autopilot-w6-strict-s311-manual-696505809372`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `f04ba1eb-b150-40a0-94a5-4087d0231c32`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket security-autopilot-w6-strict-s315-manual-696505809372`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `0242a107-32fa-44f3-bca8-820d14c20aff`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.5`
- Rollback command: `aws s3api delete-bucket-policy --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.5`
