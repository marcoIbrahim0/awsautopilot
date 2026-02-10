from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from worker.services.inventory_assets import (
    InventorySnapshot,
    compute_state_hash,
    upsert_inventory_asset,
)


def _snapshot(state_for_hash: dict) -> InventorySnapshot:
    return InventorySnapshot(
        service="ec2",
        resource_id="sg-123",
        resource_type="AwsEc2SecurityGroup",
        key_fields={"group_id": "sg-123"},
        state_for_hash=state_for_hash,
        metadata_json={"name": "main"},
        evaluations=[],
    )


def _mock_session(existing: object | None) -> MagicMock:
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = existing
    return session


def test_compute_state_hash_is_deterministic_for_key_order() -> None:
    left_hash, left_size = compute_state_hash({"b": 2, "a": 1})
    right_hash, right_size = compute_state_hash({"a": 1, "b": 2})
    assert left_hash == right_hash
    assert left_size == right_size


def test_upsert_inventory_asset_creates_when_missing() -> None:
    tenant_id = uuid.uuid4()
    session = _mock_session(existing=None)
    snapshot = _snapshot({"ingress": [{"cidr": "0.0.0.0/0", "port": 22}]})

    created, changed = upsert_inventory_asset(
        session=session,
        tenant_id=tenant_id,
        account_id="123456789012",
        region="eu-north-1",
        sweep_mode="targeted",
        snapshot=snapshot,
    )

    assert created is True
    assert changed is True
    session.add.assert_called_once()
    inserted = session.add.call_args[0][0]
    expected_hash, _expected_size = compute_state_hash(snapshot.state_for_hash)
    assert inserted.state_hash == expected_hash
    assert inserted.last_reconcile_mode == "targeted"


def test_upsert_inventory_asset_updates_existing_and_detects_change() -> None:
    old_hash, _ = compute_state_hash({"ingress": []})
    existing = SimpleNamespace(
        state_hash=old_hash,
        resource_type="AwsEc2SecurityGroup",
        key_fields={"group_id": "sg-123"},
        metadata_json={},
        state_size_bytes=0,
        last_seen_at=None,
        last_reconcile_mode=None,
        last_changed_at=None,
    )
    session = _mock_session(existing=existing)
    snapshot = _snapshot({"ingress": [{"cidr": "0.0.0.0/0", "port": 22}]})

    created, changed = upsert_inventory_asset(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="123456789012",
        region="eu-north-1",
        sweep_mode="global",
        snapshot=snapshot,
    )

    assert created is False
    assert changed is True
    assert existing.last_reconcile_mode == "global"
    assert existing.resource_type == "AwsEc2SecurityGroup"


def test_upsert_inventory_asset_update_without_hash_change() -> None:
    state = {"ingress": [{"cidr": "10.0.0.0/16", "port": 22}]}
    state_hash, _ = compute_state_hash(state)
    existing = SimpleNamespace(
        state_hash=state_hash,
        resource_type="AwsEc2SecurityGroup",
        key_fields={"group_id": "sg-123"},
        metadata_json={},
        state_size_bytes=0,
        last_seen_at=None,
        last_reconcile_mode=None,
        last_changed_at="unchanged",
    )
    session = _mock_session(existing=existing)
    snapshot = _snapshot(state)

    created, changed = upsert_inventory_asset(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="123456789012",
        region="eu-north-1",
        sweep_mode="targeted",
        snapshot=snapshot,
    )

    assert created is False
    assert changed is False
    assert existing.last_changed_at == "unchanged"
