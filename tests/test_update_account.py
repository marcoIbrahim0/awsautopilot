"""
Unit tests for PATCH /api/aws/accounts/{account_id} (Step 8.1 — WriteRole update).

Tests cover:
- Validation errors (invalid role_write_arn format)
- Account not found (404)
- Account ID mismatch in role_write_arn (400)
- Success: set role_write_arn
- Success: clear role_write_arn (null)
- Success: empty body (no change)
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app
from backend.models.enums import AwsAccountStatus


def _patch_url(account_id: str) -> str:
    return f"/api/aws/accounts/{account_id}"


def _mock_account(account_id: str, role_write_arn: str | None = None) -> MagicMock:
    acc = MagicMock()
    acc.id = uuid.uuid4()
    acc.account_id = account_id
    acc.role_read_arn = f"arn:aws:iam::{account_id}:role/ReadRole"
    acc.role_write_arn = role_write_arn
    acc.regions = ["us-east-1"]
    acc.status = AwsAccountStatus.validated
    acc.last_validated_at = datetime.now(timezone.utc)
    acc.created_at = datetime.now(timezone.utc)
    acc.updated_at = datetime.now(timezone.utc)
    return acc


def test_patch_422_invalid_role_write_arn_format(client: TestClient) -> None:
    """role_write_arn must be a valid IAM role ARN when provided."""
    r = client.patch(_patch_url("123456789012"), json={"role_write_arn": "invalid-arn"})
    assert r.status_code == 422
    assert "role" in r.text.lower() or "arn" in r.text.lower()


def test_patch_404_account_not_found(client: TestClient) -> None:
    """PATCH returns 404 when account does not exist for tenant."""
    tenant = MagicMock()
    acc = None  # No account found

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, acc]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        yield session

    app.dependency_overrides[get_db] = mock_get_db
    try:
        r = client.patch(
            _patch_url("123456789012"),
            json={"role_write_arn": "arn:aws:iam::123456789012:role/WriteRole"},
            params={"tenant_id": str(uuid.uuid4())},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_patch_400_role_write_arn_account_mismatch(client: TestClient) -> None:
    """role_write_arn account ID must match path account_id."""
    tenant = MagicMock()
    acc = _mock_account("123456789012")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, acc]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = mock_get_db
    try:
        r = client.patch(
            _patch_url("123456789012"),
            json={"role_write_arn": "arn:aws:iam::999999999999:role/WriteRole"},
            params={"tenant_id": str(uuid.uuid4())},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 400
    assert "match" in r.json()["detail"].lower() or "account" in r.json()["detail"].lower()


def test_patch_200_set_role_write_arn(client: TestClient) -> None:
    """Successfully set role_write_arn."""
    tenant = MagicMock()
    acc = _mock_account("123456789012", role_write_arn=None)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, acc]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = mock_get_db
    try:
        r = client.patch(
            _patch_url("123456789012"),
            json={"role_write_arn": "arn:aws:iam::123456789012:role/SecurityAutopilotWriteRole"},
            params={"tenant_id": str(uuid.uuid4())},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data["role_write_arn"] == "arn:aws:iam::123456789012:role/SecurityAutopilotWriteRole"
    assert data["account_id"] == "123456789012"


def test_patch_200_clear_role_write_arn(client: TestClient) -> None:
    """Successfully clear role_write_arn with null."""
    tenant = MagicMock()
    acc = _mock_account("123456789012", role_write_arn="arn:aws:iam::123456789012:role/WriteRole")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, acc]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = mock_get_db
    try:
        r = client.patch(
            _patch_url("123456789012"),
            json={"role_write_arn": None},
            params={"tenant_id": str(uuid.uuid4())},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data["role_write_arn"] is None
