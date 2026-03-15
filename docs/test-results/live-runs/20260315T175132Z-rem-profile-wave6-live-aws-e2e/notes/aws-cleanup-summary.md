# AWS cleanup summary

- Run ID: `20260315T175132Z-rem-profile-wave6-live-aws-e2e`
- Date (UTC): `2026-03-15T18:21:43Z`
- Environment used: `local master against isolated runtime`

## AWS Accounts and Regions

- SaaS queue/runtime account: `029037611564`
  - Region: `eu-north-1`
- Isolated AWS test account: `696505809372`
  - Regions: `eu-north-1`, `us-east-1`

## Resources Touched

- SaaS queue/runtime account `029037611564`
  - `security-autopilot-rpw6-20260315t175132z-ingest`
  - `security-autopilot-rpw6-20260315t175132z-contract-quarantine`
  - `security-autopilot-rpw6-20260315t175132z-events-fastlane`
  - `security-autopilot-rpw6-20260315t175132z-inventory-reconcile`
  - `security-autopilot-rpw6-20260315t175132z-export-report`
- Isolated AWS test account `696505809372`
  - assumed read-only import role `arn:aws:iam::696505809372:role/CodexP2SecurityHubImportRole`
  - read live finding/action metadata in `eu-north-1` and `us-east-1`
  - inspected bucket/config/cloudtrail-related remediation records
- Local disposable runtime resources
  - backend process
  - worker process
  - Postgres data directory `/tmp/rpw6-pg-20260315T175132Z`

## Rollback Commands Used

- Target-account AWS rollback commands: `none`
- Reason: no executable bundle was manually applied, so no target-account AWS state changed during this run.

## Cleanup Commands Used

- `/opt/homebrew/bin/pg_ctl -D /tmp/rpw6-pg-20260315T175132Z -m fast stop`
- `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-20260315t175132z-contract-quarantine`
- `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-20260315t175132z-events-fastlane`
- `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-20260315t175132z-export-report`
- `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-20260315t175132z-ingest`
- `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw6-20260315t175132z-inventory-reconcile`
- `aws sqs get-queue-attributes --queue-url <queue-url> --attribute-names QueueArn`

## Cleanup Evidence

- Caller identity after cleanup command execution: [`../evidence/aws/cleanup-saas-caller-identity.json`](../evidence/aws/cleanup-saas-caller-identity.json)
- Queue list before delete: [`../evidence/aws/cleanup-queues-before.json`](../evidence/aws/cleanup-queues-before.json)
- Queue delete log: [`../evidence/aws/cleanup-queue-delete.log`](../evidence/aws/cleanup-queue-delete.log)
- Queue deletion probe: [`../evidence/aws/cleanup-queue-probe.log`](../evidence/aws/cleanup-queue-probe.log)
- Postgres stop output: [`../evidence/aws/postgres-stop.txt`](../evidence/aws/postgres-stop.txt)

## Final Cleanup Status

- Local backend status: `stopped`
- Local worker status: `stopped`
- Disposable Postgres status: `stopped`
- Temporary SQS queues: `deleted and probed as NonExistentQueue`
- Target-account AWS resource mutations: `none`
- Final cleanup status: `complete`

## Intentionally Retained Resources

- `None`
- Explicit approval for retaining resources: `not applicable`
