# AWS cleanup summary

- Run folder: `20260318T024357Z-rem-profile-wave6-live-closure`
- Date (UTC): `2026-03-18T02:57:25Z`
- Cleanup scope: `retained EC2.53 fixture security groups, temporary SaaS-account queues, and the disposable local runtime`

## AWS target-account cleanup status

| Test / Family | Target resources | Cleanup result | Evidence |
|---|---|---|---|
| `W6-LIVE-01` / `EC2.53` | executable fixture security group `sg-06f6252fa8a95b61d` and manual fixture security group `sg-0ef32ca8805a55a8b` | `terraform destroy` removed only the restricted rules and left `sg-06f6252fa8a95b61d` with no ingress; manual `authorize-security-group-ingress` restored the original public `22/3389` rules with the captured descriptions; `sg-0ef32ca8805a55a8b` stayed unchanged throughout | [`../evidence/aws/w6-live-01-ec253-pre-security-groups.json`](../evidence/aws/w6-live-01-ec253-pre-security-groups.json), [`../evidence/aws/w6-live-01-ec253-post-rollback-security-groups.json`](../evidence/aws/w6-live-01-ec253-post-rollback-security-groups.json), [`../evidence/aws/w6-live-01-ec253-post-manual-restore-security-groups.json`](../evidence/aws/w6-live-01-ec253-post-manual-restore-security-groups.json), [`../evidence/aws/w6-live-01-ec253-manual-restore.log`](../evidence/aws/w6-live-01-ec253-manual-restore.log) |

## Retained seeded resources

These retained Wave 6 fixtures were intentionally left in place in their pre-apply state:

- security groups `sg-06f6252fa8a95b61d`, `sg-0ef32ca8805a55a8b`

## SaaS-account cleanup

- Temporary SQS queues deleted from SaaS queue/runtime account `029037611564`:
  - `security-autopilot-rpw6-ec253-20260318t024357z-ingest`
  - `security-autopilot-rpw6-ec253-20260318t024357z-contract-quarantine`
  - `security-autopilot-rpw6-ec253-20260318t024357z-events-fastlane`
  - `security-autopilot-rpw6-ec253-20260318t024357z-inventory-reconcile`
  - `security-autopilot-rpw6-ec253-20260318t024357z-export-report`
- Verification result: every `GetQueueAttributes` probe failed after deletion and was recorded per queue.
- Evidence:
  - [`../evidence/aws/final-queue-cleanup.txt`](../evidence/aws/final-queue-cleanup.txt)
  - [`../evidence/aws/security-autopilot-rpw6-ec253-20260318t024357z-ingest-post-delete.err`](../evidence/aws/security-autopilot-rpw6-ec253-20260318t024357z-ingest-post-delete.err)
  - [`../evidence/aws/security-autopilot-rpw6-ec253-20260318t024357z-contract-quarantine-post-delete.err`](../evidence/aws/security-autopilot-rpw6-ec253-20260318t024357z-contract-quarantine-post-delete.err)
  - [`../evidence/aws/security-autopilot-rpw6-ec253-20260318t024357z-events-fastlane-post-delete.err`](../evidence/aws/security-autopilot-rpw6-ec253-20260318t024357z-events-fastlane-post-delete.err)
  - [`../evidence/aws/security-autopilot-rpw6-ec253-20260318t024357z-inventory-reconcile-post-delete.err`](../evidence/aws/security-autopilot-rpw6-ec253-20260318t024357z-inventory-reconcile-post-delete.err)
  - [`../evidence/aws/security-autopilot-rpw6-ec253-20260318t024357z-export-report-post-delete.err`](../evidence/aws/security-autopilot-rpw6-ec253-20260318t024357z-export-report-post-delete.err)

## Local runtime cleanup

- API on `127.0.0.1:18020`: `stopped`
- Worker process for this run: `stopped`
- Disposable Postgres at `/tmp/rpw6-ec253-20260318T024357Z`: `stopped`
- Remaining EC2.53 live-run processes after cleanup: `none`
- Evidence:
  - [`../evidence/runtime/postgres-stop.txt`](../evidence/runtime/postgres-stop.txt)
  - [`../evidence/runtime/final-process-cleanup.txt`](../evidence/runtime/final-process-cleanup.txt)
