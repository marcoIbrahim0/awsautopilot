# ARC-008 Restore Drill Evidence (Phase 3)

## Scope

This artifact records the ARC-008 operational restore drill executed in `eu-north-1` for the DR stack:
- `security-autopilot-dr-backup-controls`

## Drill Window (UTC)

- Start: `2026-02-17T18:17:08Z`
- End: `2026-02-17T18:24:00Z`

## Backup Job Evidence

- Backup job ID: `c14b4709-a5c5-46e1-8a61-ca3dc1b43d68`
- Backup state: `COMPLETED`
- Backup completion: `2026-02-17T20:19:54.678000+02:00`
- Recovery point ARN: `arn:aws:ec2:eu-north-1::snapshot/snap-092557d4323022fb2`
- Backup vault: `security-autopilot-dr-vault`
- Retention (`DeleteAfterDays`): `35`

Source:
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-backup-job-final-20260217T181033Z.json`

## Restore Job Evidence

- Restore job ID: `8056c07c-016f-4758-b977-765e796af0f2`
- Restore status: `COMPLETED`
- Restore completion: `2026-02-17T20:23:51.441000+02:00`
- Created resource ARN: `arn:aws:ec2:eu-north-1:029037611564:volume/vol-0e04835133326dbc1`
- Restore IAM role ARN: `arn:aws:iam::029037611564:role/SecurityAutopilotDrRestoreOperatorRole`

Source:
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-job-final-20260217T181033Z.json`

## Cleanup Actions

- Deleted restored drill volume: `vol-0e04835133326dbc1`
- Deleted source drill volume: `vol-0f6f38ab7b05762de`

## Raw Command Transcript

Full command-by-command output (including timestamps and intermediate retries):
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-arc008-restore-drill-20260217T181033Z.txt`
