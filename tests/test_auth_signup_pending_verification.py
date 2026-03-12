from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.routers import auth as auth_router


def _result(scalar_one_or_none: object | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_one_or_none
    return result


def test_signup_returns_pending_response_when_firebase_enabled(client: TestClient) -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(None))
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def fake_build_link(user: User) -> str:
        user.firebase_uid = "fb-user-123"
        user.email_verification_sync_token_hash = "sync-hash"
        user.email_verification_sync_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        return "https://verify.example.com/link"

    app.dependency_overrides[get_db] = override_get_db

    with (
        patch.object(auth_router.settings, "FIREBASE_PROJECT_ID", "firebase-project"),
        patch("backend.routers.auth._build_firebase_verification_link", side_effect=fake_build_link),
        patch("backend.routers.auth.email_service.send_verification_link_email", return_value=True) as mocked_send,
    ):
        response = client.post(
            "/api/auth/signup",
            json={
                "company_name": "Acme Security",
                "email": "admin@acme.com",
                "name": "Acme Admin",
                "password": "supersafepassword",
            },
        )

    assert response.status_code == 202
    set_cookie = response.headers.get("set-cookie")
    if set_cookie is not None:
        assert 'access_token=""' in set_cookie
        assert 'csrf_token=""' in set_cookie
    payload = response.json()
    assert payload["email"] == "admin@acme.com"
    assert "verification link" in payload["message"].lower()
    assert "access_token" not in payload

    tenant_obj = next(call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], Tenant))
    user_obj = next(call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], User))
    assert tenant_obj.control_plane_token is not None
    assert user_obj.firebase_uid == "fb-user-123"
    mocked_send.assert_called_once_with(
        to_email="admin@acme.com",
        verification_link="https://verify.example.com/link",
    )


def test_signup_rejects_when_verification_delivery_is_unavailable(client: TestClient) -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(None))
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db

    with (
        patch.object(auth_router.settings, "FIREBASE_PROJECT_ID", "firebase-project"),
        patch.object(auth_router.settings, "ENV", "prod"),
        patch.object(auth_router.email_service, "smtp_host", None),
        patch.object(auth_router.email_service, "from_address", ""),
        patch("backend.routers.auth._build_firebase_verification_link") as mocked_build,
    ):
        response = client.post(
            "/api/auth/signup",
            json={
                "company_name": "Acme Security",
                "email": "admin@acme.com",
                "name": "Acme Admin",
                "password": "supersafepassword",
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == auth_router.VERIFICATION_EMAIL_DELIVERY_UNAVAILABLE
    mocked_build.assert_not_called()
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


def test_signup_fails_closed_when_verification_email_send_fails(client: TestClient) -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(None))
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def fake_build_link(user: User) -> str:
        user.firebase_uid = "fb-user-123"
        user.email_verification_sync_token_hash = "sync-hash"
        user.email_verification_sync_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        return "https://verify.example.com/link"

    app.dependency_overrides[get_db] = override_get_db

    with (
        patch.object(auth_router.settings, "FIREBASE_PROJECT_ID", "firebase-project"),
        patch.object(auth_router.settings, "ENV", "prod"),
        patch.object(auth_router.email_service, "smtp_host", "smtp.example.com"),
        patch.object(auth_router.email_service, "from_address", "verify@ocypheris.com"),
        patch("backend.routers.auth._build_firebase_verification_link", side_effect=fake_build_link),
        patch("backend.routers.auth.email_service.send_verification_link_email", return_value=False),
    ):
        response = client.post(
            "/api/auth/signup",
            json={
                "company_name": "Acme Security",
                "email": "admin@acme.com",
                "name": "Acme Admin",
                "password": "supersafepassword",
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == auth_router.VERIFICATION_EMAIL_DELIVERY_UNAVAILABLE
    session.commit.assert_awaited_once()


def test_signup_keeps_local_log_only_behavior_without_smtp(client: TestClient) -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(None))
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def fake_build_link(user: User) -> str:
        user.firebase_uid = "fb-user-123"
        user.email_verification_sync_token_hash = "sync-hash"
        user.email_verification_sync_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        return "https://verify.example.com/link"

    app.dependency_overrides[get_db] = override_get_db

    with (
        patch.object(auth_router.settings, "FIREBASE_PROJECT_ID", "firebase-project"),
        patch.object(auth_router.settings, "ENV", "local"),
        patch.object(auth_router.email_service, "smtp_host", None),
        patch.object(auth_router.email_service, "from_address", ""),
        patch("backend.routers.auth._build_firebase_verification_link", side_effect=fake_build_link),
    ):
        response = client.post(
            "/api/auth/signup",
            json={
                "company_name": "Acme Security",
                "email": "admin@acme.com",
                "name": "Acme Admin",
                "password": "supersafepassword",
            },
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["email"] == "admin@acme.com"
    assert "verification link" in payload["message"].lower()
    session.commit.assert_awaited_once()
