"""Contract tests for auth login rate limiting (Wave 8 Test 30)."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.config import settings
from backend.database import get_db
from backend.main import app
from backend.routers import auth as auth_router


def _launch_tuple() -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str,
    str,
    str | None,
    str | None,
    str | None,
    str,
]:
    return (
        "029037611564",
        None,
        None,
        None,
        None,
        "eu-north-1",
        "SecurityAutopilotReadRole",
        "SecurityAutopilotWriteRole",
        None,
        None,
        None,
        "SecurityAutopilotControlPlaneForwarder",
    )


def _mock_user() -> SimpleNamespace:
    tenant = SimpleNamespace(
        id=uuid.uuid4(),
        name="Tenant A",
        external_id="ext-tenant-a",
    )
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@example.com",
        name="Tenant Admin",
        role="admin",
        password_hash="$2b$12$placeholder",
        tenant=tenant,
        onboarding_completed_at=None,
        is_saas_admin=False,
        token_version=0,
    )


def _mock_session_for_user(user: SimpleNamespace) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


def test_login_rate_limit_returns_429_with_retry_after(client: TestClient) -> None:
    user = _mock_user()
    session = _mock_session_for_user(user)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = mock_get_db
    auth_router._LOGIN_FAILURES.clear()
    with (
        patch.object(settings, "AUTH_LOGIN_RATE_LIMIT_ENABLED", True),
        patch.object(settings, "AUTH_LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 5),
        patch.object(settings, "AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS", 3600),
        patch("backend.routers.auth.verify_password", return_value=False),
    ):
        for _ in range(5):
            r = client.post(
                "/api/auth/login",
                json={"email": user.email, "password": "wrong-password"},
            )
            assert r.status_code == 401
        blocked = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "wrong-password"},
        )

    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After")


def test_login_success_clears_failed_attempt_window(client: TestClient) -> None:
    user = _mock_user()
    session = _mock_session_for_user(user)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = mock_get_db
    auth_router._LOGIN_FAILURES.clear()
    with (
        patch.object(settings, "AUTH_LOGIN_RATE_LIMIT_ENABLED", True),
        patch.object(settings, "AUTH_LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 2),
        patch.object(settings, "AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS", 3600),
        patch.object(settings, "FIREBASE_PROJECT_ID", ""),
        patch("backend.routers.auth.verify_password", side_effect=[False, True, False]),
        patch("backend.routers.auth.get_saas_and_launch_url", return_value=_launch_tuple()),
    ):
        first_fail = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "wrong-password"},
        )
        success = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "correct-password"},
        )
        second_fail = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "wrong-password"},
        )

    assert first_fail.status_code == 401
    assert success.status_code == 200
    assert second_fail.status_code == 401
