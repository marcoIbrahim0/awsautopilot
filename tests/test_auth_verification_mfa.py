from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_current_user, hash_password
from backend.database import get_db
from backend.main import app


def _result(scalar_one_or_none: object | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_one_or_none
    return result


def test_update_me_persists_phone_and_resets_phone_verified(client: TestClient) -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="user@example.com",
        name="User",
        role="member",
        onboarding_completed_at=None,
        phone_number="+15551230000",
        phone_verified=True,
        email_verified=True,
        mfa_enabled=True,
        mfa_method="phone",
        phone_verification_code_hash="abc",
        phone_verification_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def override_current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    response = client.patch(
        "/api/users/me",
        json={"phone_number": "+15559876543"},
    )

    assert response.status_code == 200
    payload = response.json()["user"]
    assert payload["phone_number"] == "+15559876543"
    assert payload["phone_verified"] is False
    assert payload["mfa_enabled"] is False
    assert payload["mfa_method"] is None
    assert user.phone_verification_code_hash is None
    assert user.phone_verification_expires_at is None


def test_send_and_confirm_email_verification_code(client: TestClient) -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="verify@example.com",
        phone_number=None,
        email_verified=False,
        phone_verified=False,
        email_verification_code_hash=None,
        email_verification_expires_at=None,
    )

    session = MagicMock()
    session.commit = AsyncMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def override_current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    with patch("backend.routers.auth.email_service.send_security_code_email", return_value=True) as mocked_send:
        send_response = client.post(
            "/api/auth/verify/send",
            json={"verification_type": "email"},
        )

    assert send_response.status_code == 200
    send_payload = send_response.json()
    assert "code" in send_payload["message"].lower()
    if send_payload.get("debug_code") is not None:
        assert bool(re.fullmatch(r"\d{6}", send_payload["debug_code"]))
    mocked_send.assert_called_once()
    sent_code = mocked_send.call_args.kwargs["code"]
    assert user.email_verification_code_hash == hashlib.sha256(sent_code.encode("utf-8")).hexdigest()
    assert user.email_verification_expires_at is not None

    confirm_response = client.post(
        "/api/auth/verify/confirm",
        json={"verification_type": "email", "code": sent_code},
    )

    assert confirm_response.status_code == 204
    assert user.email_verified is True
    assert user.email_verification_code_hash is None
    assert user.email_verification_expires_at is None


def test_send_email_verification_returns_503_when_email_not_delivered(client: TestClient) -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="verify-fail@example.com",
        phone_number=None,
        email_verified=False,
        phone_verified=False,
        email_verification_code_hash=None,
        email_verification_expires_at=None,
    )

    session = MagicMock()
    session.commit = AsyncMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def override_current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    with patch("backend.routers.auth.email_service.send_security_code_email", return_value=False):
        response = client.post(
            "/api/auth/verify/send",
            json={"verification_type": "email"},
        )

    assert response.status_code == 503
    assert "unable to deliver verification code" in response.json()["detail"].lower()


def test_enable_mfa_requires_verified_channel(client: TestClient) -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="mfa@example.com",
        email_verified=False,
        phone_verified=False,
        phone_number=None,
        mfa_enabled=False,
        mfa_method=None,
        mfa_challenge_code_hash=None,
        mfa_challenge_token_hash=None,
        mfa_challenge_expires_at=None,
    )

    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def override_current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    response = client.patch(
        "/api/auth/mfa/settings",
        json={"mfa_enabled": True, "mfa_method": "email"},
    )

    assert response.status_code == 400
    assert "verify your email" in response.json()["detail"].lower()


def test_login_with_mfa_challenge_and_completion(client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    tenant = SimpleNamespace(
        id=uuid.uuid4(),
        name="Tenant",
        external_id="ext-123",
        control_plane_token_fingerprint=None,
        control_plane_token_created_at=None,
        control_plane_token_revoked_at=None,
        control_plane_token=None,
    )
    user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        tenant=tenant,
        email="admin@example.com",
        name="Admin",
        role="admin",
        password_hash=hash_password("Password123!"),
        onboarding_completed_at=None,
        token_version=0,
        phone_number=None,
        phone_verified=False,
        email_verified=True,
        mfa_enabled=True,
        mfa_method="email",
        mfa_challenge_code_hash=None,
        mfa_challenge_token_hash=None,
        mfa_challenge_expires_at=None,
    )

    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(user))
    session.commit = AsyncMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db

    captured_code: dict[str, str] = {}

    def _capture_code(*, to_email: str, code: str, purpose: str) -> bool:
        captured_code["value"] = code
        return True

    with patch("backend.routers.auth.email_service.send_security_code_email", side_effect=_capture_code):
        challenge_response = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "Password123!"},
        )

    assert challenge_response.status_code == 200
    challenge_payload = challenge_response.json()
    assert challenge_payload["mfa_required"] is True
    assert challenge_payload["mfa_method"] == "email"
    assert "mfa_ticket" in challenge_payload
    assert "value" in captured_code

    mfa_response = client.post(
        "/api/auth/login/mfa",
        json={
            "mfa_ticket": challenge_payload["mfa_ticket"],
            "code": captured_code["value"],
        },
    )

    assert mfa_response.status_code == 200
    payload = mfa_response.json()
    assert isinstance(payload.get("access_token"), str)
    assert payload["user"]["mfa_enabled"] is True
    assert user.mfa_challenge_code_hash is None
    assert user.mfa_challenge_token_hash is None
    assert user.mfa_challenge_expires_at is None
