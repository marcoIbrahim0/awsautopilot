# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should require requests to use SSL
- Action ID: `7451c997-3ebc-48cc-a67e-c35b3dbb76b1`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-evidence-b1-696505809372-eu-north-1|S3.5`
- Rollback command: `python3 ./executable/actions/01-arn-aws-s3-arch1-bucket-evidence-b1-696505809372-7451c997/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `f791c98c-ec11-4af7-9f19-abf8ebc44d21`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-website-a1-696505809372-eu-north-1|S3.5`
- Rollback command: `python3 ./executable/actions/02-arn-aws-s3-arch1-bucket-website-a1-696505809372--f791c98c/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `d7a6479a-8ab3-4077-8b6a-19c378ae20d1`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-dev-serverless-src-696505809372-eu-north-1|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket security-autopilot-dev-serverless-src-696505809372-eu-north-1 --policy file://pre-remediation-policy.json`

## S3 bucket enforces SSL requests
- Action ID: `e532a4a7-e830-4b75-a06b-2e0d1c52b75b`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::wi1-noncurrent-lifecycle-696505809372-20260330003655|S3.5`
- Rollback command: `python3 ./executable/actions/04-arn-aws-s3-wi1-noncurrent-lifecycle-696505809372-e532a4a7/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `ec2c5925-08d5-437c-8019-90f703484649`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r222018|S3.5`
- Rollback command: `python3 ./executable/actions/05-arn-aws-s3-security-autopilot-access-logs-696505-ec2c5925/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `d33c0b28-2a54-4623-8a5d-1f9bffc4884d`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r94854|S3.5`
- Rollback command: `python3 ./executable/actions/06-arn-aws-s3-security-autopilot-access-logs-696505-d33c0b28/rollback/s3_policy_restore.py`

## S3 bucket enforces SSL requests
- Action ID: `329b2b93-2959-430e-8a83-6d963ddce512`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329004157|S3.5`
- Rollback command: `python3 ./executable/actions/07-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-329b2b93/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `78237cc2-e47f-4f0f-80de-22b08d8725c7`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi13-14-nopolicy-696505809372-20260328201935|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket sa-wi13-14-nopolicy-696505809372-20260328201935 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `96bd1efb-91ee-4b22-9e1e-29613c8492aa`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001|S3.5`
- Rollback command: `python3 ./executable/actions/09-arn-aws-s3-security-autopilot-access-logs-696505-96bd1efb/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `2904172f-0491-4248-afca-af30be896885`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.5`
- Rollback command: `aws s3api put-bucket-policy --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.5 --policy file://pre-remediation-policy.json`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `6b99bb03-bb75-4535-b9e1-4550fbad76be`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260328224331|S3.5`
- Rollback command: `python3 ./executable/actions/11-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-6b99bb03/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `8f192c29-8cfc-4e0e-a9a4-b5a427bc80ba`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi7-seed-696505809372-20260328205857|S3.5`
- Rollback command: `python3 ./executable/actions/12-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-8f192c29/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `2cdace24-a63d-481d-81f7-f5bda82b8a80`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260328t181200z-eu-north-1|S3.5`
- Rollback command: `python3 ./executable/actions/13-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-2cdace24/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `0886946b-cf32-49cb-8f0e-5dcb07433426`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001-access-logs|S3.5`
- Rollback command: `python3 ./executable/actions/14-arn-aws-s3-security-autopilot-access-logs-696505-0886946b/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `bcd7f695-772d-418b-921b-a2f9ca3eaa47`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi5-site-696505809372-20260328t164043z|S3.5`
- Rollback command: `python3 ./executable/actions/15-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-bcd7f695/rollback/s3_policy_restore.py`

## S3 general purpose buckets should require requests to use SSL
- Action ID: `5bf35adb-e1ca-40aa-af5f-6c0f46fb6c1c`
- Control ID: `S3.5`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329002042|S3.5`
- Rollback command: `python3 ./executable/actions/16-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-5bf35adb/rollback/s3_policy_restore.py`
