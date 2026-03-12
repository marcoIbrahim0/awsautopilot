#!/usr/bin/env python3
"""Backfill persisted relationship_context for existing Security Hub findings."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.models.finding import Finding
from backend.services.action_engine import compute_actions_for_tenant
from backend.services.finding_relationship_context import enrich_finding_raw_json
from backend.workers.database import session_scope


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill finding relationship context")
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID")
    parser.add_argument("--account-id", default=None, help="Optional AWS account ID scope")
    parser.add_argument("--region", default=None, help="Optional AWS region scope")
    parser.add_argument("--dry-run", action="store_true", help="Compute changes without persisting them")
    parser.add_argument(
        "--recompute-actions",
        action="store_true",
        help="Recompute actions for the same tenant/account/region scope after backfill",
    )
    return parser.parse_args()


def _scoped_findings(session, *, tenant_id: uuid.UUID, account_id: str | None, region: str | None):
    query = session.query(Finding).filter(Finding.tenant_id == tenant_id, Finding.source == "security_hub")
    if account_id is not None:
        query = query.filter(Finding.account_id == account_id)
    if region is not None:
        query = query.filter(Finding.region == region)
    return query.order_by(Finding.id.asc())


def _enriched_raw_json(finding: Finding) -> dict:
    return enrich_finding_raw_json(
        finding.raw_json,
        account_id=finding.account_id,
        region=finding.region,
        resource_id=finding.resource_id,
        resource_type=finding.resource_type,
        resource_key=finding.resource_key,
    )


def _is_complete(payload: dict) -> bool:
    context = payload.get("relationship_context")
    return isinstance(context, dict) and bool(context.get("complete"))


def main() -> int:
    args = _parse_args()
    tenant_id = uuid.UUID(args.tenant_id)
    summary = {"scanned": 0, "updated": 0, "complete": 0, "recomputed_actions": False}
    with session_scope() as session:
        for finding in _scoped_findings(session, tenant_id=tenant_id, account_id=args.account_id, region=args.region):
            summary["scanned"] += 1
            expected = _enriched_raw_json(finding)
            summary["complete"] += int(_is_complete(expected))
            if finding.raw_json == expected:
                continue
            summary["updated"] += 1
            if not args.dry_run:
                finding.raw_json = expected
        if args.recompute_actions and not args.dry_run:
            compute_actions_for_tenant(session, tenant_id=tenant_id, account_id=args.account_id, region=args.region)
            summary["recomputed_actions"] = True
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
