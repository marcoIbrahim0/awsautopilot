from __future__ import annotations

import uuid
from types import SimpleNamespace

from backend.models.action import Action
from backend.models.action_group import ActionGroup
from backend.models.action_group_membership import ActionGroupMembership
from backend.models.enums import ActionGroupStatusBucket
from backend.services import action_groups as service


class _Store:
    def __init__(self) -> None:
        self.groups: dict[str, ActionGroup] = {}
        self.memberships: dict[uuid.UUID, ActionGroupMembership] = {}
        self.states: set[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = set()
        self.inserted_tables: list[str] = []


class _FakeSession:
    def __init__(self, store: _Store) -> None:
        self.store = store

    def execute(self, stmt):
        self.store.inserted_tables.append(stmt.table.name)
        rows = list(stmt._multi_values[0])
        if stmt.table.name == ActionGroup.__table__.name:
            for row in rows:
                key = row["group_key"]
                if key in self.store.groups:
                    continue
                self.store.groups[key] = ActionGroup(
                    id=uuid.uuid4(),
                    tenant_id=row["tenant_id"],
                    action_type=row["action_type"],
                    account_id=row["account_id"],
                    region=row["region"],
                    group_key=key,
                    metadata_json=row["metadata"],
                )
        elif stmt.table.name == ActionGroupMembership.__table__.name:
            for row in rows:
                action_id = row["action_id"]
                if action_id in self.store.memberships:
                    continue
                self.store.memberships[action_id] = ActionGroupMembership(
                    id=row["id"],
                    tenant_id=row["tenant_id"],
                    group_id=row["group_id"],
                    action_id=action_id,
                    source=row["source"],
                )
        else:
            for row in rows:
                self.store.states.add((row["tenant_id"], row["group_id"], row["action_id"]))
        return SimpleNamespace()


def _wire_store(monkeypatch, store: _Store) -> None:
    def _groups_by_key(session, group_keys):
        return {key: store.groups[key] for key in group_keys if key in store.groups}

    def _memberships_by_action_id(session, action_ids):
        return {
            action_id: store.memberships[action_id]
            for action_id in action_ids
            if action_id in store.memberships
        }

    def _existing_state_keys(session, action_ids):
        expected = set(action_ids)
        return {row for row in store.states if row[2] in expected}

    monkeypatch.setattr(service, "_groups_by_key", _groups_by_key)
    monkeypatch.setattr(service, "_memberships_by_action_id", _memberships_by_action_id)
    monkeypatch.setattr(service, "_existing_state_keys", _existing_state_keys)


def _action(*, tenant_id: uuid.UUID, account_id: str, region: str | None, action_type: str) -> Action:
    return Action(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        action_type=action_type,
        target_id=f"{account_id}|{region}|{action_type}",
        account_id=account_id,
        region=region,
        priority=50,
        score=50,
        score_components={},
        status="open",
        title=f"{action_type} title",
        description="desc",
    )


def test_ensure_membership_for_actions_reuses_membership_and_repairs_missing_state(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    action = _action(
        tenant_id=tenant_id,
        account_id="696505809372",
        region="eu-north-1",
        action_type="aws_config_enabled",
    )
    store = _Store()
    group_key = service.build_group_key(tenant_id, action.action_type, action.account_id, action.region)
    group = ActionGroup(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        action_type=action.action_type,
        account_id=action.account_id,
        region=action.region,
        group_key=group_key,
        metadata_json={"source": "auto_assign"},
    )
    membership = ActionGroupMembership(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        group_id=group.id,
        action_id=action.id,
        source="ingest",
    )
    store.groups[group_key] = group
    store.memberships[action.id] = membership
    _wire_store(monkeypatch, store)

    result = service.ensure_membership_for_actions(_FakeSession(store), [action], source="recompute")

    assert result == [membership]
    assert store.memberships[action.id] is membership
    assert store.states == {(tenant_id, group.id, action.id)}
    assert store.inserted_tables == ["action_group_action_state"]


def test_ensure_membership_for_actions_is_idempotent_across_repeated_calls(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    actions = [
        _action(
            tenant_id=tenant_id,
            account_id="696505809372",
            region="eu-north-1",
            action_type="aws_config_enabled",
        ),
        _action(
            tenant_id=tenant_id,
            account_id="696505809372",
            region="us-east-1",
            action_type="cloudtrail_enabled",
        ),
    ]
    store = _Store()
    _wire_store(monkeypatch, store)
    session = _FakeSession(store)

    first = service.ensure_membership_for_actions(session, actions + [actions[0]], source="recompute")
    first_insert_tables = list(store.inserted_tables)
    second = service.ensure_membership_for_actions(session, actions, source="recompute")

    assert len(first) == 2
    assert len(second) == 2
    assert {membership.action_id for membership in first} == {action.id for action in actions}
    assert {membership.action_id for membership in second} == {action.id for action in actions}
    assert set(store.memberships) == {action.id for action in actions}
    assert len(store.groups) == 2
    assert len(store.states) == 2
    assert first_insert_tables == [
        "action_groups",
        "action_group_memberships",
        "action_group_action_state",
    ]
    assert store.inserted_tables == first_insert_tables


def test_ensure_membership_for_actions_preserves_existing_state_rows(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    action = _action(
        tenant_id=tenant_id,
        account_id="696505809372",
        region=None,
        action_type="s3_block_public_access",
    )
    store = _Store()
    group_key = service.build_group_key(tenant_id, action.action_type, action.account_id, action.region)
    group = ActionGroup(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        action_type=action.action_type,
        account_id=action.account_id,
        region=action.region,
        group_key=group_key,
        metadata_json={"source": "auto_assign"},
    )
    membership = ActionGroupMembership(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        group_id=group.id,
        action_id=action.id,
        source="backfill",
    )
    store.groups[group_key] = group
    store.memberships[action.id] = membership
    store.states.add((tenant_id, group.id, action.id))
    _wire_store(monkeypatch, store)

    result = service.ensure_membership_for_actions(_FakeSession(store), [action], source="backfill")

    assert result == [membership]
    assert store.inserted_tables == []
    assert store.states == {(tenant_id, group.id, action.id)}
    assert ActionGroupStatusBucket.not_run_yet.value == "not_run_yet"
