# AWS cleanup summary

- Run folder: `20260315T235627Z-rem-profile-wave6-live-aws-completion-gate`
- Date (UTC): `2026-03-16T13:12:00Z`
- Cleanup scope: `disposable local runtime, temporary SaaS-account queues, and exact pre-state restoration for every AWS mutation performed during this gate`

## AWS target-account cleanup status

| Family / Test | Target resources | Cleanup result | Evidence |
|---|---|---|---|
| `S3.2` / `W6-LIVE-04` | `security-autopilot-w6-envready-s315-exec-696505809372` public-access-block state | `restored to exact pre-state` | [`../evidence/aws/w6-live-04-s32-pre-public-access-block.json`](../evidence/aws/w6-live-04-s32-pre-public-access-block.json), [`../evidence/aws/w6-live-04-s32-rollback-public-access-block.json`](../evidence/aws/w6-live-04-s32-rollback-public-access-block.json) |
| `S3.9` / `W6-LIVE-07` | `security-autopilot-w6-envready-config-696505809372` logging config | `destroy returned bucket to no logging configuration` | [`../evidence/aws/w6-live-07-s39-post-bucket-logging.json`](../evidence/aws/w6-live-07-s39-post-bucket-logging.json), [`../evidence/aws/w6-live-07-s39-rollback-bucket-logging.json`](../evidence/aws/w6-live-07-s39-rollback-bucket-logging.json) |
| `CloudTrail.1` / `W6-LIVE-09` | `security-autopilot-trail` and retained CloudTrail bucket policy | `trail removed; retained bucket policy unchanged` | [`../evidence/aws/w6-live-09-cloudtrail-post-describe-trails.json`](../evidence/aws/w6-live-09-cloudtrail-post-describe-trails.json), [`../evidence/aws/w6-live-09-cloudtrail-rollback-describe-trails.json`](../evidence/aws/w6-live-09-cloudtrail-rollback-describe-trails.json), [`../evidence/aws/w6-live-09-cloudtrail-rollback-bucket-policy.json`](../evidence/aws/w6-live-09-cloudtrail-rollback-bucket-policy.json) |
| `Config.1` / `W6-LIVE-10` | default AWS Config recorder, default delivery channel, retained config bucket policy | `bundle rollback failed; manual recovery restored pre-state` | [`../evidence/aws/w6-live-10-config-pre-recorders.json`](../evidence/aws/w6-live-10-config-pre-recorders.json), [`../evidence/aws/w6-live-10-config-rollback-recorders.json`](../evidence/aws/w6-live-10-config-rollback-recorders.json), [`../evidence/aws/w6-live-10-config-cleanup-recorders.json`](../evidence/aws/w6-live-10-config-cleanup-recorders.json), [`../evidence/aws/w6-live-10-config-cleanup-delivery-channels.json`](../evidence/aws/w6-live-10-config-cleanup-delivery-channels.json), [`../evidence/aws/w6-live-10-config-cleanup-recorder-status-final.json`](../evidence/aws/w6-live-10-config-cleanup-recorder-status-final.json) |
| `IAM.4` / `W6-LIVE-03` | root access key `<REDACTED_AWS_ACCESS_KEY_ID>` | `no mutation occurred` | [`../evidence/aws/w6-live-03-iam4-pre-list-access-keys.json`](../evidence/aws/w6-live-03-iam4-pre-list-access-keys.json), [`../evidence/aws/w6-live-03-iam4-post-list-access-keys.json`](../evidence/aws/w6-live-03-iam4-post-list-access-keys.json) |
| `S3.11` / `W6-LIVE-06` | grouped executable `S3.11` bundle buckets | `retained evidence is incomplete; apply log shows lifecycle mutations progressed past init, but this package lacks post-apply verification and rollback capture` | [`../evidence/bundles/w6-live-06-s311-group/run_all-apply.log`](../evidence/bundles/w6-live-06-s311-group/run_all-apply.log), [`../tests/w6-live-06.md`](../tests/w6-live-06.md) |

