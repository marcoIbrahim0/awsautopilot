# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should have server access logging enabled
- Action ID: `60a49649-3cfc-4565-9b93-0aa58590a308`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-evidence-b1-696505809372-eu-north-1|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket arch1-bucket-evidence-b1-696505809372-eu-north-1 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `a7ad353b-2925-43cc-a5fe-a24ca377b825`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi13-14-nopolicy-696505809372-20260328201935|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket sa-wi13-14-nopolicy-696505809372-20260328201935 --bucket-logging-status '{}'`

## S3 bucket access logging enabled
- Action ID: `6cf8c5a0-d031-40e5-b254-2f4eb08a9f5d`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-website-a1-696505809372-eu-north-1|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket arch1-bucket-website-a1-696505809372-eu-north-1 --bucket-logging-status '{}'`

## S3 bucket access logging enabled
- Action ID: `adc31819-3200-4a15-a299-977a8059cc8b`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::wi1-noncurrent-lifecycle-696505809372-20260330003655|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket wi1-noncurrent-lifecycle-696505809372-20260330003655 --bucket-logging-status '{}'`

## S3 bucket access logging enabled
- Action ID: `5ab0ba1e-d6ba-4f8d-b478-fab185dc844d`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329004157|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket phase2-wi1-lifecycle-696505809372-20260329004157 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `9ce4c3bd-638b-4c57-a629-b3cce990d92e`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-dev-serverless-src-696505809372-eu-north-1|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-dev-serverless-src-696505809372-eu-north-1 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `19a9b0f0-de47-4a5b-982f-8d3c876c2064`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-access-logs-696505809372-r221001 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `51038315-855b-4113-a0d0-0db8391aeece`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r94854|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-access-logs-696505809372-r94854 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `cc3ba387-feb0-42a6-a6b6-6e18f2a1dc65`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r222018|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-access-logs-696505809372-r222018 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `0fd42f91-d019-4b8b-a9ae-cdf93b99cdeb`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.9 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `f704085e-6481-4304-af67-d7358aa6de30`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260328224331|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket phase2-wi1-lifecycle-696505809372-20260328224331 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `1f3adb89-5325-439b-8675-fece9afef0ef`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi7-seed-696505809372-20260328205857|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket sa-wi7-seed-696505809372-20260328205857 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `6efea359-8c2a-4b28-8165-ee61690b5a8e`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260328t181200z-eu-north-1|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket ocypheris-live-ct-20260328t181200z-eu-north-1 --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `bed34478-fc8a-4714-bb40-e52cfbc8bf9b`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001-access-logs|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket security-autopilot-access-logs-696505809372-r221001-access-logs --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `0197deac-4964-41c5-92a1-f1ee3c224dbb`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi5-site-696505809372-20260328t164043z|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket sa-wi5-site-696505809372-20260328t164043z --bucket-logging-status '{}'`

## S3 general purpose buckets should have server access logging enabled
- Action ID: `d32172a1-429a-42c2-a144-31076bba3150`
- Control ID: `S3.9`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329002042|S3.9`
- Rollback command: `aws s3api put-bucket-logging --bucket phase2-wi1-lifecycle-696505809372-20260329002042 --bucket-logging-status '{}'`
