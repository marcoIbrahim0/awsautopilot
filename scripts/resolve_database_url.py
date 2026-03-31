#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from backend.services.database_failover import primary_sync_pending, resolve_database_urls
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from backend.services.database_failover import primary_sync_pending, resolve_database_urls


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print the active database URL chosen by failover logic.")
    parser.add_argument("--sync", action="store_true", help="Print the sync PostgreSQL URL.")
    parser.add_argument("--async-url", action="store_true", help="Print the async PostgreSQL URL.")
    parser.add_argument("--json", action="store_true", help="Print JSON with source and both URLs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resolved = resolve_database_urls(force_refresh=True)
    if args.json:
        print(
            json.dumps(
                {
                    "source": resolved.source,
                    "sync_url": resolved.sync_url,
                    "async_url": resolved.async_url,
                    "primary_sync_pending": primary_sync_pending(),
                }
            )
        )
        return 0
    if args.sync:
        print(resolved.sync_url)
        return 0
    print(resolved.async_url if args.async_url else resolved.sync_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