## Retained seeded resources

> ❓ Needs verification: The retained `W6-LIVE-06` package does not contain a paired post-apply or rollback lifecycle capture, so the exact cleanup state for that S3.11 attempt cannot be proven from this package alone.

These fixtures were intentionally left in place because they are shared strict-gate prerequisites, not disposable execution byproducts:

- `security-autopilot-w6-envready-accesslogs-696505809372`
- `security-autopilot-w6-envready-cloudtrail-696505809372`
- `security-autopilot-w6-envready-config-696505809372`
- `security-autopilot-w6-envready-s311-exec-696505809372`
- `security-autopilot-w6-envready-s311-review-696505809372`
- `security-autopilot-w6-envready-s315-exec-696505809372`
- `security-autopilot-w6-strict-s311-exec-696505809372`
- `security-autopilot-w6-strict-s311-manual-696505809372`
- `security-autopilot-w6-strict-s315-exec-696505809372`
- `security-autopilot-w6-strict-s315-manual-696505809372`
- security groups `sg-06f6252fa8a95b61d`, `sg-0ef32ca8805a55a8b`
- customer-managed KMS key `arn:aws:kms:eu-north-1:696505809372:key/ef0cca31-8328-41e6-ab28-64cbedc1a44c`

## SaaS-account cleanup

- Temporary SQS queues deleted from SaaS queue/runtime account `029037611564`:
  - `security-autopilot-rpw6-completion-20260315t235627z-ingest`
  - `security-autopilot-rpw6-completion-20260315t235627z-contract-quarantine`
  - `security-autopilot-rpw6-completion-20260315t235627z-events-fastlane`
  - `security-autopilot-rpw6-completion-20260315t235627z-inventory-reconcile`
  - `security-autopilot-rpw6-completion-20260315t235627z-export-report`
- Verification result: every `GetQueueAttributes` probe returned `AWS.SimpleQueueService.NonExistentQueue`
- Evidence:
  - [`../evidence/aws/final-queue-cleanup.txt`](../evidence/aws/final-queue-cleanup.txt)
  - [`../evidence/aws/security-autopilot-rpw6-completion-20260315t235627z-ingest-post-delete.err`](../evidence/aws/security-autopilot-rpw6-completion-20260315t235627z-ingest-post-delete.err)
  - [`../evidence/aws/security-autopilot-rpw6-completion-20260315t235627z-contract-quarantine-post-delete.err`](../evidence/aws/security-autopilot-rpw6-completion-20260315t235627z-contract-quarantine-post-delete.err)
  - [`../evidence/aws/security-autopilot-rpw6-completion-20260315t235627z-events-fastlane-post-delete.err`](../evidence/aws/security-autopilot-rpw6-completion-20260315t235627z-events-fastlane-post-delete.err)
  - [`../evidence/aws/security-autopilot-rpw6-completion-20260315t235627z-inventory-reconcile-post-delete.err`](../evidence/aws/security-autopilot-rpw6-completion-20260315t235627z-inventory-reconcile-post-delete.err)
  - [`../evidence/aws/security-autopilot-rpw6-completion-20260315t235627z-export-report-post-delete.err`](../evidence/aws/security-autopilot-rpw6-completion-20260315t235627z-export-report-post-delete.err)

## Local runtime cleanup

- Secondary root-key API on `127.0.0.1:18021`: `stopped`
- Disposable Postgres at `/tmp/rpw6-completion-pg-20260315T235627Z`: `stopped`
- Remaining backend/worker/uvicorn processes for this run: `none expected after cleanup`
- Evidence:
  - [`../evidence/runtime/final-process-cleanup.txt`](../evidence/runtime/final-process-cleanup.txt)
  - [`../evidence/runtime/postgres-stop.txt`](../evidence/runtime/postgres-stop.txt)
