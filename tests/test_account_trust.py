from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.models.tenant import Tenant
from backend.services.account_trust import (
    account_assume_role_external_id,
    count_external_id_mismatches,
    sync_account_external_id_mirror,
)


def test_account_assume_role_external_id_prefers_explicit_tenant_value() -> None:
    account = SimpleNamespace(
        external_id="account-external-id",
        tenant=SimpleNamespace(external_id="tenant-external-id"),
    )

    value = account_assume_role_external_id(
        account,
        tenant_external_id="explicit-tenant-external-id",
    )

    assert value == "explicit-tenant-external-id"


def test_account_assume_role_external_id_falls_back_to_loaded_tenant() -> None:
    account = SimpleNamespace(
        external_id="account-external-id",
        tenant=SimpleNamespace(external_id="tenant-external-id"),
    )

    value = account_assume_role_external_id(account)

    assert value == "tenant-external-id"


def test_account_assume_role_external_id_uses_account_mirror_as_last_resort() -> None:
    account = SimpleNamespace(external_id="account-external-id", tenant=None)

    value = account_assume_role_external_id(account)

    assert value == "account-external-id"


def test_count_external_id_mismatches_returns_scalar_count() -> None:
    session = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = 3
    session.execute.return_value = result

    count = count_external_id_mismatches(session)

    assert count == 3
    session.execute.assert_called_once()


def test_sync_account_external_id_mirror_returns_updated_rowcount() -> None:
    session = MagicMock()
    result = MagicMock()
    result.rowcount = 5
    session.execute.return_value = result

    updated = sync_account_external_id_mirror(session)

    assert updated == 5
    session.execute.assert_called_once()


def test_tenant_external_id_is_immutable_after_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = Tenant(name="Acme", external_id="ext-initial")
    monkeypatch.setattr("backend.models.tenant.inspect", lambda instance: SimpleNamespace(persistent=True))

    with pytest.raises(ValueError, match="immutable"):
        tenant.external_id = "ext-rotated"
