from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.lib.no_ui_agent_terraform import TerraformError, run_terraform_apply


class _Completed:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_terraform_apply_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(command, cwd, env, capture_output, text, check, timeout):
        del cwd, env, capture_output, text, check, timeout
        calls.append(command)
        return _Completed(0, stdout="ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    transcript = run_terraform_apply(tmp_path, timeout_sec=30)

    assert len(transcript) == 3
    assert calls[0][:2] == ["terraform", "init"]
    assert transcript[-1]["exit_code"] == 0


def test_run_terraform_apply_failure_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(command, cwd, env, capture_output, text, check, timeout):
        del cwd, env, capture_output, text, check, timeout
        if command[1] == "plan":
            return _Completed(1, stderr="plan failed")
        return _Completed(0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(TerraformError) as exc:
        run_terraform_apply(tmp_path, timeout_sec=30)

    assert len(exc.value.transcript) == 2
    assert exc.value.transcript[-1]["stderr"] == "plan failed"
