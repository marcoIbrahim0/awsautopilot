# Phase 3 Architecture Closure Checklist

This checklist tracks closure for `ARC-008` and `ARC-009` in `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/02-architecture-plan.md`.

## Scope

- `ARC-008`: HA/DR controls, backup retention, restore permissions, and recovery runbook evidence.
- `ARC-009`: dependency-aware readiness endpoint and operational SLO signals.

## Gate Status

- Phase 3 architecture scope status: `Complete` (objective evidence and architecture owner acknowledgement are attached).
- Single traceable closure index: `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-phase4-closure-index-20260217T195458Z.md`.

## Automated Test Evidence

Run from repo root:

```bash
pytest -q \
  tests/test_health_readiness.py \
  tests/test_saas_system_health_phase3.py \
  tests/test_cloudformation_phase3_resilience.py \
  --noconftest
```

CI gate:
- `/Users/marcomaher/AWS Security Autopilot/.github/workflows/architecture-phase3.yml`

## Deployment Evidence

Primary deployment region for this repo: `eu-north-1`.

The helper deploy script enforces this by default and will refuse other regions unless you explicitly set:
- `SECURITY_AUTOPILOT_ALLOW_CROSS_REGION_DEPLOY=true`

1. Deploy DR controls stack:
- `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/dr-backup-controls.yaml`

2. Run deployment helper (includes readiness gate by default):
- `/Users/marcomaher/AWS Security Autopilot/scripts/deploy_phase3_architecture.sh`

3. Capture architecture + readiness evidence snapshot:
- `/Users/marcomaher/AWS Security Autopilot/scripts/collect_phase3_architecture_evidence.py`

## Required Operational Proof

- [x] `ARC-008`: successful restore drill with start/end timestamps and restore job output.
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-drill-20260217T181033Z.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-drill-20260217T181033Z.txt`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-job-final-20260217T181033Z.json`
- [x] `ARC-008`: backup retention and (if configured) cross-region copy verified in stack outputs.
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-stack-outputs-20260217T181033Z.json`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-architecture-20260217T182441Z.md`
  - Verification: `BackupDeleteAfterDays=35`, `CopyDeleteAfterDays=35`, `SecondaryBackupVaultArn=""` (cross-region copy not configured).
- [x] `ARC-009`: `/ready` returns non-200 under dependency failure simulation.
- [x] `ARC-009`: `/ready` returns 200 after dependency recovery.
- [x] `ARC-009`: queue lag + worker failure SLO metrics visible in admin system health.

`ARC-009` proof artifacts (2026-02-17 UTC):
- Closure summary:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-closure-20260217T181525Z.md`
- Failure simulation (`/ready` -> HTTP 503):
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-readiness-failure-20260217T181415Z.txt`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-readiness-failure-20260217T181415Z.json`
- Recovery simulation (`/ready` -> HTTP 200):
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-readiness-recovery-20260217T181415Z.txt`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-readiness-recovery-20260217T181415Z.json`
- Queue lag + worker failure SLO visibility:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-system-health-slo-20260217T181442Z.txt`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-system-health-slo-20260217T181442Z.json`
- Validation command output:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-pytest-20260217T181247Z.txt`
- Command log:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-command-log-20260217T181525Z.md`

`ARC-008` proof artifacts (2026-02-17 UTC):
- Deployment output:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-deploy-20260217T181033Z.txt`
- Stack output capture:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-stack-outputs-20260217T181033Z.json`
- Restore drill summary and transcript:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-drill-20260217T181033Z.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-drill-20260217T181033Z.txt`
- Backup/restore final job outputs:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-backup-job-final-20260217T181033Z.json`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-job-final-20260217T181033Z.json`
- Architecture evidence collector output:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-evidence-collect-20260217T181033Z.txt`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-architecture-20260217T182441Z.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-architecture-20260217T182441Z.json`

## Runbooks

- DR restore procedure:
  - `/Users/marcomaher/AWS Security Autopilot/docs/disaster-recovery-runbook.md`
- EventBridge target DLQ replay:
  - `/Users/marcomaher/AWS Security Autopilot/docs/eventbridge-target-dlq-replay-runbook.md`

## Sign-off

