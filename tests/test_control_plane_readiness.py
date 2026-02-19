"""
Unit tests for GET /api/aws/accounts/{account_id}/control-plane-readiness.

Evidence focus:
- onboarding gate blocks when any monitored region is stale/missing
- onboarding gate passes only when all monitored regions are recent
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.routers.aws_accounts import router as aws_accounts_router


app = FastAPI()
app.include_router(aws_accounts_router, prefix="/api")


def _client() -> TestClient:
    return TestClient(app)


def _readiness_url(account_id: str = "123456789012") -> str:
    return f"/api/aws/accounts/{account_id}/control-plane-readiness"


def test_control_plane_readiness_blocks_when_region_missing_or_stale() -> None:
    tenant_id = uuid.uuid4()
    account = SimpleNamespace(account_id="123456789012", regions=["eu-north-1", "us-east-1"])

    now = datetime.now(timezone.utc)
    rows = [
        SimpleNamespace(
            region="us-east-1",
            last_event_time=now - timedelta(minutes=95),
            last_intake_time=now - timedelta(minutes=95),
        )
    ]

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        yield session

    with patch("backend.routers.aws_accounts.resolve_tenant_id", return_value=tenant_id):
        with patch("backend.routers.aws_accounts.get_account_for_tenant", new=AsyncMock(return_value=account)):
            app.dependency_overrides[get_db] = mock_get_db
            try:
                response = _client().get(
                    _readiness_url(),
                    params={"tenant_id": str(tenant_id), "stale_after_minutes": 30},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert data["overall_ready"] is False
    assert sorted(data["missing_regions"]) == ["eu-north-1", "us-east-1"]
    assert len(data["regions"]) == 2


def test_control_plane_readiness_passes_when_all_regions_recent() -> None:
    tenant_id = uuid.uuid4()
    account = SimpleNamespace(account_id="123456789012", regions=["eu-north-1", "us-east-1"])

    now = datetime.now(timezone.utc)
    rows = [
        SimpleNamespace(
            region="eu-north-1",
            last_event_time=now - timedelta(minutes=4),
            last_intake_time=now - timedelta(minutes=4),
        ),
        SimpleNamespace(
            region="us-east-1",
            last_event_time=now - timedelta(minutes=7),
            last_intake_time=now - timedelta(minutes=7),
        ),
    ]

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        yield session

    with patch("backend.routers.aws_accounts.resolve_tenant_id", return_value=tenant_id):
        with patch("backend.routers.aws_accounts.get_account_for_tenant", new=AsyncMock(return_value=account)):
            app.dependency_overrides[get_db] = mock_get_db
            try:
                response = _client().get(
                    _readiness_url(),
                    params={"tenant_id": str(tenant_id), "stale_after_minutes": 30},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert data["overall_ready"] is True
    assert data["missing_regions"] == []
    assert len(data["regions"]) == 2
