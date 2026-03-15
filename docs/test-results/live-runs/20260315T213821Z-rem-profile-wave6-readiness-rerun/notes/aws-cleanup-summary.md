# AWS cleanup summary

- Run ID: `20260315T213821Z-rem-profile-wave6-readiness-rerun`
- Date (UTC): `2026-03-15T21:38:21Z`
- Environment used: `local master against resumed isolated runtime`

## AWS accounts and regions

- SaaS queue/runtime account: `029037611564`
  - Region: `eu-north-1`
- Isolated AWS test account: `696505809372`
  - Regions: `eu-north-1`, `us-east-1`

## Resources touched

- SaaS queue/runtime account `029037611564`
  - temporary rerun queues:
    - `security-autopilot-rpw6-rerun-20260315t213821z-ingest`
    - `security-autopilot-rpw6-rerun-20260315t213821z-contract-quarantine`
    - `security-autopilot-rpw6-rerun-20260315t213821z-events-fastlane`
    - `security-autopilot-rpw6-rerun-20260315t213821z-inventory-reconcile`
    - `security-autopilot-rpw6-rerun-20260315t213821z-export-report`
  - abandoned fresh S3.2 attempt buckets created under SaaS-account credentials:
    - `security-autopilot-w6-rerun-s32-exec-696505809372`
    - `security-autopilot-w6-rerun-s32-review-696505809372`
- Isolated AWS test account `696505809372`
  - customer-run validation profile `test28-root`
  - retained target-account fixtures used by the ready families:
    - `security-autopilot-w6-envready-accesslogs-696505809372`
    - `security-autopilot-w6-envready-cloudtrail-696505809372`
    - `security-autopilot-w6-envready-config-696505809372`
    - `security-autopilot-w6-envready-s311-exec-696505809372`
    - `security-autopilot-w6-envready-s311-review-696505809372`
    - `security-autopilot-w6-envready-s315-exec-696505809372`
- Local disposable runtime resources
  - API PID `83250`
  - worker PID `83249`
  - Postgres PID `79328`
  - Postgres data directory `/tmp/rpw6-rerun-pg-20260315T213821Z`

## Rollback commands used during this blocker-closure task

- Target-account AWS rollback commands: `none`
- Reason:
  - This blocker-closure pass generated and inspected customer-run PR bundles only.
  - No PR bundle was manually applied to the isolated AWS test account.

## Cleanup commands used

- Local runtime cleanup:
  - `kill 83250`
  - `kill 83249`
  - `/opt/homebrew/bin/pg_ctl -D /tmp/rpw6-rerun-pg-20260315T213821Z -m fast stop`
- SaaS queue cleanup:
  - `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-rerun-20260315t213821z-ingest`
  - `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-rerun-20260315t213821z-contract-quarantine`
  - `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-rerun-20260315t213821z-events-fastlane`
  - `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-rerun-20260315t213821z-inventory-reconcile`
  - `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-rerun-20260315t213821z-export-report`
- SaaS-account abandoned bucket cleanup:
  - `aws s3api delete-bucket --bucket security-autopilot-w6-rerun-s32-exec-696505809372`
  - `aws s3api delete-bucket --bucket security-autopilot-w6-rerun-s32-review-696505809372`

## Cleanup evidence

- SaaS caller identity at cleanup time: [`../evidence/aws/cleanup-saas-caller-identity.json`](../evidence/aws/cleanup-saas-caller-identity.json)
- Queue delete log: [`../evidence/aws/cleanup-queue-delete.log`](../evidence/aws/cleanup-queue-delete.log)
- Queue deletion probe: [`../evidence/aws/cleanup-queue-probe.log`](../evidence/aws/cleanup-queue-probe.log)
- Abandoned S3.2 bucket delete outputs:
  - [`../evidence/aws/cleanup-s32-exec-delete.json`](../evidence/aws/cleanup-s32-exec-delete.json)
  - [`../evidence/aws/cleanup-s32-review-delete.json`](../evidence/aws/cleanup-s32-review-delete.json)
  - [`../evidence/aws/cleanup-s32-delete-probe.log`](../evidence/aws/cleanup-s32-delete-probe.log)
- API stop check: [`../evidence/runtime/api-stop.txt`](../evidence/runtime/api-stop.txt)
- Worker stop check: [`../evidence/runtime/worker-stop.txt`](../evidence/runtime/worker-stop.txt)
- Postgres stop output: [`../evidence/runtime/postgres-stop.txt`](../evidence/runtime/postgres-stop.txt)

## Final cleanup status

- Local API status: `stopped`
- Local worker status: `stopped`
- Local Postgres status: `stopped`
- Temporary rerun SQS queues: `deleted and probed as NonExistentQueue`
- Abandoned fresh S3.2 buckets in the SaaS account: `deleted`
- Target-account seeded readiness fixtures: `retained intentionally`
- Final cleanup status: `complete for disposable local resources and abandoned SaaS-account S3.2 buckets; deferred only for reusable target-account fixtures`

## Intentionally retained resources and follow-up cleanup plan

- Retained isolated-account buckets backing ready families:
  - `security-autopilot-w6-envready-accesslogs-696505809372`
  - `security-autopilot-w6-envready-cloudtrail-696505809372`
  - `security-autopilot-w6-envready-config-696505809372`
  - `security-autopilot-w6-envready-s311-exec-696505809372`
  - `security-autopilot-w6-envready-s311-review-696505809372`
  - `security-autopilot-w6-envready-s315-exec-696505809372`
- Why retained:
  - They now back the ready `S3.2`, `S3.5`, `S3.9`, `CloudTrail.1`, `Config.1`, and executable-only `S3.11` live proof paths.
- Delete sequence after the final full live gate:
  - `aws s3 rm s3://<bucket-name> --recursive --region eu-north-1 --profile test28-root`
  - `aws s3api delete-bucket --bucket <bucket-name> --region eu-north-1 --profile test28-root`
- Additional retained live state:
  - `test28-root` remains the customer-run apply/rollback profile for the isolated account
  - No target-account policy, trail, or recorder change was applied during this blocker-closure rerun, so no service-state rollback is pending yet
