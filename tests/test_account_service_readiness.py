"""
Contract tests for GET /api/aws/accounts/{account_id}/service-readiness.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app
from backend.models.enums import AwsAccountStatus


def _url(account_id: str = "123456789012") -> str:
    return f"/api/aws/accounts/{account_id}/service-readiness"


def _params(tenant_id: str = "123e4567-e89b-12d3-a456-426614174000") -> dict:
    return {"tenant_id": tenant_id}


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def test_service_readiness_404_account_not_found(client: TestClient) -> None:
    tenant = SimpleNamespace(external_id="ext-123")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        session = MagicMock()
        session.execute = AsyncMock(side_effect=[_scalar_result(tenant), _scalar_result(None)])
        yield session

    app.dependency_overrides[get_db] = mock_get_db
    try:
        response = client.post(_url(), params=_params())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_service_readiness_200_all_services_enabled(client: TestClient) -> None:
    tenant = SimpleNamespace(external_id="ext-123")
    account = SimpleNamespace(
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/TestRole",
        regions=["us-east-1"],
        status=AwsAccountStatus.validated,
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        session = MagicMock()
        session.execute = AsyncMock(side_effect=[_scalar_result(tenant), _scalar_result(account)])
        yield session

    sts = MagicMock()
    sts.get_caller_identity.return_value = {"Account": "123456789012"}
    security_hub = MagicMock()
    security_hub.describe_hub.return_value = {}
    config = MagicMock()
    config.describe_configuration_recorders.return_value = {"ConfigurationRecorders": [{"name": "default"}]}
    config.describe_configuration_recorder_status.return_value = {"ConfigurationRecordersStatus": [{"recording": True}]}
    access_analyzer = MagicMock()
    access_analyzer.list_analyzers.side_effect = [
        {"analyzers": [{"status": "ACTIVE"}]},
        {"analyzers": [{"status": "ACTIVE"}]},
    ]
    inspector = MagicMock()
    inspector.batch_get_account_status.return_value = {"accounts": [{"state": {"status": "ENABLED"}}]}

    def client_factory(service_name: str, **_: object) -> MagicMock:
        if service_name == "sts":
            return sts
        if service_name == "securityhub":
            return security_hub
        if service_name == "config":
            return config
        if service_name == "accessanalyzer":
            return access_analyzer
        if service_name == "inspector2":
            return inspector
        return MagicMock()

    boto_session = MagicMock()
    boto_session.client.side_effect = client_factory

    with patch("backend.routers.aws_accounts.assume_role", return_value=boto_session):
        app.dependency_overrides[get_db] = mock_get_db
        try:
            response = client.post(_url(), params=_params())
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["overall_ready"] is True
    assert body["all_security_hub_enabled"] is True
    assert body["all_aws_config_enabled"] is True
    assert body["all_access_analyzer_enabled"] is True
    assert body["all_inspector_enabled"] is True
    assert body["missing_security_hub_regions"] == []
    assert body["missing_aws_config_regions"] == []
    assert body["missing_access_analyzer_regions"] == []
    assert body["missing_inspector_regions"] == []
    assert len(body["regions"]) == 1


def test_service_readiness_400_on_caller_mismatch(client: TestClient) -> None:
    tenant = SimpleNamespace(external_id="ext-123")
    account = SimpleNamespace(
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/TestRole",
        regions=["us-east-1"],
        status=AwsAccountStatus.validated,
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        session = MagicMock()
        session.execute = AsyncMock(side_effect=[_scalar_result(tenant), _scalar_result(account)])
        yield session

    sts = MagicMock()
    sts.get_caller_identity.return_value = {"Account": "999999999999"}
    boto_session = MagicMock()
    boto_session.client.return_value = sts

    with patch("backend.routers.aws_accounts.assume_role", return_value=boto_session):
        app.dependency_overrides[get_db] = mock_get_db
        try:
            response = client.post(_url(), params=_params())
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 400
    assert "mismatch" in response.json()["detail"].lower()
