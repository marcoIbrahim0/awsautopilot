#!/usr/bin/env python3
from __future__ import annotations

import argparse

from backend.services.migration_guard import get_revision_status


def validate_revision_status(*, require_at_head: bool) -> tuple[bool, str]:
    status = get_revision_status()
    expected = set(status.expected_heads)
    current = set(status.current_heads)

    extra_current = sorted(current - expected)
    if extra_current:
        return (
            False,
            "Runtime/DB alignment failed: database revision is ahead of the runtime artifact "
            f"(current={sorted(current)}, expected={sorted(expected)}).",
        )

    if require_at_head and current != expected:
        return (
            False,
            "Runtime/DB alignment failed: database revision is not at Alembic head "
            f"(current={sorted(current)}, expected={sorted(expected)}).",
        )

    relation = "at_head" if current == expected else "db_behind_runtime"
    return (
        True,
        "Runtime/DB alignment passed: "
        f"relation={relation} current={sorted(current)} expected={sorted(expected)}",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate that the target database revision is compatible with the runtime artifact being deployed. "
            "By default the database may be behind the repo/runtime heads, but it may not be ahead."
        )
    )
    parser.add_argument(
        "--require-at-head",
        action="store_true",
        help="Require the database revision to exactly match the repo/runtime Alembic heads.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    ok, message = validate_revision_status(require_at_head=bool(args.require_at_head))
    stream = print
    stream(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
