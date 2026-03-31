from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import hash_control_plane_token, hash_password
from backend.database import get_db
from backend.main import app
from backend.models.audit_log import AuditLog
from backend.models.tenant import Tenant
from backend.routers import auth as auth_router
from backend.routers.auth import get_current_user


def _result(scalar_one_or_none: object | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_one_or_none
    result.scalar_one.return_value = scalar_one_or_none
    return result


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


def _valid_event() -> dict:
    return {
        "id": "evt-1",
        "time": "2026-02-10T10:00:00Z",
        "account": "123456789012",
        "region": "us-east-1",
        "source": "aws.ec2",
        "detail-type": "AWS API Call via CloudTrail",
        "detail": {
            "eventName": "AuthorizeSecurityGroupIngress",
            "eventCategory": "Management",
            "requestParameters": {"groupId": "sg-123"},
        },
    }


def test_signup_hashes_control_plane_token_and_reveals_once(client: TestClient) -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(None))
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with (
        patch.object(auth_router.settings, "FIREBASE_PROJECT_ID", ""),
        patch("backend.routers.auth.get_saas_and_launch_url", return_value=_launch_tuple()),
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

    assert response.status_code == 201
    payload = response.json()
    revealed_token = payload["control_plane_token"]
    assert revealed_token.startswith("cptok-")
    assert payload["control_plane_token_active"] is True

    tenant_obj = next(call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], Tenant))
    assert tenant_obj.control_plane_token == hash_control_plane_token(revealed_token)
    assert tenant_obj.control_plane_token != revealed_token
    assert payload["control_plane_token_fingerprint"] == tenant_obj.control_plane_token_fingerprint


def test_login_never_returns_existing_control_plane_token(client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    tenant = SimpleNamespace(
        id=uuid.uuid4(),
        name="Acme Security",
        external_id="ext-test-123",
        control_plane_token="deadbeef" * 8,
        control_plane_token_fingerprint="cptok-ab...1234",
        control_plane_token_created_at=now,
        control_plane_token_revoked_at=None,
    )
    user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@acme.com",
        name="Acme Admin",
        role="admin",
        onboarding_completed_at=None,
        password_hash=hash_password("supersafepassword"),
        tenant=tenant,
    )

    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(user))

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with (
        patch.object(auth_router.settings, "FIREBASE_PROJECT_ID", ""),
        patch("backend.routers.auth.get_saas_and_launch_url", return_value=_launch_tuple()),
    ):
        response = client.post(
            "/api/auth/login",
            json={"email": "admin@acme.com", "password": "supersafepassword"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["control_plane_token"] is None
    assert payload["control_plane_token_fingerprint"] == tenant.control_plane_token_fingerprint
    assert payload["control_plane_token_active"] is True


def test_me_never_returns_existing_control_plane_token(client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    tenant = SimpleNamespace(
        id=uuid.uuid4(),
        name="Acme Security",
        external_id="ext-test-123",
        control_plane_token="deadbeef" * 8,
        control_plane_token_fingerprint="cptok-ab...1234",
        control_plane_token_created_at=now,
        control_plane_token_revoked_at=None,
    )
    current_user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@acme.com",
        name="Acme Admin",
        role="admin",
        onboarding_completed_at=None,
        tenant=tenant,
    )

    async def override_current_user():
        return current_user

    app.dependency_overrides[get_current_user] = override_current_user
    with patch("backend.routers.auth.get_saas_and_launch_url", return_value=_launch_tuple()):
        response = client.get("/api/auth/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["control_plane_token"] is None
    assert payload["control_plane_token_fingerprint"] == tenant.control_plane_token_fingerprint
    assert payload["control_plane_token_active"] is True


def test_rotate_control_plane_token_returns_one_time_value_and_audits(client: TestClient) -> None:
    tenant = SimpleNamespace(
        id=uuid.uuid4(),
        control_plane_token="a" * 64,
        control_plane_token_fingerprint="cptok-ol...1111",
        control_plane_token_created_at=datetime.now(timezone.utc),
        control_plane_token_revoked_at=None,
        control_plane_previous_token=None,
        control_plane_previous_token_fingerprint=None,
        control_plane_previous_token_expires_at=None,
    )
    current_user = SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant.id, role="admin")

    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(tenant))
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def override_current_user():
        return current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    response = client.post("/api/auth/control-plane-token/rotate")

    assert response.status_code == 200
    payload = response.json()
    revealed_token = payload["control_plane_token"]
    assert revealed_token.startswith("cptok-")
    assert tenant.control_plane_token == hash_control_plane_token(revealed_token)
    assert tenant.control_plane_token_fingerprint == payload["control_plane_token_fingerprint"]
    assert tenant.control_plane_token_revoked_at is None
    assert tenant.control_plane_previous_token == "a" * 64
    assert tenant.control_plane_previous_token_fingerprint == "cptok-ol...1111"
    assert tenant.control_plane_previous_token_expires_at is not None
    grace_window = timedelta(hours=auth_router.settings.CONTROL_PLANE_PREVIOUS_TOKEN_GRACE_HOURS)
    expires_at_delta = tenant.control_plane_previous_token_expires_at - tenant.control_plane_token_created_at
    assert grace_window - timedelta(seconds=5) <= expires_at_delta <= grace_window + timedelta(seconds=5)
    assert any(
        isinstance(call.args[0], AuditLog) and call.args[0].event_type == "control_plane_token_rotated"
        for call in session.add.call_args_list
    )


def test_revoke_control_plane_token_deactivates_and_audits(client: TestClient) -> None:
    tenant = SimpleNamespace(
        id=uuid.uuid4(),
        control_plane_token="b" * 64,
        control_plane_token_fingerprint="cptok-ab...9999",
        control_plane_token_created_at=datetime.now(timezone.utc),
        control_plane_token_revoked_at=None,
        control_plane_previous_token="c" * 64,
        control_plane_previous_token_fingerprint="cptok-cd...8888",
        control_plane_previous_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    current_user = SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant.id, role="admin")

    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(tenant))
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def override_current_user():
        return current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    response = client.post("/api/auth/control-plane-token/revoke")

    assert response.status_code == 200
    payload = response.json()
    assert payload["control_plane_token_active"] is False
    assert tenant.control_plane_token_revoked_at is not None
    assert tenant.control_plane_previous_token is None
    assert tenant.control_plane_previous_token_fingerprint is None
    assert tenant.control_plane_previous_token_expires_at is None
    assert any(
        isinstance(call.args[0], AuditLog) and call.args[0].event_type == "control_plane_token_revoked"
        for call in session.add.call_args_list
    )


