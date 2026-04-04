# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `0ca99079-34e6-4c17-b121-b1f1727494eb`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-strict-s311-exec-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `129fa65e-11e1-4eb0-bf8f-dff5fec13487`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-strict-s315-exec-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `23bf691b-8ec2-4920-80a8-09bca2b8e218`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-envready-cloudtrail-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `4da3d806-4084-4075-8f3c-221d08ef5c2c`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-strict-s315-manual-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `61552073-d604-4ba5-8430-b04485f90a5c`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-envready-s311-review-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `967d71a9-8027-4223-b6c6-aa5578d1d2d5`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-strict-s311-manual-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `9e4562df-9922-4f75-b4e4-2d17c2c615f8`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-envready-s311-exec-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `b84115cb-a701-48d7-832c-4fbcf80b8724`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-envready-accesslogs-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `b8a67bbf-1255-40f1-ab21-569689459a36`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-envready-s315-exec-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `c1c2ed6d-408b-4743-86d9-0fedeff97ce6`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-w6-envready-config-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `830944d9-30ad-432f-a84e-e09c0dde3d5d`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket config-bucket-696505809372 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `3970aa2f-edc5-4870-87bd-fa986dad3d98`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-evidence-b1-696505809372-eu-north-1|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket arch1-bucket-evidence-b1-696505809372-eu-north-1 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `53b7b063-8531-4829-9b23-f03b1796b23d`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-website-a1-696505809372-eu-north-1|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket arch1-bucket-website-a1-696505809372-eu-north-1 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `6826cb31-57ad-4704-8b2f-3f2387125e8e`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi13-14-nopolicy-696505809372-20260328201935|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket sa-wi13-14-nopolicy-696505809372-20260328201935 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `2ac461ec-b4c1-4fcd-8ae1-a6d18f53c8d4`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.5 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `0eb4440d-ae39-46c1-80b8-a04d04f7a8bc`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001-access-logs|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-access-logs-696505809372-r221001-access-logs --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `205f94f3-d76b-4a08-8082-253013ff9857`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::wi1-noncurrent-lifecycle-696505809372-20260330003655|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket wi1-noncurrent-lifecycle-696505809372-20260330003655 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `3b2f7c5d-00dc-4a60-a146-e66a3427d902`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi7-seed-696505809372-20260328205857|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket sa-wi7-seed-696505809372-20260328205857 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `413846db-f9af-4910-9192-d17c79c6153e`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260328t181200z-eu-north-1|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket ocypheris-live-ct-20260328t181200z-eu-north-1 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `44920b7c-8125-4998-bc91-3ad537601670`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329002042|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket phase2-wi1-lifecycle-696505809372-20260329002042 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `bd4da43a-91bc-4b0b-84d7-9ca776af9210`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329004157|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket phase2-wi1-lifecycle-696505809372-20260329004157 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `ceb048a5-805e-4a13-978b-e8ed9e3c82ea`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260328224331|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket phase2-wi1-lifecycle-696505809372-20260328224331 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `cfdc868f-5a50-4188-b770-77f7082b3c06`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi5-site-696505809372-20260328t164043z|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket sa-wi5-site-696505809372-20260328t164043z --policy file://pre-remediation-policy.json`

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
