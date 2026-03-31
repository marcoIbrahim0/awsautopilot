#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from backend.services.database_failover import (
        build_database_sync_command,
        configured_database_urls,
        sync_configured_databases,
    )
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from backend.services.database_failover import (
        build_database_sync_command,
        configured_database_urls,
        sync_configured_databases,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize one configured failover database into the other with pg_dump | psql."
    )
    parser.add_argument("--source", choices=("primary", "fallback"), default="fallback")
    parser.add_argument("--target", choices=("primary", "fallback"), default="primary")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-destructive-sync", action="store_true")
    return parser.parse_args()


def _database_urls(source: str, target: str) -> tuple[str, str]:
    urls = configured_database_urls()
    if source == target:
        raise SystemExit("Source and target must differ.")
    if source not in urls or target not in urls:
        raise SystemExit("Primary and fallback database URLs must both be configured.")
    return urls[source].sync_url, urls[target].sync_url


def main() -> int:
    args = parse_args()
    source_url, target_url = _database_urls(args.source, args.target)
    command = build_database_sync_command(source_url, target_url)
    if args.dry_run:
        print(command)
        return 0
    try:
        sync_configured_databases(
            source=args.source,
            target=args.target,
            allow_destructive_sync=args.allow_destructive_sync,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
