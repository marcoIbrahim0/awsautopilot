"""
Contract tests for source-specific ingest triggers.

Locks behavior for:
- POST /api/aws/accounts/{account_id}/ingest-access-analyzer
- POST /api/aws/accounts/{account_id}/ingest-inspector
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.main import app
from backend.models.enums import AwsAccountStatus


def _source_url(endpoint_suffix: str, account_id: str = "123456789012") -> str:
    return f"/api/aws/accounts/{account_id}/{endpoint_suffix}"


def _params(tenant_id: str = "123e4567-e89b-12d3-a456-426614174000") -> dict:
    return {"tenant_id": tenant_id}


def _mock_session(account: object | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = account
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    return session


async def _mock_get_db_with_account(
    *,
    status: AwsAccountStatus = AwsAccountStatus.validated,
    regions: list[str] | None = None,
) -> AsyncGenerator[MagicMock, None]:
    account = MagicMock()
    account.status = status
    account.regions = regions if regions is not None else ["us-east-1", "us-west-2"]
    yield _mock_session(account)


@pytest.mark.parametrize(
    "endpoint_suffix",
    ["ingest-access-analyzer", "ingest-inspector"],
)
def test_source_ingest_503_queue_not_configured(client: TestClient, endpoint_suffix: str) -> None:
    with patch("backend.routers.aws_accounts.settings") as mock_settings:
        mock_settings.has_ingest_queue = False
        response = client.post(_source_url(endpoint_suffix), params=_params())
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "Ingestion service unavailable"


@pytest.mark.parametrize(
    "endpoint_suffix",
    ["ingest-access-analyzer", "ingest-inspector"],
)
def test_source_ingest_409_account_not_validated(client: TestClient, endpoint_suffix: str) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        async for session in _mock_get_db_with_account(status=AwsAccountStatus.error):
            yield session

    with patch("backend.routers.aws_accounts.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        with patch("backend.routers.aws_accounts.get_tenant", new_callable=AsyncMock):
            app.dependency_overrides[get_db] = mock_get_db
            try:
                response = client.post(_source_url(endpoint_suffix), params=_params())
            finally:
                app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "Account not validated"


@pytest.mark.parametrize(
    "endpoint_suffix",
    ["ingest-access-analyzer", "ingest-inspector"],
)
def test_source_ingest_400_regions_override_not_subset(client: TestClient, endpoint_suffix: str) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        async for session in _mock_get_db_with_account(regions=["eu-west-1"]):
            yield session

    with patch("backend.routers.aws_accounts.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        with patch("backend.routers.aws_accounts.get_tenant", new_callable=AsyncMock):
            app.dependency_overrides[get_db] = mock_get_db
            try:
                response = client.post(
                    _source_url(endpoint_suffix),
                    params=_params(),
                    json={"regions": ["us-east-1"]},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 400
    assert "subset" in response.json()["detail"]["detail"].lower()


@pytest.mark.parametrize(
    "endpoint_suffix,enqueue_function,message_prefix",
    [
        ("ingest-access-analyzer", "_enqueue_ingest_access_analyzer_jobs", "Access Analyzer"),
        ("ingest-inspector", "_enqueue_ingest_inspector_jobs", "Inspector"),
    ],
)
def test_source_ingest_202_success_with_region_override(
    client: TestClient,
    endpoint_suffix: str,
    enqueue_function: str,
    message_prefix: str,
) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        async for session in _mock_get_db_with_account(regions=["us-east-1", "us-west-2"]):
            yield session

    with patch("backend.routers.aws_accounts.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        with patch("backend.routers.aws_accounts.get_tenant", new_callable=AsyncMock):
            with patch(f"backend.routers.aws_accounts.{enqueue_function}") as enqueue_mock:
                enqueue_mock.return_value = ["msg-1"]
                app.dependency_overrides[get_db] = mock_get_db
                try:
                    response = client.post(
                        _source_url(endpoint_suffix),
                        params=_params(),
                        json={"regions": ["us-east-1"]},
                    )
                finally:
                    app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 202
    body = response.json()
    assert body["account_id"] == "123456789012"
    assert body["jobs_queued"] == 1
    assert body["regions"] == ["us-east-1"]
    assert body["message_ids"] == ["msg-1"]
    assert body["message"].startswith(message_prefix)
    enqueue_mock.assert_called_once()
