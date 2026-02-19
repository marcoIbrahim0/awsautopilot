"""
Contract tests for POST /api/aws/accounts/{account_id}/onboarding-fast-path.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app
from backend.models.enums import AwsAccountStatus
from backend.services.aws_account_orchestration import RegionServiceReadinessResult, ServiceReadinessSummary


def _url(account_id: str = "123456789012") -> str:
    return f"/api/aws/accounts/{account_id}/onboarding-fast-path"


def _params(tenant_id: str = "123e4567-e89b-12d3-a456-426614174000") -> dict:
    return {"tenant_id": tenant_id}


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _control_plane_result(rows: list[SimpleNamespace]) -> MagicMock:
    result = MagicMock()
    scalar_wrapper = MagicMock()
    scalar_wrapper.all.return_value = rows
    result.scalars.return_value = scalar_wrapper
    return result


def _readiness_summary(
    *,
    missing_security_hub_regions: list[str],
    missing_aws_config_regions: list[str],
    missing_access_analyzer_regions: list[str],
    missing_inspector_regions: list[str],
    regions: list[str],
) -> ServiceReadinessSummary:
    return ServiceReadinessSummary(
        all_security_hub_enabled=len(missing_security_hub_regions) == 0,
        all_aws_config_enabled=len(missing_aws_config_regions) == 0,
        all_access_analyzer_enabled=len(missing_access_analyzer_regions) == 0,
        all_inspector_enabled=len(missing_inspector_regions) == 0,
        missing_security_hub_regions=missing_security_hub_regions,
        missing_aws_config_regions=missing_aws_config_regions,
        missing_access_analyzer_regions=missing_access_analyzer_regions,
        missing_inspector_regions=missing_inspector_regions,
        regions=[
            RegionServiceReadinessResult(
                region=region,
                security_hub_enabled=region not in missing_security_hub_regions,
                aws_config_enabled=region not in missing_aws_config_regions,
                access_analyzer_enabled=region not in missing_access_analyzer_regions,
                inspector_enabled=region not in missing_inspector_regions,
                security_hub_error=None,
                aws_config_error=None,
                access_analyzer_error=None,
                inspector_error=None,
            )
            for region in regions
        ],
    )


def test_onboarding_fast_path_200_queues_when_safe(client: TestClient) -> None:
    tenant = SimpleNamespace(external_id="ext-123")
    account = SimpleNamespace(
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/TestReadRole",
        regions=["us-east-1", "us-west-2"],
        status=AwsAccountStatus.validated,
    )
    now = datetime.now(timezone.utc)
    control_plane_rows = [
        SimpleNamespace(region="us-east-1", last_intake_time=now - timedelta(minutes=3)),
        SimpleNamespace(region="us-west-2", last_intake_time=now - timedelta(minutes=7)),
    ]

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        session = MagicMock()
        session.execute = AsyncMock(
            side_effect=[
                _scalar_result(tenant),
                _scalar_result(account),
                _control_plane_result(control_plane_rows),
            ]
        )
        yield session

    summary = _readiness_summary(
        missing_security_hub_regions=[],
        missing_aws_config_regions=[],
        missing_access_analyzer_regions=["us-west-2"],
        missing_inspector_regions=[],
        regions=["us-east-1", "us-west-2"],
    )

    with (
        patch("backend.routers.aws_accounts.settings") as settings_mock,
        patch("backend.routers.aws_accounts.collect_service_readiness", new_callable=AsyncMock) as readiness_mock,
        patch("backend.routers.aws_accounts._enqueue_ingest_jobs") as enqueue_ingest_mock,
        patch("backend.routers.aws_accounts._enqueue_compute_actions_job") as enqueue_compute_mock,
    ):
        settings_mock.has_ingest_queue = True
        settings_mock.AWS_REGION = "us-east-1"
        readiness_mock.return_value = summary
        enqueue_ingest_mock.return_value = ["ingest-1", "ingest-2"]
        enqueue_compute_mock.return_value = "compute-1"
        app.dependency_overrides[get_db] = mock_get_db
        try:
            response = client.post(_url(), params=_params())
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["fast_path_triggered"] is True
    assert body["ingest_jobs_queued"] == 2
    assert body["ingest_message_ids"] == ["ingest-1", "ingest-2"]
    assert body["compute_actions_queued"] is True
    assert body["compute_actions_message_id"] == "compute-1"
    assert body["missing_access_analyzer_regions"] == ["us-west-2"]
    enqueue_ingest_mock.assert_called_once()
    enqueue_compute_mock.assert_called_once()


def test_onboarding_fast_path_200_deferred_until_security_hub_and_config_ready(client: TestClient) -> None:
    tenant = SimpleNamespace(external_id="ext-123")
    account = SimpleNamespace(
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/TestReadRole",
        regions=["us-east-1"],
        status=AwsAccountStatus.validated,
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        session = MagicMock()
        session.execute = AsyncMock(
            side_effect=[
                _scalar_result(tenant),
                _scalar_result(account),
                _control_plane_result([]),
            ]
        )
        yield session

    summary = _readiness_summary(
        missing_security_hub_regions=["us-east-1"],
        missing_aws_config_regions=["us-east-1"],
        missing_access_analyzer_regions=["us-east-1"],
        missing_inspector_regions=["us-east-1"],
        regions=["us-east-1"],
    )

    with (
        patch("backend.routers.aws_accounts.settings") as settings_mock,
        patch("backend.routers.aws_accounts.collect_service_readiness", new_callable=AsyncMock) as readiness_mock,
        patch("backend.routers.aws_accounts._enqueue_ingest_jobs") as enqueue_ingest_mock,
        patch("backend.routers.aws_accounts._enqueue_compute_actions_job") as enqueue_compute_mock,
    ):
        settings_mock.has_ingest_queue = True
        settings_mock.AWS_REGION = "us-east-1"
        readiness_mock.return_value = summary
        app.dependency_overrides[get_db] = mock_get_db
        try:
            response = client.post(_url(), params=_params())
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["fast_path_triggered"] is False
    assert body["ingest_jobs_queued"] == 0
    assert body["compute_actions_queued"] is False
    assert body["missing_security_hub_regions"] == ["us-east-1"]
    assert body["missing_aws_config_regions"] == ["us-east-1"]
    assert body["missing_inspector_regions"] == ["us-east-1"]
    assert body["missing_control_plane_regions"] == ["us-east-1"]
    assert "deferred" in body["message"].lower()
    enqueue_ingest_mock.assert_not_called()
    enqueue_compute_mock.assert_not_called()


def test_onboarding_fast_path_409_when_account_not_validated(client: TestClient) -> None:
    tenant = SimpleNamespace(external_id="ext-123")
    account = SimpleNamespace(
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/TestReadRole",
        regions=["us-east-1"],
        status=AwsAccountStatus.error,
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        session = MagicMock()
        session.execute = AsyncMock(
            side_effect=[
                _scalar_result(tenant),
                _scalar_result(account),
            ]
        )
        yield session

    with patch("backend.routers.aws_accounts.settings") as settings_mock:
        settings_mock.has_ingest_queue = True
        settings_mock.AWS_REGION = "us-east-1"
        app.dependency_overrides[get_db] = mock_get_db
        try:
            response = client.post(_url(), params=_params())
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 409
    assert "validate" in response.json()["detail"].lower()
