# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `4b97cf9a-f514-4033-b54e-dd679c427cd9`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi13-14-nopolicy-696505809372-20260328201935|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket sa-wi13-14-nopolicy-696505809372-20260328201935`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `8ab29997-bb6c-41fe-ba0c-26f03523f0ed`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-access-logs-696505809372-r221001`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `cbe0d2c3-c609-4aa2-a12f-6afb336cd507`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.11`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `176c29ed-fcec-4934-a1ab-344bb4b6f444`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi7-seed-696505809372-20260328205857|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket sa-wi7-seed-696505809372-20260328205857`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `a9e5a989-3dba-4114-aeaf-2ddac120ac0c`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260328t181200z-eu-north-1|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket ocypheris-live-ct-20260328t181200z-eu-north-1`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `37e0f71d-4805-46d0-9f9f-bf4342d7e63c`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001-access-logs|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-access-logs-696505809372-r221001-access-logs`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `abaa9de7-ac08-4b7c-8660-93695e992c1a`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi5-site-696505809372-20260328t164043z|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket sa-wi5-site-696505809372-20260328t164043z`
