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


def test_delete_204_runs_cleanup_then_deletes(client: TestClient) -> None:
    tenant = _mock_tenant()
    account = _mock_account("123456789012")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, account]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = mock_get_db
    with patch("backend.routers.aws_accounts.cleanup_account_resources") as mock_cleanup:
        try:
            response = client.delete(_delete_url("123456789012"), params={"tenant_id": str(tenant.id)})
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 204
    mock_cleanup.assert_called_once_with(account=account, external_id=tenant.external_id)


def test_delete_400_when_cleanup_fails(client: TestClient) -> None:
    tenant = _mock_tenant()
    account = _mock_account("123456789012")

    db_session = MagicMock()
    db_session.delete = AsyncMock()
    db_session.commit = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, account]
        db_session.execute = AsyncMock(return_value=result)
        yield db_session

    app.dependency_overrides[get_db] = mock_get_db
    with patch(
        "backend.routers.aws_accounts.cleanup_account_resources",
        side_effect=AwsCleanupError("missing IAM permissions"),
    ):
        try:
            response = client.delete(_delete_url("123456789012"), params={"tenant_id": str(tenant.id)})
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 400
    assert "failed to clean up aws resources" in response.json()["detail"].lower()
    db_session.delete.assert_not_awaited()
    db_session.commit.assert_not_awaited()


def test_delete_204_skips_cleanup_when_disabled(client: TestClient) -> None:
    tenant = _mock_tenant()
    account = _mock_account("123456789012")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, account]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = mock_get_db
    with patch("backend.routers.aws_accounts.cleanup_account_resources") as mock_cleanup:
        try:
            response = client.delete(
                _delete_url("123456789012"),
                params={"tenant_id": str(tenant.id), "cleanup_resources": "false"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 204
    mock_cleanup.assert_not_called()
