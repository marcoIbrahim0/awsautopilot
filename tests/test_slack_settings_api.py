"""
Unit tests for Slack settings API (Step 11.4).

Covers: GET returns slack_webhook_configured (no URL), slack_digest_enabled;
PATCH admin only; PATCH updates tenant; auth required.
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


def _mock_tenant(
    tenant_id: str,
    slack_webhook_url: str | None = None,
    slack_digest_enabled: bool = False,
) -> MagicMock:
    tenant = MagicMock()
    tenant.id = uuid.UUID(tenant_id)
    tenant.name = "Test Tenant"
    tenant.slack_webhook_url = slack_webhook_url
    tenant.slack_digest_enabled = slack_digest_enabled
    return tenant


def test_get_slack_settings_requires_auth() -> None:
    """GET /api/users/me/slack-settings returns 401 without auth."""
    client = TestClient(app)
    r = client.get("/api/users/me/slack-settings")
    assert r.status_code == 401


def test_get_slack_settings_returns_configured_and_enabled_not_url() -> None:
    """GET returns slack_webhook_configured and slack_digest_enabled; never the URL."""
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id)
    tenant = _mock_tenant(
        tenant_id,
        slack_webhook_url="https://hooks.slack.com/services/secret",
        slack_digest_enabled=True,
    )

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
        r = client.get("/api/users/me/slack-settings")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["slack_webhook_configured"] is True
    assert data["slack_digest_enabled"] is True
    assert "slack_webhook_url" not in data
    assert "secret" not in str(data)


def test_get_slack_settings_not_configured() -> None:
    """GET returns slack_webhook_configured false when URL is null."""
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id)
    tenant = _mock_tenant(tenant_id, slack_webhook_url=None, slack_digest_enabled=False)

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
        r = client.get("/api/users/me/slack-settings")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    assert r.json()["slack_webhook_configured"] is False


def test_patch_slack_settings_requires_admin() -> None:
    """PATCH /api/users/me/slack-settings returns 403 for non-admin."""
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="member")

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        client = TestClient(app)
        r = client.patch(
            "/api/users/me/slack-settings",
            json={"slack_digest_enabled": True},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 403
    assert "admin" in (r.json().get("detail") or "").lower()


def test_patch_slack_settings_updates_tenant() -> None:
    """PATCH updates tenant slack_webhook_url and slack_digest_enabled."""
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="admin")
    tenant = _mock_tenant(tenant_id, slack_webhook_url=None, slack_digest_enabled=False)

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
            "/api/users/me/slack-settings",
            json={
                "slack_webhook_url": "https://hooks.slack.com/services/T/B/X",
                "slack_digest_enabled": True,
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    assert tenant.slack_webhook_url == "https://hooks.slack.com/services/T/B/X"
    assert tenant.slack_digest_enabled is True
    data = r.json()
    assert data["slack_webhook_configured"] is True
    assert data["slack_digest_enabled"] is True
    assert "slack_webhook_url" not in data


def test_patch_slack_settings_clear_webhook() -> None:
    """PATCH with empty slack_webhook_url clears it."""
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="admin")
    tenant = _mock_tenant(
        tenant_id,
        slack_webhook_url="https://hooks.slack.com/old",
        slack_digest_enabled=True,
    )

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
            "/api/users/me/slack-settings",
            json={"slack_webhook_url": "   "},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    assert tenant.slack_webhook_url is None
    assert r.json()["slack_webhook_configured"] is False
