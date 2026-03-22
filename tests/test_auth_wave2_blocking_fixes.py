from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.auth import (
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    hash_password_reset_token,
    verify_password,
)
from backend.database import get_db
from backend.main import app
from backend.routers import auth as auth_router


def _result(scalar_one_or_none: object | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_one_or_none
    return result


def _set_cookie_headers(response) -> list[str]:
    return response.headers.get_list("set-cookie")


def test_refresh_endpoint_success_contract(client: TestClient) -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        token_version=2,
    )

    async def override_current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    response = client.post("/api/auth/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str)
    set_cookie = (response.headers.get("set-cookie") or "").lower()
    assert "access_token=" in set_cookie
    assert "csrf_token=" in set_cookie


def test_refresh_preserves_session_cookie_mode(client: TestClient) -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        token_version=2,
    )
    token = create_access_token(
        user.id,
        user.tenant_id,
        token_version=user.token_version,
        persistent_session=False,
    )

    async def override_current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    client.cookies.set("access_token", token)
    response = client.post("/api/auth/refresh")

    assert response.status_code == 200
    cookie_headers = "\n".join(_set_cookie_headers(response)).lower()
    assert "access_token=" in cookie_headers
    assert "max-age" not in cookie_headers
    assert "expires" not in cookie_headers


def test_logout_invalidates_old_bearer_token(client: TestClient) -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        token_version=0,
    )
    old_token = create_access_token(user.id, user.tenant_id, token_version=0)

    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(user))
    session.commit = AsyncMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    logout_response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {old_token}"},
    )

    assert logout_response.status_code == 204
    assert user.token_version == 1
    assert session.commit.await_count == 1

    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert me_response.status_code == 401
    assert me_response.json()["detail"] == "Invalid or expired token"


def test_password_change_success_and_wrong_old_password(client: TestClient) -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        token_version=0,
        password_hash=hash_password("OldPassword123!"),
        password_reset_token_hash="existing-reset-hash",
        password_reset_expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        password_reset_requested_at=datetime.now(timezone.utc),
    )

    session = MagicMock()
    session.commit = AsyncMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def override_current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    wrong_response = client.put(
        "/api/auth/password",
        json={
            "old_password": "WrongPassword!",
            "new_password": "NewPassword123!",
        },
    )
    assert wrong_response.status_code == 400
    assert wrong_response.json()["detail"] == "Old password is incorrect"
    assert session.commit.await_count == 0

    success_response = client.put(
        "/api/auth/password",
        json={
            "old_password": "OldPassword123!",
            "new_password": "NewPassword123!",
        },
    )
    assert success_response.status_code == 204
    assert verify_password("NewPassword123!", user.password_hash)
    assert user.token_version == 1
    assert user.password_reset_token_hash is None
    assert user.password_reset_expires_at is None
    assert user.password_reset_requested_at is None
    assert session.commit.await_count == 1
    set_cookie = (success_response.headers.get("set-cookie") or "").lower()
    assert "access_token=" in set_cookie


def test_login_remember_me_false_sets_session_cookies(client: TestClient) -> None:
    tenant = SimpleNamespace(
        id=uuid.uuid4(),
        name="Tenant A",
        external_id="ext-tenant-a",
    )
    user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@example.com",
        name="Tenant Admin",
        role="admin",
        password_hash=hash_password("OldPassword123!"),
        tenant=tenant,
        onboarding_completed_at=None,
        is_saas_admin=False,
        token_version=0,
    )

    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(user))

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with (
        patch.object(auth_router.settings, "FIREBASE_PROJECT_ID", ""),
        patch("backend.routers.auth.get_saas_and_launch_url", return_value=("029037611564", None, None, None, None, "eu-north-1", "SecurityAutopilotReadRole", "SecurityAutopilotWriteRole", None, None, None, "SecurityAutopilotControlPlaneForwarder")),
    ):
        response = client.post(
            "/api/auth/login",
            json={
                "email": user.email,
                "password": "OldPassword123!",
                "remember_me": False,
            },
        )

    assert response.status_code == 200
    cookie_headers = "\n".join(_set_cookie_headers(response)).lower()
    assert "access_token=" in cookie_headers
    assert "csrf_token=" in cookie_headers
    assert "max-age" not in cookie_headers
    assert "expires" not in cookie_headers


