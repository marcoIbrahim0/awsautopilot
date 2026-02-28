from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app


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
        "SecurityAutopilotControlPlaneForwarder",
    )


def _invite_with_context(token: str, *, expired: bool = False) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    tenant = SimpleNamespace(id=uuid.uuid4(), name="Valens", external_id="ext-test-invite")
    inviter = SimpleNamespace(name="Marco Admin")
    return SimpleNamespace(
        token=uuid.UUID(token),
        email="wave3-invitee@example.com",
        tenant_id=tenant.id,
        tenant=tenant,
        created_by_user=inviter,
        expires_at=now - timedelta(minutes=1) if expired else now + timedelta(days=1),
    )


@pytest.mark.parametrize("endpoint", ["/api/users/accept-invite", "/api/users/invite-info"])
def test_get_invite_info_valid_token_contract(client: TestClient, endpoint: str) -> None:
    token = str(uuid.uuid4())
    invite = _invite_with_context(token, expired=False)
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(invite))

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get(endpoint, params={"token": token})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "email": invite.email,
        "tenant_name": invite.tenant.name,
        "inviter_name": invite.created_by_user.name,
    }


@pytest.mark.parametrize("endpoint", ["/api/users/accept-invite", "/api/users/invite-info"])
def test_get_invite_info_invalid_token_format_returns_400(client: TestClient, endpoint: str) -> None:
    session = MagicMock()
    session.execute = AsyncMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get(endpoint, params={"token": "not-a-uuid"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid invite token format"
    assert session.execute.await_count == 0


@pytest.mark.parametrize("endpoint", ["/api/users/accept-invite", "/api/users/invite-info"])
def test_get_invite_info_expired_token_returns_410(client: TestClient, endpoint: str) -> None:
    token = str(uuid.uuid4())
    invite = _invite_with_context(token, expired=True)
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(invite))

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get(endpoint, params={"token": token})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 410
    assert response.json()["detail"] == "This invite has expired"


def test_accept_invite_invalid_token_format_returns_400(client: TestClient) -> None:
    session = MagicMock()
    session.execute = AsyncMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/api/users/accept-invite",
            json={
                "token": "not-a-uuid",
                "password": "TempPass123!",
                "name": "Wave 3 User",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid invite token format"
    assert session.execute.await_count == 0


def test_accept_invite_expired_token_returns_410(client: TestClient) -> None:
    token = str(uuid.uuid4())
    invite = _invite_with_context(token, expired=True)
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(invite))

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/api/users/accept-invite",
            json={
                "token": token,
                "password": "TempPass123!",
                "name": "Wave 3 User",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 410
    assert response.json()["detail"] == "This invite has expired"


def test_accept_invite_valid_once_then_reused_token_rejected(client: TestClient) -> None:
    token = str(uuid.uuid4())
    invite = _invite_with_context(token, expired=False)
    existing_user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=invite.tenant_id,
        email=invite.email,
        name="Existing User",
        role="member",
        onboarding_completed_at=None,
        password_hash="old-hash",
        token_version=0,
    )
    tenant = SimpleNamespace(
        id=invite.tenant_id,
        name=invite.tenant.name,
        external_id=invite.tenant.external_id,
    )

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(invite),
            _result(existing_user),
            _result(tenant),
            _result(None),
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
        first = client.post(
            "/api/users/accept-invite",
            json={
                "token": token,
                "password": "TempPass123!",
                "name": "Updated User",
            },
        )
        second = client.post(
            "/api/users/accept-invite",
            json={
                "token": token,
                "password": "TempPass123!",
                "name": "Updated User",
            },
        )

    assert first.status_code == 200
    assert second.status_code == 404
    assert second.json()["detail"] == "Invite not found or expired"
    assert session.delete.await_count == 1