def test_accept_invite_never_returns_existing_control_plane_token(client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    invite_token = str(uuid.uuid4())
    tenant = SimpleNamespace(
        id=uuid.uuid4(),
        name="Acme Security",
        external_id="ext-test-123",
        control_plane_token="deadbeef" * 8,
        control_plane_token_fingerprint="cptok-ab...1234",
        control_plane_token_created_at=now,
        control_plane_token_revoked_at=None,
    )
    invite = SimpleNamespace(
        token=uuid.UUID(invite_token),
        email="admin@acme.com",
        tenant_id=tenant.id,
        expires_at=now + timedelta(days=1),
    )
    existing_user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=invite.email,
        name="Existing Admin",
        role="admin",
        onboarding_completed_at=None,
        password_hash=hash_password("oldpassword"),
    )

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(invite),
            _result(existing_user),
            _result(tenant),
        ]
    )
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with patch("backend.routers.users.get_saas_and_launch_url", return_value=_launch_tuple()):
        response = client.post(
            "/api/users/accept-invite",
            json={
                "token": invite_token,
                "password": "supersafepassword",
                "name": "Updated Admin",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["control_plane_token"] is None
    assert payload["control_plane_token_fingerprint"] == tenant.control_plane_token_fingerprint
    assert payload["control_plane_token_active"] is True


def test_public_intake_hashes_token_before_lookup(client: TestClient) -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(None))

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with patch("backend.routers.control_plane.hash_control_plane_token", return_value="hashed-token") as mock_hash:
        response = client.post(
            "/api/control-plane/events",
            headers={"X-Control-Plane-Token": "cptok-test-token"},
            json=_valid_event(),
        )

    assert response.status_code == 403
    mock_hash.assert_called_once_with("cptok-test-token")
