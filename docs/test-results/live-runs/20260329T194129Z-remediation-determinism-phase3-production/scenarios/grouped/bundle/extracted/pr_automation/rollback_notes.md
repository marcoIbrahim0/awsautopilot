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
- Action ID: `04996269-922e-453e-9aa9-aac21366e24b`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-cloudtrail-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `33ed3776-00f0-4d99-b3ad-316f97c08a1a`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket config-bucket-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `54b0d584-d60a-409d-86e3-5458bd8054b1`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-s311-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `6cb0769e-5bd2-48cf-a4c8-0ea00684f44d`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s311-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `747e6a9e-ead9-4e60-810f-fdf6b3f7ef2d`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-accesslogs-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `8ada62c8-36e1-4f90-afbb-3ab89b18096e`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s311-manual-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `8edeb7f6-556e-412c-9f59-905c8a83f452`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260323162333-eu-north-1|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket ocypheris-live-ct-20260323162333-eu-north-1`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `971002ff-f70b-4f64-bc1f-8ae9c1f9f600`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s315-manual-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `d108dd29-a89d-45d3-b2d5-9689d9699d5e`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s315-exec-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `d3419cb8-984b-4c95-817d-83dd3b394b98`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-config-696505809372-eu-north-1|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-config-696505809372-eu-north-1`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `da9d8713-383d-415e-b2fa-7b0b5039ff94`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-config-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-config-696505809372`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `deb71e7d-1fc9-4108-a466-859fe51c52ef`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260328224331|S3.11`
- Rollback command: `python3 ./executable/actions/15-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-deb71e7d/rollback/s3_lifecycle_restore.py`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `176c29ed-fcec-4934-a1ab-344bb4b6f444`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi7-seed-696505809372-20260328205857|S3.11`
- Rollback command: `python3 ./executable/actions/16-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-176c29ed/rollback/s3_lifecycle_restore.py`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `a9e5a989-3dba-4114-aeaf-2ddac120ac0c`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260328t181200z-eu-north-1|S3.11`
- Rollback command: `python3 ./executable/actions/17-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-a9e5a989/rollback/s3_lifecycle_restore.py`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `37e0f71d-4805-46d0-9f9f-bf4342d7e63c`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001-access-logs|S3.11`
- Rollback command: `python3 ./executable/actions/18-arn-aws-s3-security-autopilot-access-logs-696505-37e0f71d/rollback/s3_lifecycle_restore.py`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `abaa9de7-ac08-4b7c-8660-93695e992c1a`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi5-site-696505809372-20260328t164043z|S3.11`
- Rollback command: `python3 ./executable/actions/19-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-abaa9de7/rollback/s3_lifecycle_restore.py`

## S3 general purpose buckets should have Lifecycle configurations
- Action ID: `ba09febf-3385-40ec-a11b-707cd082b798`
- Control ID: `S3.11`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.11`
- Rollback command: `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-envready-s315-exec-696505809372`