Sign-off package status:
- [x] test artifacts attached
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-pytest-20260217T181247Z.txt`
- [x] stack update output attached
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-deploy-20260217T181033Z.txt`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-stack-outputs-20260217T181033Z.json`
- [x] restore exercise output attached
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-drill-20260217T181033Z.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-drill-20260217T181033Z.txt`
- [x] on-call owner acknowledgement attached
  - Decision artifact:
    - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-architecture-owner-acknowledgement-20260217T234632Z.md`
  - Owner: `arn:aws:iam::029037611564:user/AutoPilotAdmin`
  - Decision: `Acknowledge`
  - Decision timestamp (UTC): `2026-02-17T23:46:32Z`

## Final Closure Index

- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-phase4-closure-index-20260217T195458Z.md`

## ARC-008 Command Log (Exact Commands Executed)

```bash
./scripts/deploy_phase3_architecture.sh --region eu-north-1 --skip-readiness-gate
aws cloudformation describe-stacks --region eu-north-1 --stack-name security-autopilot-dr-backup-controls --query 'Stacks[0].{StackStatus:StackStatus,CreationTime:CreationTime,LastUpdatedTime:LastUpdatedTime,Outputs:Outputs,Parameters:Parameters}' --output json
aws ec2 create-volume --region eu-north-1 --availability-zone eu-north-1a --size 1 --volume-type gp3 --tag-specifications 'ResourceType=volume,Tags=[{Key=Name,Value=arc008-restore-drill-source-20260217T181033Z},{Key=Application,Value=SecurityAutopilot},{Key=Control,Value=ARC-008}]' --output json
aws ec2 wait volume-available --region eu-north-1 --volume-ids vol-0f6f38ab7b05762de
aws backup start-backup-job --region eu-north-1 --backup-vault-name security-autopilot-dr-vault --resource-arn arn:aws:ec2:eu-north-1:029037611564:volume/vol-0f6f38ab7b05762de --iam-role-arn arn:aws:iam::029037611564:role/SecurityAutopilotDrBackupServiceRole --idempotency-token arc008-backup-20260217T181033Z --start-window-minutes 60 --complete-window-minutes 120 --lifecycle DeleteAfterDays=35 --recovery-point-tags Application=SecurityAutopilot,Control=ARC-008,Drill=Restore --output json
aws backup describe-backup-job --region eu-north-1 --backup-job-id c14b4709-a5c5-46e1-8a61-ca3dc1b43d68 --output json
aws backup get-recovery-point-restore-metadata --region eu-north-1 --backup-vault-name security-autopilot-dr-vault --recovery-point-arn arn:aws:ec2:eu-north-1::snapshot/snap-092557d4323022fb2 --output json
aws backup start-restore-job --region eu-north-1 --recovery-point-arn arn:aws:ec2:eu-north-1::snapshot/snap-092557d4323022fb2 --iam-role-arn arn:aws:iam::029037611564:role/SecurityAutopilotDrRestoreOperatorRole --resource-type EBS --metadata file://docs/audit-remediation/evidence/phase3-arc008-restore-metadata-20260217T181033Z.json --idempotency-token arc008-restore-20260217T181033Z-r2 --output json
aws backup describe-restore-job --region eu-north-1 --restore-job-id 8056c07c-016f-4758-b977-765e796af0f2 --output json
aws ec2 delete-volume --region eu-north-1 --volume-id vol-0e04835133326dbc1
aws ec2 delete-volume --region eu-north-1 --volume-id vol-0f6f38ab7b05762de
python3 scripts/collect_phase3_architecture_evidence.py --region eu-north-1 --dr-stack security-autopilot-dr-backup-controls --out-dir docs/audit-remediation/evidence
```

## Evidence Index

- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-deploy-20260217T181033Z.txt`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-stack-outputs-20260217T181033Z.json`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-metadata-20260217T181033Z.json`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-backup-job-final-20260217T181033Z.json`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-job-final-20260217T181033Z.json`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-drill-20260217T181033Z.md`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-drill-20260217T181033Z.txt`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-evidence-collect-20260217T181033Z.txt`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-architecture-20260217T182441Z.md`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-architecture-20260217T182441Z.json`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-closure-20260217T181525Z.md`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-command-log-20260217T181525Z.md`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-pytest-20260217T181247Z.txt`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-readiness-failure-20260217T181415Z.txt`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-readiness-failure-20260217T181415Z.json`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-readiness-recovery-20260217T181415Z.txt`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-readiness-recovery-20260217T181415Z.json`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-system-health-slo-20260217T181442Z.txt`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc009-system-health-slo-20260217T181442Z.json`
