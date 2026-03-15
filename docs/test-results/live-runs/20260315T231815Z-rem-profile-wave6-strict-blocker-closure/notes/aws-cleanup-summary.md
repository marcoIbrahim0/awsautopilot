# AWS cleanup summary

- Run ID: `20260315T231815Z-rem-profile-wave6-strict-blocker-closure`
- Date (UTC): `2026-03-15T23:18:15Z`
- Environment used: `local master against a fresh isolated runtime`

## AWS accounts and regions

- SaaS queue/runtime account: `029037611564`
  - Region: `eu-north-1`
- Isolated AWS test account: `696505809372`
  - Region: `eu-north-1`

## Resources touched

- SaaS queue/runtime account `029037611564`
  - temporary strict queues:
    - `security-autopilot-rpw6-strict-20260315t231815z-ingest`
    - `security-autopilot-rpw6-strict-20260315t231815z-contract-quarantine`
    - `security-autopilot-rpw6-strict-20260315t231815z-events-fastlane`
    - `security-autopilot-rpw6-strict-20260315t231815z-inventory-reconcile`
    - `security-autopilot-rpw6-strict-20260315t231815z-export-report`
- Isolated AWS test account `696505809372`
  - customer-run validation profile `test28-root`
  - retained strict fixture buckets:
    - `security-autopilot-w6-strict-s311-exec-696505809372`
    - `security-autopilot-w6-strict-s311-manual-696505809372`
    - `security-autopilot-w6-strict-s315-exec-696505809372`
    - `security-autopilot-w6-strict-s315-manual-696505809372`
  - retained customer-managed KMS key for the `S3.15` downgrade path:
    - `arn:aws:kms:eu-north-1:696505809372:key/ef0cca31-8328-41e6-ab28-64cbedc1a44c`
    - alias `alias/security-autopilot-w6-strict-s315-manual`
  - retained Security Hub standards state:
    - NIST 800-53 remains enabled in `eu-north-1` because the strict findings depend on that control set
- Local disposable runtime resources
  - API PID `50232`
  - worker PID `71121`
  - Postgres PID `36485`
  - Postgres data directory `/tmp/rpw6-strict-pg-20260315T231815Z`

## Rollback commands used during this blocker-closure task

- Target-account AWS rollback commands: `none`
- Reason:
  - This strict blocker-closure pass generated and inspected customer-run PR bundles or guidance bundles only.
  - No PR bundle was manually applied to the isolated AWS test account.

## Cleanup commands used

- Local runtime cleanup:
  - `kill 50232`
  - `kill 71121`
  - `/opt/homebrew/bin/pg_ctl -D /tmp/rpw6-strict-pg-20260315T231815Z -m fast stop`
- SaaS queue cleanup:
  - `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-strict-20260315t231815z-ingest`
  - `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-strict-20260315t231815z-contract-quarantine`
  - `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-strict-20260315t231815z-events-fastlane`
  - `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-strict-20260315t231815z-inventory-reconcile`
  - `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-strict-20260315t231815z-export-report`

## Cleanup evidence

- SaaS caller identity at cleanup time: [`../evidence/aws/cleanup-saas-caller-identity.json`](../evidence/aws/cleanup-saas-caller-identity.json)
- Queue delete log: [`../evidence/aws/cleanup-queue-delete.log`](../evidence/aws/cleanup-queue-delete.log)
- Queue deletion probe: [`../evidence/aws/cleanup-queue-probe.log`](../evidence/aws/cleanup-queue-probe.log)
- API stop check: [`../evidence/runtime/api-stop.txt`](../evidence/runtime/api-stop.txt)
- Worker stop check: [`../evidence/runtime/worker-stop.txt`](../evidence/runtime/worker-stop.txt)
- Postgres stop output: [`../evidence/runtime/postgres-stop.txt`](../evidence/runtime/postgres-stop.txt)

## Final cleanup status

- Local API status: `stopped`
- Local worker status: `stopped`
- Local Postgres status: `stopped`
- Temporary strict SQS queues: `deleted and probed as NonExistentQueue`
- Target-account strict fixture buckets: `retained intentionally`
- Target-account strict custom KMS key: `retained intentionally`
- Target-account Security Hub standards state: `retained intentionally`
- Final cleanup status: `complete for disposable local resources and temporary SaaS queues; deferred only for reusable isolated-account proof fixtures`

## Intentionally retained resources and follow-up cleanup plan

- Retained isolated-account buckets backing the strict proof paths:
  - `security-autopilot-w6-strict-s311-exec-696505809372`
  - `security-autopilot-w6-strict-s311-manual-696505809372`
  - `security-autopilot-w6-strict-s315-exec-696505809372`
  - `security-autopilot-w6-strict-s315-manual-696505809372`
- Retained isolated-account KMS state backing the strict `S3.15` downgrade path:
  - `arn:aws:kms:eu-north-1:696505809372:key/ef0cca31-8328-41e6-ab28-64cbedc1a44c`
  - alias `alias/security-autopilot-w6-strict-s315-manual`
- Why retained:
  - These resources back the fresh `S3.11` and `S3.15` live proof claims in this package.
  - NIST 800-53 enablement is part of the same live proof surface and was not rolled back in this closure task.
- Delete sequence after the final full live gate:
  - `aws s3 rm s3://<bucket-name> --recursive --region eu-north-1 --profile test28-root`
  - `aws s3api delete-bucket --bucket <bucket-name> --region eu-north-1 --profile test28-root`
  - `aws kms schedule-key-deletion --key-id <kms-key-arn> --pending-window-in-days 7 --region eu-north-1 --profile test28-root`
- Additional retained live state:
  - `test28-root` remains the customer-run apply/rollback profile for the isolated account
  - No target-account PR bundle was manually applied in this task, so no service-state rollback is pending
