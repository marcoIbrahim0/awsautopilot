#!/usr/bin/env python3
"""Recompute actions for one tenant/account scope.

Safe for repeated runs: action computation is idempotent and reconciles links.
"""
from __future__ import annotations

import argparse
import json
import uuid

from backend.services.action_engine import compute_actions_for_tenant
from backend.workers.database import session_scope


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recompute actions for a tenant/account scope")
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID")
    parser.add_argument("--account-id", required=True, help="AWS account ID (12 digits)")
    parser.add_argument("--region", default=None, help="Optional AWS region scope")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    tenant_id = uuid.UUID(args.tenant_id)
    with session_scope() as session:
        result = compute_actions_for_tenant(
            session,
            tenant_id=tenant_id,
            account_id=args.account_id,
            region=args.region,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
