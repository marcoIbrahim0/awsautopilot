from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth import require_saas_admin
from backend.database import get_db
from backend.routers.saas_admin import router as saas_admin_router


app = FastAPI()
app.include_router(saas_admin_router, prefix="/api")


def _result(*, scalar: object | None = None) -> MagicMock:
    res = MagicMock()
    res.scalar.return_value = scalar
    return res


def test_system_health_exposes_phase3_slo_metrics() -> None:
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(scalar=2),    # remediation_failed
            _result(scalar=10),   # remediation_total
            _result(scalar=1),    # baseline_failed
            _result(scalar=4),    # baseline_total
            _result(scalar=0),    # exports_failed
            _result(scalar=2),    # exports_total
            _result(scalar=30),   # control_plane_total
            _result(scalar=3),    # control_plane_dropped
            _result(scalar=4500), # queue_lag_p95
        ]
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_require_saas_admin():
        return SimpleNamespace(id="admin-id", email="admin@example.com")

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[require_saas_admin] = mock_require_saas_admin

    with patch("backend.routers.saas_admin.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/ingest"
        mock_settings.S3_EXPORT_BUCKET = "security-autopilot-exports"
        mock_settings.S3_SUPPORT_BUCKET = "security-autopilot-support"
        try:
            client = TestClient(app)
            response = client.get("/api/saas/system-health")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(require_saas_admin, None)

    assert response.status_code == 200
    body = response.json()
    assert body["window_hours"] == 24
    assert body["failing_remediation_runs_24h"] == 2
    assert body["failing_baseline_reports_24h"] == 1
    assert body["failing_exports_24h"] == 0
    assert body["remediation_failure_rate_24h"] == 0.2
    assert body["baseline_report_failure_rate_24h"] == 0.25
    assert body["export_failure_rate_24h"] == 0.0
    assert body["worker_failure_rate_24h"] == 0.1875
    assert body["control_plane_drop_rate_24h"] == 0.1
    assert body["p95_queue_lag_ms_24h"] == 4500.0
