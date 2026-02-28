"""
Unit tests for DELETE /api/aws/accounts/{account_id}.

Tests cover:
- Successful account removal with AWS cleanup enabled (default)
- Cleanup failure blocks account removal
- Optional bypass with cleanup_resources=false
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.services.aws_account_cleanup import AwsCleanupError


def _delete_url(account_id: str) -> str:
    return f"/api/aws/accounts/{account_id}"


def _mock_tenant() -> MagicMock:
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.external_id = "ext-123"
    return tenant


def _mock_account(account_id: str) -> MagicMock:
    account = MagicMock()
    account.account_id = account_id
    account.role_read_arn = f"arn:aws:iam::{account_id}:role/SecurityAutopilotReadRole"
    account.role_write_arn = f"arn:aws:iam::{account_id}:role/SecurityAutopilotWriteRole"
    return account


def _mock_user(tenant_id: uuid.UUID, role: str = "admin") -> MagicMock:
    user = MagicMock()
    user.tenant_id = tenant_id
    user.role = role
    return user


def test_delete_204_runs_cleanup_then_deletes(client: TestClient) -> None:
    tenant = _mock_tenant()
    account = _mock_account("123456789012")
    admin_user = _mock_user(tenant.id, role="admin")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, account]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        yield session

    async def mock_get_optional_user() -> MagicMock:
        return admin_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.aws_accounts.cleanup_account_resources") as mock_cleanup:
        try:
            response = client.delete(_delete_url("123456789012"), params={"tenant_id": str(tenant.id)})
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 204
    mock_cleanup.assert_called_once_with(account=account, external_id=tenant.external_id)


def test_delete_400_when_cleanup_fails(client: TestClient) -> None:
    tenant = _mock_tenant()
    account = _mock_account("123456789012")
    admin_user = _mock_user(tenant.id, role="admin")

    db_session = MagicMock()
    db_session.delete = AsyncMock()
    db_session.commit = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, account]
        db_session.execute = AsyncMock(return_value=result)
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return admin_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch(
        "backend.routers.aws_accounts.cleanup_account_resources",
        side_effect=AwsCleanupError("missing IAM permissions"),
    ):
        try:
            response = client.delete(_delete_url("123456789012"), params={"tenant_id": str(tenant.id)})
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 400
    assert "failed to clean up aws resources" in response.json()["detail"].lower()
    db_session.delete.assert_not_awaited()
    db_session.commit.assert_not_awaited()


def test_delete_204_skips_cleanup_when_disabled(client: TestClient) -> None:
    tenant = _mock_tenant()
    account = _mock_account("123456789012")
    admin_user = _mock_user(tenant.id, role="admin")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, account]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        yield session

    async def mock_get_optional_user() -> MagicMock:
        return admin_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.aws_accounts.cleanup_account_resources") as mock_cleanup:
        try:
            response = client.delete(
                _delete_url("123456789012"),
                params={"tenant_id": str(tenant.id), "cleanup_resources": "false"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 204
    mock_cleanup.assert_not_called()


def test_delete_401_when_not_authenticated(client: TestClient) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        session = MagicMock()
        session.execute = AsyncMock()
        yield session

    async def mock_get_optional_user() -> None:
        return None

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        response = client.delete(_delete_url("123456789012"))
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 401


def test_delete_403_when_member_user(client: TestClient) -> None:
    member_user = _mock_user(uuid.uuid4(), role="member")

    db_session = MagicMock()
    db_session.execute = AsyncMock()
    db_session.delete = AsyncMock()
    db_session.commit = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return member_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        response = client.delete(_delete_url("123456789012"))
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 403
    db_session.execute.assert_not_awaited()
    db_session.delete.assert_not_awaited()
    db_session.commit.assert_not_awaited()
