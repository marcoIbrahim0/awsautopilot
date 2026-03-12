#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys

REV_TOKEN_RE = re.compile(r"^([a-zA-Z0-9_]+)")


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    print(f"$ {' '.join(cmd)}")
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return stdout


def _parse_revisions(output: str) -> list[str]:
    revisions: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        match = REV_TOKEN_RE.match(line)
        if match:
            revisions.append(match.group(1))
    return revisions


def main() -> None:
    heads_output = _run(["alembic", "heads"])
    current_output = _run(["alembic", "current"])

    heads = sorted(set(_parse_revisions(heads_output)))
    current = sorted(set(_parse_revisions(current_output)))

    if not heads:
        print("No Alembic heads found; migration setup is invalid.", file=sys.stderr)
        raise SystemExit(1)
    if not current:
        print("Database has no current Alembic revision; run 'alembic upgrade heads'.", file=sys.stderr)
        raise SystemExit(1)
    if current != heads:
        print(
            "Migration gate failed: database revision is not at Alembic head "
            f"(current={current}, heads={heads}). Run 'alembic upgrade heads'.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"Migration gate passed: current={current} heads={heads}")


if __name__ == "__main__":
    main()
