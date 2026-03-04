"""
Unit tests for POST /api/aws/accounts/{account_id}/validate (Step 2.4).

Tests cover:
- Invalid tenant_id (400)
- Tenant not found (404)
- Account not found (404)
- STS assume_role failure → status=error
- Caller identity mismatch (400)
- Security Hub check failure (permissions_ok=False)
- Successful validation (200)
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app
from backend.models.enums import AwsAccountStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validate_url(account_id: str = "123456789012") -> str:
    return f"/api/aws/accounts/{account_id}/validate"


def _params(tenant_id: str = "123e4567-e89b-12d3-a456-426614174000") -> dict:
    return {"tenant_id": tenant_id}


def _mock_account(
    account_id: str = "123456789012",
    status: AwsAccountStatus = AwsAccountStatus.pending,
    regions: list[str] | None = None,
) -> MagicMock:
    acc = MagicMock()
    acc.account_id = account_id
    acc.status = status
    acc.regions = regions if regions is not None else ["us-east-1"]
    acc.role_read_arn = "arn:aws:iam::123456789012:role/TestRole"
    acc.last_validated_at = None
    return acc


# ---------------------------------------------------------------------------
# 400 — Invalid tenant_id
# ---------------------------------------------------------------------------
def test_validate_400_invalid_tenant_id(client: TestClient) -> None:
    """tenant_id must be a valid UUID."""
    r = client.post(_validate_url(), params={"tenant_id": "not-a-uuid"})
    assert r.status_code == 400
    assert "uuid" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 404 — Tenant not found
# ---------------------------------------------------------------------------
def test_validate_404_tenant_not_found(client: TestClient) -> None:
    """Validation fails if tenant doesn't exist."""
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # No tenant
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        yield session
    
    app.dependency_overrides[get_db] = mock_get_db
    try:
        r = client.post(_validate_url(), params=_params())
    finally:
        app.dependency_overrides.pop(get_db, None)
    
    assert r.status_code == 404
    assert "tenant" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 404 — Account not found
# ---------------------------------------------------------------------------
def test_validate_404_account_not_found(client: TestClient) -> None:
    """Validation fails if account doesn't exist for tenant."""
    tenant = MagicMock()
    tenant.external_id = "ext-123"
    
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        # First call: tenant lookup, Second call: account lookup
        result.scalar_one_or_none.side_effect = [tenant, None]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        yield session
    
    app.dependency_overrides[get_db] = mock_get_db
    try:
        r = client.post(_validate_url(), params=_params())
    finally:
        app.dependency_overrides.pop(get_db, None)
    
    assert r.status_code == 404
    assert "account" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 200 — STS failure → status=error, permissions_ok=False
# ---------------------------------------------------------------------------
def test_validate_200_sts_failure(client: TestClient) -> None:
    """STS failure updates status to error and returns permissions_ok=False."""
    tenant = MagicMock()
    tenant.external_id = "ext-123"
    acc = _mock_account()
    
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, acc]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        yield session
    
    sts_error = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
        "AssumeRole"
    )
    
    with patch("backend.routers.aws_accounts.assume_role", side_effect=sts_error):
        app.dependency_overrides[get_db] = mock_get_db
        try:
            r = client.post(_validate_url(), params=_params())
        finally:
            app.dependency_overrides.pop(get_db, None)
    
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "error"
    assert data["permissions_ok"] is False
    assert acc.status == AwsAccountStatus.error


# ---------------------------------------------------------------------------
# 400 — Caller identity mismatch
# ---------------------------------------------------------------------------
def test_validate_400_caller_identity_mismatch(client: TestClient) -> None:
    """Validation fails if get_caller_identity returns different account ID."""
    tenant = MagicMock()
    tenant.external_id = "ext-123"
    acc = _mock_account()
    
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, acc]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        yield session
    
    mock_boto_session = MagicMock()
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {"Account": "999999999999"}  # Different
    mock_boto_session.client.return_value = mock_sts
    
    with patch("backend.routers.aws_accounts.assume_role", return_value=mock_boto_session):
        app.dependency_overrides[get_db] = mock_get_db
        try:
            r = client.post(_validate_url(), params=_params())
        finally:
            app.dependency_overrides.pop(get_db, None)
    
    assert r.status_code == 400
    assert "mismatch" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 200 — Security Hub check failure → permissions_ok=False, status=validated
# ---------------------------------------------------------------------------
def test_validate_200_security_hub_failure(client: TestClient) -> None:
    """STS succeeds but Security Hub fails → validated with permissions_ok=False."""
    tenant = MagicMock()
    tenant.external_id = "ext-123"
    acc = _mock_account()
    
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, acc]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        yield session
    
    mock_boto_session = MagicMock()
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
    
    mock_sh = MagicMock()
    mock_sh.get_findings.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "Not enabled"}},
        "GetFindings"
    )
    
    def client_factory(service_name, **kwargs):
        if service_name == "sts":
            return mock_sts
        elif service_name == "securityhub":
            return mock_sh
        return MagicMock()
    
    mock_boto_session.client.side_effect = client_factory
    
    with patch("backend.routers.aws_accounts.assume_role", return_value=mock_boto_session):
        app.dependency_overrides[get_db] = mock_get_db
        try:
            r = client.post(_validate_url(), params=_params())
        finally:
            app.dependency_overrides.pop(get_db, None)
    
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "validated"
    assert data["permissions_ok"] is False
    required = set(data["required_permissions"])
    assert "config:DescribeConfigurationRecorders" in required
    assert "config:DescribeDeliveryChannels" in required
    assert "config:DescribeConfigRules" in required
    assert "config:DescribeComplianceByConfigRules" in required
    assert "config:GetComplianceDetailsByConfigRule" in required


# ---------------------------------------------------------------------------
# 200 — Full success
# ---------------------------------------------------------------------------
def test_validate_200_success(client: TestClient) -> None:
    """Full validation success: STS + Security Hub both pass."""
    tenant = MagicMock()
    tenant.external_id = "ext-123"
    acc = _mock_account()
    
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [tenant, acc]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        yield session
    
    mock_boto_session = MagicMock()
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
    
    mock_sh = MagicMock()
    mock_sh.get_findings.return_value = {"Findings": []}
    
    def client_factory(service_name, **kwargs):
        if service_name == "sts":
            return mock_sts
        elif service_name == "securityhub":
            return mock_sh
        return MagicMock()
    
    mock_boto_session.client.side_effect = client_factory
    
    with patch("backend.routers.aws_accounts.assume_role", return_value=mock_boto_session):
        app.dependency_overrides[get_db] = mock_get_db
        try:
            r = client.post(_validate_url(), params=_params())
        finally:
            app.dependency_overrides.pop(get_db, None)
    
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "validated"
    assert data["permissions_ok"] is True
    assert data["account_id"] == "123456789012"
    required = set(data["required_permissions"])
    assert "config:DescribeConfigurationRecorders" in required
    assert "config:DescribeDeliveryChannels" in required
    assert "config:DescribeConfigRules" in required
    assert "config:DescribeComplianceByConfigRules" in required
    assert "config:GetComplianceDetailsByConfigRule" in required
    assert acc.status == AwsAccountStatus.validated
