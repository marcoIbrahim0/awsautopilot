#!/usr/bin/env python3
"""Rebuild materialized shared attack paths for one tenant scope."""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from backend.database import AsyncSessionLocal
from backend.services.attack_path_materialized import materialize_attack_paths


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild materialized attack-path read model")
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID")
    parser.add_argument("--account-id", default=None, help="Optional AWS account scope")
    parser.add_argument("--region", default=None, help="Optional AWS region scope")
    return parser.parse_args()


async def _run(tenant_id: uuid.UUID, *, account_id: str | None, region: str | None) -> dict:
    async with AsyncSessionLocal() as session:
        result = await materialize_attack_paths(session, tenant_id=tenant_id, account_id=account_id, region=region)
        await session.commit()
        return result


def main() -> int:
    args = _parse_args()
    tenant_id = uuid.UUID(args.tenant_id)
    result = asyncio.run(_run(tenant_id, account_id=args.account_id, region=args.region))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
