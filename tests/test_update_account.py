"""
Unit tests for PATCH /api/aws/accounts/{account_id}.

Tests cover:
- Validation errors for role ARNs
- Account not found and account-ID mismatch cases
- Successful WriteRole, ReadRole, and region updates
- Failed revalidation leaves stored account data unchanged
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app
from backend.models.enums import AwsAccountStatus


def _patch_url(account_id: str) -> str:
    return f"/api/aws/accounts/{account_id}"


def _params() -> dict[str, str]:
    return {"tenant_id": str(uuid.uuid4())}


def _mock_account(account_id: str, role_write_arn: str | None = None) -> MagicMock:
    acc = MagicMock()
    acc.id = uuid.uuid4()
    acc.account_id = account_id
    acc.role_read_arn = f"arn:aws:iam::{account_id}:role/ReadRole"
    acc.role_write_arn = role_write_arn
    acc.regions = ["us-east-1"]
    acc.status = AwsAccountStatus.validated
    acc.last_validated_at = datetime(2026, 3, 11, tzinfo=timezone.utc)
    acc.created_at = datetime.now(timezone.utc)
    acc.updated_at = datetime.now(timezone.utc)
    return acc


def _mock_tenant() -> MagicMock:
    tenant = MagicMock()
    tenant.external_id = "ext-123"
    return tenant


def _override_db(tenant: MagicMock, account: MagicMock | None) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, account]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = mock_get_db


def _mock_assume_session(account_id: str) -> MagicMock:
    session = MagicMock()
    sts = MagicMock()
    sts.get_caller_identity.return_value = {"Account": account_id}

    def client_factory(service_name: str, **kwargs) -> MagicMock:
        if service_name == "sts":
            return sts
        return MagicMock()

    session.client.side_effect = client_factory
    return session


def test_patch_422_invalid_role_read_arn_format(client: TestClient) -> None:
    r = client.patch(_patch_url("123456789012"), json={"role_read_arn": "invalid-arn"})
    assert r.status_code == 422
    assert "role" in r.text.lower() or "arn" in r.text.lower()


def test_patch_200_invalid_role_write_arn_is_ignored(client: TestClient) -> None:
    tenant = _mock_tenant()
    acc = _mock_account("123456789012")
    _override_db(tenant, acc)
    try:
        r = client.patch(
            _patch_url("123456789012"),
            json={"role_write_arn": "invalid-arn"},
            params=_params(),
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data["role_write_arn"] is None
    assert acc.role_write_arn is None


def test_patch_404_account_not_found(client: TestClient) -> None:
    tenant = _mock_tenant()
    _override_db(tenant, None)
    try:
        r = client.patch(
            _patch_url("123456789012"),
            json={"role_write_arn": "arn:aws:iam::123456789012:role/WriteRole"},
            params=_params(),
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_patch_400_role_read_arn_account_mismatch(client: TestClient) -> None:
    tenant = _mock_tenant()
    acc = _mock_account("123456789012")
    _override_db(tenant, acc)
    try:
        r = client.patch(
            _patch_url("123456789012"),
            json={"role_read_arn": "arn:aws:iam::999999999999:role/ReadRole"},
            params=_params(),
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 400
    assert "mismatch" in r.json()["detail"].lower() or "match" in r.json()["detail"].lower()
    assert acc.role_read_arn == "arn:aws:iam::123456789012:role/ReadRole"


def test_patch_200_role_write_arn_account_mismatch_is_ignored(client: TestClient) -> None:
    tenant = _mock_tenant()
    acc = _mock_account("123456789012")
    _override_db(tenant, acc)
    try:
        r = client.patch(
            _patch_url("123456789012"),
            json={"role_write_arn": "arn:aws:iam::999999999999:role/WriteRole"},
            params=_params(),
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data["role_write_arn"] is None
    assert acc.role_write_arn is None


def test_patch_200_updates_read_role_and_regions(client: TestClient) -> None:
    tenant = _mock_tenant()
    acc = _mock_account("123456789012", role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    previous_validated_at = acc.last_validated_at
    _override_db(tenant, acc)

    with patch("backend.routers.aws_accounts.assume_role", return_value=_mock_assume_session(acc.account_id)) as mock_assume:
        try:
            r = client.patch(
                _patch_url(acc.account_id),
                json={
                    "role_read_arn": "arn:aws:iam::123456789012:role/NewReadRole",
                    "regions": ["us-east-1", "us-west-2"],
                },
                params=_params(),
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data["role_read_arn"] == "arn:aws:iam::123456789012:role/NewReadRole"
    assert data["regions"] == ["us-east-1", "us-west-2"]
    assert acc.role_read_arn == "arn:aws:iam::123456789012:role/NewReadRole"
    assert acc.regions == ["us-east-1", "us-west-2"]
    assert acc.role_write_arn == "arn:aws:iam::123456789012:role/WriteRole"
    assert acc.status == AwsAccountStatus.validated
    assert acc.last_validated_at >= previous_validated_at
    assert mock_assume.call_count == 1


def test_patch_200_set_role_write_arn_is_ignored(client: TestClient) -> None:
    tenant = _mock_tenant()
    acc = _mock_account("123456789012")
    _override_db(tenant, acc)

    with patch("backend.routers.aws_accounts.assume_role", return_value=_mock_assume_session(acc.account_id)) as mock_assume:
        try:
            r = client.patch(
                _patch_url(acc.account_id),
                json={"role_write_arn": "arn:aws:iam::123456789012:role/SecurityAutopilotWriteRole"},
                params=_params(),
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data["role_write_arn"] is None
    assert acc.role_write_arn is None
    assert acc.status == AwsAccountStatus.validated
    assert mock_assume.call_count == 0


def test_patch_200_clear_role_write_arn(client: TestClient) -> None:
    tenant = _mock_tenant()
    acc = _mock_account("123456789012", role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    _override_db(tenant, acc)
    try:
        r = client.patch(
            _patch_url("123456789012"),
            json={"role_write_arn": None},
            params=_params(),
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data["role_write_arn"] is None
    assert acc.role_write_arn is None


def test_patch_400_failed_revalidation_keeps_existing_account_state(client: TestClient) -> None:
    tenant = _mock_tenant()
    acc = _mock_account("123456789012")
    original_regions = list(acc.regions)
    original_role_read_arn = acc.role_read_arn
    _override_db(tenant, acc)

    sts_error = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
        "AssumeRole",
    )

    with patch("backend.routers.aws_accounts.assume_role", side_effect=sts_error):
        try:
            r = client.patch(
                _patch_url(acc.account_id),
                json={
                    "role_read_arn": "arn:aws:iam::123456789012:role/NewReadRole",
                    "regions": ["us-east-1", "eu-west-1"],
                },
                params=_params(),
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 400
    assert "failed to assume role" in r.json()["detail"].lower()
    assert acc.role_read_arn == original_role_read_arn
    assert acc.regions == original_regions
