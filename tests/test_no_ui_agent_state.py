from __future__ import annotations

from pathlib import Path

import pytest

from scripts.lib.no_ui_agent_state import CheckpointManager


def test_checkpoint_resume_roundtrip(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    manager = CheckpointManager.create_or_resume(checkpoint_path, resume=False)
    manager.mark_phase_complete("auth", {"tenant_id": "t-1"})
    manager.increment_retry("run_poll")

    resumed = CheckpointManager.create_or_resume(checkpoint_path, resume=True)
    assert resumed.is_phase_complete("auth")
    assert resumed.checkpoint.context["tenant_id"] == "t-1"
    assert resumed.checkpoint.retries["run_poll"] == 1


def test_resume_requires_existing_checkpoint(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        CheckpointManager.create_or_resume(missing, resume=True)


def test_finalize_sets_status_and_exit_code(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    manager = CheckpointManager.create_or_resume(checkpoint_path, resume=False)
    manager.finalize("failed", 3)

    loaded = CheckpointManager.create_or_resume(checkpoint_path, resume=True)
    assert loaded.checkpoint.status == "failed"
    assert loaded.checkpoint.exit_code == 3
