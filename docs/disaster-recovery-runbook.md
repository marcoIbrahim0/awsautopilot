# Disaster Recovery Runbook (ARC-008)

This runbook defines the Phase 3 HA/DR operating procedure for backup, restore, and recovery evidence.

## Target RTO/RPO

| Service | Target RTO | Target RPO | Control |
| --- | --- | --- | --- |
| Primary Postgres (RDS) | 60 minutes | 15 minutes | AWS Backup daily snapshots + cross-region copy |
| SQS queues (`ingest/events/inventory/export`) | 30 minutes | 5 minutes | Queue redrive + DLQ replay runbooks |
| API service | 30 minutes | 15 minutes | readiness-gated rollout + DB restore validation |

Notes:
- RPO is constrained by backup schedule plus restore point selection.
- Queue RPO depends on retained messages in queue/DLQ and replay.

## DR IaC

- CloudFormation template:
  - `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/dr-backup-controls.yaml`
- Deployment helper:
  - `/Users/marcomaher/AWS Security Autopilot/scripts/deploy_phase3_architecture.sh`
- Readiness gate:
  - `/Users/marcomaher/AWS Security Autopilot/scripts/check_api_readiness.py`

## 1. Confirm Backup Controls

```bash
aws cloudformation describe-stacks \
  --stack-name security-autopilot-dr-backup-controls
```

```bash
aws backup list-backup-vaults
```

```bash
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name security-autopilot-dr-vault \
  --max-results 20
```

## 2. Start Restore Drill (RDS Example)

1. Select recovery point ARN from the backup vault.

```bash
aws backup start-restore-job \
  --iam-role-arn <restore-operator-role-arn> \
  --recovery-point-arn <recovery-point-arn> \
  --resource-type RDS \
  --metadata file://restore-metadata.json
```

Example `restore-metadata.json` keys for RDS instance restore:
- `dbInstanceIdentifier`
- `dbSubnetGroupName`
- `vpcSecurityGroupIds`
- `dbInstanceClass`
- `engine`

## 3. Track Restore Job

```bash
aws backup describe-restore-job \
  --restore-job-id <restore-job-id>
```

```bash
aws rds describe-db-instances \
  --db-instance-identifier <restored-instance-id>
```

## 4. Validate Service Readiness

Validate API dependency health (DB + SQS):

```bash
python3 scripts/check_api_readiness.py --url https://<api-host>/ready
```

Or direct:

```bash
curl -sS https://<api-host>/ready
```

Expected:
- HTTP `200`
- `"ready": true`
- no SQS or DB dependency errors

## 5. Recovery Evidence Capture

Record:
1. Backup recovery point ARN used.
2. Restore job ID and start/end timestamps.
3. Restore status output (`COMPLETED`).
4. Readiness gate result after restore.
5. Any rollback or cleanup actions.

Store evidence under:
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/`

Helper:

```bash
python3 scripts/collect_phase3_architecture_evidence.py \
  --dr-stack security-autopilot-dr-backup-controls \
  --readiness-url https://<api-host>/ready
```

## 6. Drill Cadence

- Minimum cadence: monthly recovery drill.
- Trigger window: first business week of each month.
- Include at least one restore validation and one `/ready` gate check.

Recommended scheduler (example):

```bash
0 14 3 * * cd /Users/marcomaher/AWS\ Security\ Autopilot && \
  python3 scripts/collect_phase3_architecture_evidence.py --dr-stack security-autopilot-dr-backup-controls
```
