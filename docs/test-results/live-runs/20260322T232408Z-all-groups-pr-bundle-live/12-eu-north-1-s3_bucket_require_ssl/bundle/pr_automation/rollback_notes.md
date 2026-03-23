# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `0ca99079-34e6-4c17-b121-b1f1727494eb`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.5`
- Rollback command: `python3 ./executable/actions/01-arn-aws-s3-security-autopilot-w6-strict-s311-exe-0ca99079/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `129fa65e-11e1-4eb0-bf8f-dff5fec13487`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.5`
- Rollback command: `python3 ./executable/actions/02-arn-aws-s3-security-autopilot-w6-strict-s315-exe-129fa65e/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `23bf691b-8ec2-4920-80a8-09bca2b8e218`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.5`
- Rollback command: `python3 ./executable/actions/03-arn-aws-s3-security-autopilot-w6-envready-cloudt-23bf691b/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `4da3d806-4084-4075-8f3c-221d08ef5c2c`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.5`
- Rollback command: `python3 ./executable/actions/04-arn-aws-s3-security-autopilot-w6-strict-s315-man-4da3d806/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `61552073-d604-4ba5-8430-b04485f90a5c`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.5`
- Rollback command: `python3 ./executable/actions/05-arn-aws-s3-security-autopilot-w6-envready-s311-r-61552073/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `967d71a9-8027-4223-b6c6-aa5578d1d2d5`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.5`
- Rollback command: `python3 ./executable/actions/06-arn-aws-s3-security-autopilot-w6-strict-s311-man-967d71a9/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `9e4562df-9922-4f75-b4e4-2d17c2c615f8`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.5`
- Rollback command: `python3 ./executable/actions/07-arn-aws-s3-security-autopilot-w6-envready-s311-e-9e4562df/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `b84115cb-a701-48d7-832c-4fbcf80b8724`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.5`
- Rollback command: `python3 ./executable/actions/08-arn-aws-s3-security-autopilot-w6-envready-access-b84115cb/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `b8a67bbf-1255-40f1-ab21-569689459a36`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.5`
- Rollback command: `python3 ./executable/actions/09-arn-aws-s3-security-autopilot-w6-envready-s315-e-b8a67bbf/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `c1c2ed6d-408b-4743-86d9-0fedeff97ce6`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.5`
- Rollback command: `python3 ./executable/actions/10-arn-aws-s3-security-autopilot-w6-envready-config-c1c2ed6d/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `830944d9-30ad-432f-a84e-e09c0dde3d5d`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.5`
- Rollback command: `python3 ./executable/actions/11-arn-aws-s3-config-bucket-696505809372-830944d9/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `2ac461ec-b4c1-4fcd-8ae1-a6d18f53c8d4`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.5 --policy file://pre-remediation-policy.json`
