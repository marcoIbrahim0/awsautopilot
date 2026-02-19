from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any


class TerraformError(Exception):
    def __init__(self, message: str, transcript: list[dict[str, Any]]):
        super().__init__(message)
        self.transcript = transcript


def run_terraform_apply(
    workdir: Path,
    timeout_sec: int,
    env: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    commands = [
        ["terraform", "init", "-input=false"],
        ["terraform", "plan", "-input=false", "-out=tfplan"],
        ["terraform", "apply", "-auto-approve", "tfplan"],
    ]

    transcript: list[dict[str, Any]] = []
    for command in commands:
        record = run_command(command, workdir, timeout_sec, merged_env)
        transcript.append(record)
        if int(record["exit_code"]) != 0:
            raise TerraformError(f"Terraform command failed: {' '.join(command)}", transcript)

    return transcript


def run_command(
    command: list[str],
    workdir: Path,
    timeout_sec: int,
    env: dict[str, str],
) -> dict[str, Any]:
    started = time.monotonic()
    started_at = _utc_epoch_seconds()
    completed = subprocess.run(
        command,
        cwd=str(workdir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_sec,
    )
    duration_sec = round(time.monotonic() - started, 3)

    return {
        "command": " ".join(command),
        "exit_code": int(completed.returncode),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "duration_sec": duration_sec,
        "started_at_epoch": started_at,
        "finished_at_epoch": _utc_epoch_seconds(),
    }


def _utc_epoch_seconds() -> float:
    return time.time()
