# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `f47a11cd-8055-4b52-81c3-2838e9696f80`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-evidence-b1-696505809372-eu-north-1|S3.15`
- Rollback command: `python3 ./executable/actions/01-arn-aws-s3-arch1-bucket-evidence-b1-696505809372-f47a11cd/rollback/s3_encryption_restore.py`

## S3 bucket uses SSE-KMS by default
- Action ID: `45d79702-98f7-4ddc-964c-4b8d91e0e06b`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-website-a1-696505809372-eu-north-1|S3.15`
- Rollback command: `python3 ./executable/actions/02-arn-aws-s3-arch1-bucket-website-a1-696505809372--45d79702/rollback/s3_encryption_restore.py`

## S3 bucket uses SSE-KMS by default
- Action ID: `39732b9a-956a-4deb-913d-d652cad22526`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::wi1-noncurrent-lifecycle-696505809372-20260330003655|S3.15`
- Rollback command: `python3 ./executable/actions/03-arn-aws-s3-wi1-noncurrent-lifecycle-696505809372-39732b9a/rollback/s3_encryption_restore.py`

## S3 bucket uses SSE-KMS by default
- Action ID: `8130621f-9c7c-4b7c-83cb-9397fb14c7cd`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329004157|S3.15`
- Rollback command: `python3 ./executable/actions/04-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-8130621f/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `998b9663-cc6f-4baf-a796-99ae261f482c`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-dev-serverless-src-696505809372-eu-north-1|S3.15`
- Rollback command: `python3 ./executable/actions/05-arn-aws-s3-security-autopilot-dev-serverless-src-998b9663/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `90a9507a-7a74-4e6f-a2ff-b78712719388`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi13-14-nopolicy-696505809372-20260328201935|S3.15`
- Rollback command: `python3 ./executable/actions/06-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-90a9507a/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `ba07da99-600c-4fd2-8091-3f1b7d5ecc02`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260328224331|S3.15`
- Rollback command: `python3 ./executable/actions/07-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-ba07da99/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `45d7dd83-bc32-4789-a5ce-a71cd4a215cd`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi7-seed-696505809372-20260328205857|S3.15`
- Rollback command: `python3 ./executable/actions/08-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-45d7dd83/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `15891d06-c639-4692-881d-05fdcca5d581`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260328t181200z-eu-north-1|S3.15`
- Rollback command: `python3 ./executable/actions/09-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-15891d06/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `4fe5d11f-81f1-48f6-b1eb-2fca55cee9d9`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001-access-logs|S3.15`
- Rollback command: `python3 ./executable/actions/10-arn-aws-s3-security-autopilot-access-logs-696505-4fe5d11f/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `c5c8cb79-6e08-4341-9301-4e9f2272cb0e`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi5-site-696505809372-20260328t164043z|S3.15`
- Rollback command: `python3 ./executable/actions/11-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-c5c8cb79/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `7249615a-d298-4278-9f9f-e41a04cb2811`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001|S3.15`
- Rollback command: `python3 ./executable/actions/12-arn-aws-s3-security-autopilot-access-logs-696505-7249615a/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `b74b1748-222a-44f5-bd02-93d1e3ea5d34`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r222018|S3.15`
- Rollback command: `python3 ./executable/actions/13-arn-aws-s3-security-autopilot-access-logs-696505-b74b1748/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `a7f92106-2df8-4768-aac0-358250abdb7b`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329002042|S3.15`
- Rollback command: `python3 ./executable/actions/14-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-a7f92106/rollback/s3_encryption_restore.py`

## S3 general purpose buckets should be encrypted at rest with AWS KMS keys
- Action ID: `398a13c7-d1fc-44f6-8621-ea7c4bf9da88`
- Control ID: `S3.15`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r94854|S3.15`
- Rollback command: `python3 ./executable/actions/15-arn-aws-s3-security-autopilot-access-logs-696505-398a13c7/rollback/s3_encryption_restore.py`
