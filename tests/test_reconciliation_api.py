from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app


def _result(*, scalar_one_or_none: object | None = None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_one_or_none
    return result


def test_reconciliation_run_blocks_cross_tenant_account(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id, email="tenant-a@example.com")

    tenant = SimpleNamespace(id=tenant_id, external_id="ext-a")
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(scalar_one_or_none=tenant),  # get_tenant
            _result(scalar_one_or_none=None),  # get_account_for_tenant
        ]
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        response = client.post(
            "/api/reconciliation/run",
            json={
                "account_id": "123456789012",
                "services": ["ec2"],
                "regions": ["us-east-1"],
                "max_resources": 100,
                "sweep_mode": "global",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_reconciliation_status_blocks_cross_tenant_account_filter(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id, email="tenant-a@example.com")

    tenant = SimpleNamespace(id=tenant_id, external_id="ext-a")
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(scalar_one_or_none=tenant),  # get_tenant
            _result(scalar_one_or_none=None),  # get_account_for_tenant(account_id filter)
        ]
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.reconciliation.settings") as mock_settings:
        mock_settings.TENANT_RECONCILIATION_ENABLED = True
        mock_settings.tenant_reconciliation_pilot_tenants_list = set()
        try:
            response = client.get("/api/reconciliation/status?account_id=123456789012")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
