"""
Unit tests for digest settings API (Step 11.3).

Covers: GET /api/users/me/digest-settings (auth), PATCH (admin only), tenant digest_enabled/digest_recipients.
"""
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
    user.email = "user@example.com"
    user.name = "Test User"
    user.role = UserRole.admin if role == "admin" else UserRole.member
    return user


def _mock_tenant(tenant_id: str, digest_enabled: bool = True, digest_recipients: str | None = None) -> MagicMock:
    tenant = MagicMock()
    tenant.id = uuid.UUID(tenant_id)
    tenant.name = "Test Tenant"
    tenant.digest_enabled = digest_enabled
    tenant.digest_recipients = digest_recipients
    return tenant


def test_get_digest_settings_requires_auth() -> None:
    """GET /api/users/me/digest-settings returns 401 without auth."""
    client = TestClient(app)
    r = client.get("/api/users/me/digest-settings")
    assert r.status_code == 401


def test_get_digest_settings_returns_tenant_settings() -> None:
    """GET /api/users/me/digest-settings returns digest_enabled and digest_recipients."""
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="member")
    tenant = _mock_tenant(tenant_id, digest_enabled=True, digest_recipients="a@b.com, c@d.com")

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        client = TestClient(app)
        r = client.get("/api/users/me/digest-settings")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["digest_enabled"] is True
    assert data["digest_recipients"] == "a@b.com, c@d.com"


def test_get_digest_settings_null_recipients() -> None:
    """GET returns digest_recipients null when not set."""
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id)
    tenant = _mock_tenant(tenant_id, digest_enabled=True, digest_recipients=None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        client = TestClient(app)
        r = client.get("/api/users/me/digest-settings")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    assert r.json()["digest_recipients"] is None


def test_patch_digest_settings_requires_admin() -> None:
    """PATCH /api/users/me/digest-settings returns 403 for non-admin."""
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="member")

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        client = TestClient(app)
        r = client.patch(
            "/api/users/me/digest-settings",
            json={"digest_enabled": False},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 403
    assert "admin" in (r.json().get("detail") or "").lower()


def test_patch_digest_settings_updates_tenant() -> None:
    """PATCH /api/users/me/digest-settings updates tenant digest_enabled and digest_recipients."""
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="admin")
    tenant = _mock_tenant(tenant_id, digest_enabled=True, digest_recipients=None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        client = TestClient(app)
        r = client.patch(
            "/api/users/me/digest-settings",
            json={"digest_enabled": False, "digest_recipients": "digest@acme.com"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    assert tenant.digest_enabled is False
    assert tenant.digest_recipients == "digest@acme.com"
    data = r.json()
    assert data["digest_enabled"] is False
    assert data["digest_recipients"] == "digest@acme.com"


def test_patch_digest_settings_empty_recipients_clears() -> None:
    """PATCH with digest_recipients empty string sets tenant.digest_recipients to None."""
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="admin")
    tenant = _mock_tenant(tenant_id, digest_enabled=True, digest_recipients="old@acme.com")

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        client = TestClient(app)
        r = client.patch(
            "/api/users/me/digest-settings",
            json={"digest_recipients": "   "},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    assert tenant.digest_recipients is None