def test_login_refreshes_token_version_before_issuing_cookie(client: TestClient) -> None:
    tenant = SimpleNamespace(
        id=uuid.uuid4(),
        name="Tenant A",
        external_id="ext-tenant-a",
    )
    user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@example.com",
        name="Tenant Admin",
        role="admin",
        password_hash=hash_password("OldPassword123!"),
        tenant=tenant,
        onboarding_completed_at=None,
        is_saas_admin=False,
        token_version=0,
    )

    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(user))

    async def refresh_user(target_user, attribute_names=None) -> None:
        assert target_user is user
        assert attribute_names == ["token_version"]
        user.token_version = 1

    session.refresh = AsyncMock(side_effect=refresh_user)

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with (
        patch.object(auth_router.settings, "FIREBASE_PROJECT_ID", ""),
        patch("backend.routers.auth.get_saas_and_launch_url", return_value=("029037611564", None, None, None, None, "eu-north-1", "SecurityAutopilotReadRole", "SecurityAutopilotWriteRole", None, None, None, "SecurityAutopilotControlPlaneForwarder")),
    ):
        response = client.post(
            "/api/auth/login",
            json={
                "email": user.email,
                "password": "OldPassword123!",
                "remember_me": True,
            },
        )

    assert response.status_code == 200
    assert session.refresh.await_count == 1
    token = response.json()["access_token"]
    token_data = decode_access_token(token)
    assert token_data is not None
    assert token_data.token_version == 1


def test_forgot_password_generic_response_for_existing_and_non_existing_user(client: TestClient) -> None:
    existing_user = SimpleNamespace(
        id=uuid.uuid4(),
        email="existing@example.com",
        password_reset_token_hash=None,
        password_reset_expires_at=None,
        password_reset_requested_at=None,
    )

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[_result(existing_user), _result(None)])
    session.commit = AsyncMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with patch(
        "backend.routers.auth.email_service.send_password_reset_email",
        return_value=True,
    ) as mock_send_reset:
        existing_response = client.post(
            "/api/auth/forgot-password",
            json={"email": "existing@example.com"},
        )
        missing_response = client.post(
            "/api/auth/forgot-password",
            json={"email": "missing@example.com"},
        )

    assert existing_response.status_code == 200
    assert missing_response.status_code == 200
    assert existing_response.json() == missing_response.json()
    assert existing_response.json()["message"] == "If an account exists, a reset link was sent."
    assert existing_user.password_reset_token_hash is not None
    assert len(existing_user.password_reset_token_hash) == 64
    assert existing_user.password_reset_expires_at is not None
    assert existing_user.password_reset_requested_at is not None
    assert session.commit.await_count == 1
    mock_send_reset.assert_called_once()


def test_reset_password_success(client: TestClient) -> None:
    token = "valid-reset-token"
    user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        token_version=0,
        password_hash=hash_password("OldPassword123!"),
        password_reset_token_hash=hash_password_reset_token(token),
        password_reset_expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        password_reset_requested_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(user))
    session.commit = AsyncMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    response = client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "new_password": "BrandNewPassword123!",
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Password reset successful."
    assert verify_password("BrandNewPassword123!", user.password_hash)
    assert user.password_reset_token_hash is None
    assert user.password_reset_expires_at is None
    assert user.password_reset_requested_at is None
    assert user.token_version == 1
    assert session.commit.await_count == 1


@pytest.mark.parametrize("expired", [False, True])
def test_reset_password_invalid_or_expired_token_returns_400(client: TestClient, expired: bool) -> None:
    token = "token-under-test"
    user = None
    if expired:
        user = SimpleNamespace(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            token_version=0,
            password_hash=hash_password("OldPassword123!"),
            password_reset_token_hash=hash_password_reset_token(token),
            password_reset_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            password_reset_requested_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )

    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(user))
    session.commit = AsyncMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    response = client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "new_password": "BrandNewPassword123!",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired token"
    assert session.commit.await_count == 0
