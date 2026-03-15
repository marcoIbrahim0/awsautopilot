# AWS Cleanup Summary

- Run ID: `20260315T125927Z-rem-profile-wave5-post-archive-live-aws-e2e`
- Cleanup completed (UTC): `2026-03-15T13:13:39Z`
- Branch tested: `master`

## AWS Accounts and Regions

- Target isolated AWS test account: `696505809372`
- Isolated runtime queue/account plumbing: `029037611564`
- Region(s): `eu-north-1`

## Resources Touched

- Read-only target-account verification:
  - `sts:GetCallerIdentity` under runtime/SaaS credentials
  - `sts:AssumeRole` attempt into `arn:aws:iam::696505809372:role/SecurityAutopilotReadRole` (`AccessDenied`)
- Isolated runtime AWS resources created in account `029037611564`:
  - `security-autopilot-rpw5-post-archive-20260315t125927z-ingest`
  - `security-autopilot-rpw5-post-archive-20260315t125927z-contract-quarantine`
  - `security-autopilot-rpw5-post-archive-20260315t125927z-events-fastlane`
  - `security-autopilot-rpw5-post-archive-20260315t125927z-inventory-reconcile`
  - `security-autopilot-rpw5-post-archive-20260315t125927z-export-report`
- Local isolated runtime resources:
  - Postgres cluster at `/tmp/rpw5-post-archive-pg-20260315T125927Z`
  - backend on `http://127.0.0.1:18008`
  - worker polling the isolated SQS queues

## Cleanup Actions

- Deleted all five isolated SQS queues created for this run.
- Polled queue existence until the AWS API stopped resolving the deleted queue URLs.
- Stopped the isolated backend and worker exec sessions.
- Stopped the disposable Postgres cluster with `pg_ctl -m fast stop`.
- Removed `/tmp/rpw5-post-archive-pg-20260315T125927Z`.

## Final Retained-Resource Status

- Target account `696505809372`: `no AWS resources created or mutated`
- Runtime account `029037611564`: `no isolated run queues retained`
- Local runtime: `not retained`
- Retained resources: `none`

## Evidence

- Caller identity: [../evidence/aws/saas-caller-identity.json](../evidence/aws/saas-caller-identity.json)
- Failed ReadRole assume-role probe: [../evidence/aws/read-role-assume.err](../evidence/aws/read-role-assume.err)
- Cleanup action summary: [../evidence/aws/cleanup-actions.json](../evidence/aws/cleanup-actions.json)
