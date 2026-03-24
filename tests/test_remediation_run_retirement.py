from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.models.enums import RemediationRunMode, RemediationRunStatus
from backend.services.remediation_run_retirement import (
    STALE_RUN_ARTIFACT_KEY,
    retire_stale_active_runs,
    stale_active_run_reason,
)


def _run(**overrides):
    now = datetime.now(timezone.utc)
    base = {
        "mode": RemediationRunMode.pr_only,
        "status": RemediationRunStatus.pending,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "artifacts": {},
        "outcome": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_stale_active_run_reason_detects_old_pending() -> None:
    now = datetime.now(timezone.utc)
    run = _run(created_at=now - timedelta(minutes=15), updated_at=now - timedelta(minutes=15))

    assert stale_active_run_reason(run, now=now) == "stale_pending_no_progress"


def test_stale_active_run_reason_detects_old_running() -> None:
    now = datetime.now(timezone.utc)
    run = _run(
        status=RemediationRunStatus.running,
        created_at=now - timedelta(hours=4),
        updated_at=now - timedelta(hours=4),
        started_at=now - timedelta(hours=4),
    )

    assert stale_active_run_reason(run, now=now) == "stale_running_no_progress"


def test_retire_stale_active_runs_marks_run_failed() -> None:
    now = datetime.now(timezone.utc)
    run = _run(created_at=now - timedelta(minutes=20), updated_at=now - timedelta(minutes=20))

    retired = retire_stale_active_runs([run], now=now)

    assert retired == [run]
    assert run.status == RemediationRunStatus.failed
    assert run.outcome == "stale_active_run_retired"
    assert run.completed_at == now
    assert run.artifacts[STALE_RUN_ARTIFACT_KEY]["reason"] == "stale_pending_no_progress"
