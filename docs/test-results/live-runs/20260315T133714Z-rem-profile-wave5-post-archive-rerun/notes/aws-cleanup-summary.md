# AWS Cleanup Summary

- Run ID: `20260315T133714Z-rem-profile-wave5-post-archive-rerun`
- Cleanup completed (UTC): `2026-03-15T13:45:21Z`
- Branch tested: `master`
- Commit / HEAD: `7eee3cbb57ee99fa9866d811aa5f1bdf5f428a73`

## AWS Accounts and Regions

- Target isolated AWS test account: `696505809372`
- Isolated runtime queue/account plumbing: `029037611564`
- Region(s): `eu-north-1`

## Resources Touched

- Read-only target-account verification:
  - `sts:GetCallerIdentity` under runtime/SaaS credentials
  - `sts:AssumeRole` attempt into `arn:aws:iam::696505809372:role/SecurityAutopilotReadRole` (`AccessDenied`)
- Isolated runtime AWS resources created in account `029037611564`:
  - `security-autopilot-rpw5-post-archive-rerun-20260315t133714z-ingest`
  - `security-autopilot-rpw5-post-archive-rerun-20260315t133714z-contract-quarantine`
  - `security-autopilot-rpw5-post-archive-rerun-20260315t133714z-events-fastlane`
  - `security-autopilot-rpw5-post-archive-rerun-20260315t133714z-inventory-reconcile`
  - `security-autopilot-rpw5-post-archive-rerun-20260315t133714z-export-report`
- Local isolated runtime resources:
  - Postgres cluster at `/tmp/rpw5-post-archive-rerun-pg-20260315T133714Z`
  - backend on `http://127.0.0.1:18010`
  - worker polling the isolated SQS queues

## Cleanup Actions

- Deleted all five isolated SQS queues created for this rerun.
- Stopped the isolated backend and worker exec sessions.
- Stopped the disposable Postgres cluster with `pg_ctl stop`.
- Removed `/tmp/rpw5-post-archive-rerun-pg-20260315T133714Z`.

## Final Retained-Resource Status

- Target account `696505809372`: `no AWS resources created or mutated`
- Runtime account `029037611564`: `no isolated run queues retained`
- Local runtime: `not retained`
- Retained resources: `none`

## Evidence

- Caller identity: [../evidence/aws/saas-caller-identity.json](../evidence/aws/saas-caller-identity.json)
- Failed ReadRole assume-role probe: [../evidence/aws/read-role-assume.err](../evidence/aws/read-role-assume.err)
- Cleanup action summary: [../evidence/aws/cleanup-actions.json](../evidence/aws/cleanup-actions.json)
