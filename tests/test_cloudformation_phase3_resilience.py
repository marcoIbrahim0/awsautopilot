from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_phase3_dr_template_has_backup_restore_controls() -> None:
    text = _read("infrastructure/cloudformation/dr-backup-controls.yaml")

    required_tokens = (
        "Type: AWS::Backup::BackupVault",
        "Type: AWS::Backup::BackupPlan",
        "Type: AWS::Backup::BackupSelection",
        "RecoveryPointTags:",
        "DeleteAfterDays:",
        "MoveToColdStorageAfterDays:",
        "CopyActions:",
        "DrRestoreOperatorRole:",
        "backup:StartRestoreJob",
        "rds:RestoreDBInstanceFromDBSnapshot",
        "BackupJobsFailedAlarm:",
        "RestoreJobsFailedAlarm:",
    )

    for token in required_tokens:
        assert token in text


def test_phase3_dr_runbook_has_restore_commands_and_readiness_gate() -> None:
    text = _read("docs/disaster-recovery-runbook.md")

    required_tokens = (
        "Target RTO",
        "Target RPO",
        "aws backup list-recovery-points-by-backup-vault",
        "aws backup start-restore-job",
        "scripts/check_api_readiness.py",
        "/ready",
    )

    for token in required_tokens:
        assert token in text
