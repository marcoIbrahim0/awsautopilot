from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.models.enums import UserRole


def _mock_user(tenant_id: str, role: str = "member") -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = uuid.UUID(tenant_id)
    user.role = UserRole.admin if role == "admin" else UserRole.member
    return user


def _mock_tenant(tenant_id: str) -> MagicMock:
    tenant = MagicMock()
    tenant.id = uuid.UUID(tenant_id)
    tenant.governance_notifications_enabled = True
    tenant.governance_webhook_url = "https://hooks.example.com/governance"
    return tenant


def test_get_governance_settings_requires_auth() -> None:
    client = TestClient(app)
    r = client.get("/api/users/me/governance-settings")
    assert r.status_code == 401


def test_get_governance_settings_returns_flags_not_url() -> None:
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id)
    tenant = _mock_tenant(tenant_id)

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        client = TestClient(app)
        r = client.get("/api/users/me/governance-settings")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["governance_notifications_enabled"] is True
    assert data["governance_webhook_configured"] is True
    assert "governance_webhook_url" not in data


def test_patch_governance_settings_requires_admin() -> None:
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="member")

    async def _override_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        client = TestClient(app)
        r = client.patch(
            "/api/users/me/governance-settings",
            json={"governance_notifications_enabled": True},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 403


def test_patch_governance_settings_updates_tenant() -> None:
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="admin")
    tenant = _mock_tenant(tenant_id)

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        client = TestClient(app)
        r = client.patch(
            "/api/users/me/governance-settings",
            json={
                "governance_notifications_enabled": False,
                "governance_webhook_url": "https://notify.example.com/governance",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    assert tenant.governance_notifications_enabled is False
    assert tenant.governance_webhook_url == "https://notify.example.com/governance"


def test_patch_governance_settings_rejects_invalid_webhook() -> None:
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="admin")
    tenant = _mock_tenant(tenant_id)

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        client = TestClient(app)
        r = client.patch(
            "/api/users/me/governance-settings",
            json={"governance_webhook_url": "http://insecure.example.com"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    assert session.commit.await_count == 0
