# AWS Cleanup Summary

- AWS account id: `696505809372`
- Regions: `eu-north-1`, `us-east-1`
- Environment used: `local master against isolated local runtime`

## Resources Touched

- Read-only target-account access:
  - `arn:aws:iam::696505809372:role/SecurityAutopilotReadRole`
  - Security Hub findings in `eu-north-1` and `us-east-1`
  - grouped action families for `EC2.182`, `S3.5`, and `S3.9`
- Isolated SaaS-side disposable resources:
  - `https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw5-20260315t001855z-ingest`
  - `https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw5-20260315t001855z-contract-quarantine`

## Rollback Commands Used

- Target AWS account `696505809372`
  - `none`
  - No apply path ran, so no target-account rollback command was executed.
- Isolated SaaS/runtime cleanup
  - `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw5-20260315t001855z-ingest --region eu-north-1`
  - `aws sqs delete-queue --queue-url https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-rpw5-20260315t001855z-contract-quarantine --region eu-north-1`
  - `pg_ctl -D /tmp/rpw5-pg-20260315T001855Z -m fast stop`
  - local backend and worker were terminated after evidence capture

## Final Cleanup Status

- Target-account mutation status: `no mutations were applied`
- Target-account cleanup status: `complete; no rollback required`
- Isolated queue cleanup status: `complete; both temporary queues deleted at 2026-03-15T00:44:15Z`
- Local runtime cleanup status: `complete; backend, worker, and disposable Postgres cluster stopped`

## Intentionally Retained Resources

- `none`
- Approval for retaining resources: `not applicable`
