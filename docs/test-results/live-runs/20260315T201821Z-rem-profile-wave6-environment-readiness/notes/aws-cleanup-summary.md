# AWS cleanup summary

- Run ID: `20260315T201821Z-rem-profile-wave6-environment-readiness`
- Date (UTC): `2026-03-15T20:18:21Z`
- Environment used: `local master against isolated runtime`

## AWS accounts and regions

- SaaS queue/runtime account: `029037611564`
  - Region: `eu-north-1`
- Isolated AWS test account: `696505809372`
  - Regions: `eu-north-1`, `us-east-1`

## Resources touched

- SaaS queue/runtime account `029037611564`
  - `security-autopilot-rpw6-envready-20260315t201821z-ingest`
  - `security-autopilot-rpw6-envready-20260315t201821z-contract-quarantine`
  - `security-autopilot-rpw6-envready-20260315t201821z-events-fastlane`
  - `security-autopilot-rpw6-envready-20260315t201821z-inventory-reconcile`
  - `security-autopilot-rpw6-envready-20260315t201821z-export-report`
- Isolated AWS test account `696505809372`
  - assumed read-path role `arn:aws:iam::696505809372:role/CodexP2SecurityHubImportRole`
  - repaired local target-account profile `test28-root`
  - retained seeded buckets:
    - `security-autopilot-w6-envready-accesslogs-696505809372`
    - `security-autopilot-w6-envready-cloudtrail-696505809372`
    - `security-autopilot-w6-envready-config-696505809372`
    - `security-autopilot-w6-envready-s311-exec-696505809372`
    - `security-autopilot-w6-envready-s311-review-696505809372`
    - `security-autopilot-w6-envready-s315-exec-696505809372`
  - retained seeded security groups:
    - `sg-06f6252fa8a95b61d`
    - `sg-0ef32ca8805a55a8b`
- Local disposable runtime resources
  - backend PID `5473`
  - worker PID `5500`
  - Postgres data directory `/tmp/rpw6-envready-pg-20260315T201821Z`

## Rollback commands used during this readiness task

- Target-account AWS rollback commands: `none`
- Reason: this readiness task prepared scenarios and generated/inspected bundles only. No customer-run PR bundle was manually applied to the target account during this pass.

## Cleanup commands used

- `kill 5473`
- `kill 5500`
- `/opt/homebrew/bin/pg_ctl -D /tmp/rpw6-envready-pg-20260315T201821Z -m fast stop`
- `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-envready-20260315t201821z-contract-quarantine`
- `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-envready-20260315t201821z-events-fastlane`
- `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-envready-20260315t201821z-export-report`
- `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-envready-20260315t201821z-ingest`
- `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-envready-20260315t201821z-inventory-reconcile`
- `aws sqs get-queue-attributes --queue-url <queue-url> --attribute-names QueueArn`

## Cleanup evidence

- Caller identity after cleanup command execution: [`../evidence/aws/cleanup-saas-caller-identity.json`](../evidence/aws/cleanup-saas-caller-identity.json)
- Queue list before delete: [`../evidence/aws/cleanup-queues-before.json`](../evidence/aws/cleanup-queues-before.json)
- Queue delete log: [`../evidence/aws/cleanup-queue-delete.log`](../evidence/aws/cleanup-queue-delete.log)
- Queue deletion probe: [`../evidence/aws/cleanup-queue-probe.log`](../evidence/aws/cleanup-queue-probe.log)
- Postgres stop output: [`../evidence/runtime/postgres-stop.txt`](../evidence/runtime/postgres-stop.txt)
- Postgres status after stop: [`../evidence/runtime/postgres-status-after-stop.txt`](../evidence/runtime/postgres-status-after-stop.txt)
- API stop check: [`../evidence/runtime/api-stop.txt`](../evidence/runtime/api-stop.txt)
- Worker stop check: [`../evidence/runtime/worker-stop.txt`](../evidence/runtime/worker-stop.txt)

## Final cleanup status

- Local backend status: `stopped`
- Local worker status: `stopped`
- Disposable Postgres status: `stopped`
- Temporary SQS queues: `deleted and probed as NonExistentQueue`
- Target-account seeded AWS resources: `retained intentionally for the next Wave 6 live validation`
- Final cleanup status: `complete for disposable local resources; deferred for retained target-account readiness fixtures`

## Intentionally retained resources and follow-up cleanup plan

- Retained target-account credential path:
  - Local profile `test28-root` is now valid against `arn:aws:iam::696505809372:root`
  - The secret value is not stored in the repo or evidence package
  - After the next live run, delete or rotate the temporary root access key from **My security credentials** in the AWS console
- Retained security groups:
  - `sg-06f6252fa8a95b61d`
  - `sg-0ef32ca8805a55a8b`
  - Delete command after the next run:
    - `aws ec2 delete-security-group --group-id <group-id> --region eu-north-1 --profile test28-root`
- Retained buckets:
  - `security-autopilot-w6-envready-accesslogs-696505809372`
  - `security-autopilot-w6-envready-cloudtrail-696505809372`
  - `security-autopilot-w6-envready-config-696505809372`
  - `security-autopilot-w6-envready-s311-exec-696505809372`
  - `security-autopilot-w6-envready-s311-review-696505809372`
  - `security-autopilot-w6-envready-s315-exec-696505809372`
  - Delete sequence after the next run:
    - `aws s3 rm s3://<bucket-name> --recursive --region eu-north-1 --profile test28-root`
    - `aws s3api delete-bucket --bucket <bucket-name> --region eu-north-1 --profile test28-root`
- Retained service state expected only after executable validation:
  - Any CloudTrail trail created by the next live run should be stopped/deleted or restored to the prior bucket before bucket cleanup
  - Any AWS Config recorder/delivery-channel changes from the next live run should be reverted before bucket cleanup
