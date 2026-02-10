from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.inventory_asset import InventoryAsset


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _json_dumps_sorted(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def compute_state_hash(value: Any) -> tuple[str, int]:
    payload = _json_dumps_sorted(value)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest, len(payload.encode("utf-8"))


@dataclass
class InventorySnapshot:
    service: str
    resource_id: str
    resource_type: str
    key_fields: dict[str, Any]
    state_for_hash: dict[str, Any]
    metadata_json: dict[str, Any] | None
    evaluations: list[Any]


def upsert_inventory_asset(
    session: Session,
    tenant_id: uuid.UUID,
    account_id: str,
    region: str,
    sweep_mode: str,
    snapshot: InventorySnapshot,
) -> tuple[bool, bool]:
    """
    Upsert one inventory asset snapshot.

    Returns:
        (created, changed_hash)
    """
    state_hash, state_size = compute_state_hash(snapshot.state_for_hash)
    now = _now_utc()
    existing = (
        session.query(InventoryAsset)
        .filter(
            InventoryAsset.tenant_id == tenant_id,
            InventoryAsset.account_id == account_id,
            InventoryAsset.region == region,
            InventoryAsset.service == snapshot.service,
            InventoryAsset.resource_id == snapshot.resource_id,
        )
        .first()
    )
    if existing:
        changed_hash = existing.state_hash != state_hash
        existing.resource_type = snapshot.resource_type
        existing.key_fields = snapshot.key_fields
        existing.metadata_json = snapshot.metadata_json
        existing.state_hash = state_hash
        existing.state_size_bytes = state_size
        existing.last_seen_at = now
        existing.last_reconcile_mode = sweep_mode
        if changed_hash:
            existing.last_changed_at = now
        return False, changed_hash

    row = InventoryAsset(
        tenant_id=tenant_id,
        account_id=account_id,
        region=region,
        service=snapshot.service,
        resource_id=snapshot.resource_id,
        resource_type=snapshot.resource_type,
        key_fields=snapshot.key_fields,
        state_hash=state_hash,
        state_size_bytes=state_size,
        metadata_json=snapshot.metadata_json,
        first_seen_at=now,
        last_seen_at=now,
        last_changed_at=now,
        last_reconcile_mode=sweep_mode,
    )
    session.add(row)
    return True, True
