#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path

MAX_TRACKED_FILE_BYTES = 25 * 1024 * 1024
BANNED_TRACKED_PATTERNS = (
    re.compile(r"^(?:venv|\.venv)/"),
    re.compile(r"^artifacts/"),
    re.compile(r"^backups/.*\.bundle$"),
    re.compile(r"(?:^|/)\.terraform(?:/|$)"),
    re.compile(r"^docs/test-results/.*/evidence/playwright/profile[^/]*/"),
    re.compile(r"^docs/test-results/.*/evidence/playwright/.*/(?:Cache|GPUCache|Code Cache|Service Worker)(?:/|$)"),
    re.compile(r"^docs/test-results/.*/evidence/playwright/.*/BrowserMetrics.*\.pma$"),
    re.compile(r"^docs/test-results/.*/evidence/playwright/.*/GraphiteDawnCache(?:/|$)"),
)


def git(*args: str, text: bool = True) -> str | bytes:
    return subprocess.check_output(["git", *args], text=text)


def iter_head_files() -> list[tuple[int, str]]:
    tree = git("ls-tree", "-rlz", "HEAD", text=False)
    files: list[tuple[int, str]] = []
    for record in tree.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        size = int(metadata.split()[3])
        path = raw_path.decode("utf-8", errors="surrogateescape")
        files.append((size, path))
    return files


def main() -> int:
    repo_root = Path(str(git("rev-parse", "--show-toplevel")).strip())
    tracked_errors: list[str] = []
    os_errors: list[str] = []

    frontend_entry = str(git("ls-tree", "HEAD", "frontend")).strip()
    if not frontend_entry.startswith("040000 tree "):
        tracked_errors.append("frontend must be tracked as a normal tree, not a gitlink/submodule")

    if (repo_root / "frontend" / ".git").exists():
        os_errors.append("frontend/.git exists on disk; nested frontend git metadata is not allowed")
    if not (repo_root / ".git").is_dir():
        os_errors.append("root checkout must use a normal .git directory; linked worktrees are not allowed for deploys")

    gitmodules = repo_root / ".gitmodules"
    if gitmodules.exists():
        gitmodules_text = gitmodules.read_text()
        if 'submodule "frontend"' in gitmodules_text or "path = frontend" in gitmodules_text:
            tracked_errors.append(".gitmodules still defines frontend as a submodule")

    for size, path in iter_head_files():
        if path == "frontend/.git" or path.startswith("frontend/.git/"):
            tracked_errors.append(f"frontend nested git metadata is tracked: {path}")
        if any(pattern.search(path) for pattern in BANNED_TRACKED_PATTERNS):
            tracked_errors.append(f"banned generated path is tracked: {path}")
        if size > MAX_TRACKED_FILE_BYTES:
            mib = size / (1024 * 1024)
            tracked_errors.append(
                f"tracked file exceeds {MAX_TRACKED_FILE_BYTES // (1024 * 1024)} MiB: {path} ({mib:.1f} MiB)"
            )

    issues = tracked_errors + os_errors
    if not issues:
        print("Repo hygiene checks passed.")
        return 0

    print("Repo hygiene violations detected:")
    for issue in issues:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
