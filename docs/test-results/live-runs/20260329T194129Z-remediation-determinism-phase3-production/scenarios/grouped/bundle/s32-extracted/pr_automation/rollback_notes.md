# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should block public access
- Action ID: `688f5ed0-9594-4df1-9883-cc17feca62f8`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi13-14-nopolicy-696505809372-20260328201935|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket sa-wi13-14-nopolicy-696505809372-20260328201935`

## S3 general purpose buckets should block public access
- Action ID: `0b87839b-28f5-4150-af26-74cf2b1af3a3`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-w6-envready-s315-exec-696505809372`

## S3 general purpose buckets should block public access
- Action ID: `352ac9b2-d343-40ac-b427-4c4f285615ef`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-w6-envready-s311-review-696505809372`

## S3 general purpose buckets should block public write access
- Action ID: `08a9f629-3bfa-46a1-bd88-e22027f7e133`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.2`

## S3 general purpose buckets should block public read access
- Action ID: `e88846fa-71d2-4291-ae12-2c13b1b49544`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329002042|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket phase2-wi1-lifecycle-696505809372-20260329002042`

## S3 general purpose buckets should block public read access
- Action ID: `7522bc9f-5cab-4bad-908b-a382045f8d87`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260328224331|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket phase2-wi1-lifecycle-696505809372-20260328224331`

## S3 general purpose buckets should block public access
- Action ID: `4a965fac-c139-46e3-8594-11058b1dfe24`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi7-seed-696505809372-20260328205857|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket sa-wi7-seed-696505809372-20260328205857`

## S3 general purpose buckets should block public write access
- Action ID: `cdb53f5c-8701-497d-a866-4256cddd9d66`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260328t181200z-eu-north-1|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket ocypheris-live-ct-20260328t181200z-eu-north-1`

## S3 general purpose buckets should block public access
- Action ID: `5571e909-6491-4077-818e-5441ae0dc95d`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-access-logs-696505809372-r221001-access-logs`

## S3 general purpose buckets should block public access
- Action ID: `bdfa85bc-b3a3-4456-b8d9-9ed1dd895ad3`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi5-site-696505809372-20260328t164043z|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket sa-wi5-site-696505809372-20260328t164043z`
