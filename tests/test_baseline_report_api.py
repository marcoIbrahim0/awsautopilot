"""
Unit tests for baseline report API (Step 13.3).

Covers: POST (auth, 503 when not configured, 429 rate limit, 201 created),
GET list, GET by id (404, 200 with download_url when success), and
GET by id/data (auth, 404/409/200 contracts).
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.models.baseline_report import BaselineReport
from backend.models.enums import BaselineReportStatus
from backend.routers.baseline_report import router as baseline_report_router


app = FastAPI()
app.include_router(baseline_report_router, prefix="/api")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.tenant_id = tenant_id
    u.email = "user@example.com"
    return u


def _mock_tenant() -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    return t


def _mock_baseline_report(
    status: BaselineReportStatus = BaselineReportStatus.pending,
    s3_bucket: str | None = None,
    s3_key: str | None = None,
    file_size_bytes: int | None = None,
) -> MagicMock:
    r = MagicMock()
    r.id = uuid.uuid4()
    r.tenant_id = uuid.uuid4()
    r.status = status
    r.requested_at = datetime.now(timezone.utc)
    r.completed_at = None
    r.s3_bucket = s3_bucket
    r.s3_key = s3_key
    r.file_size_bytes = file_size_bytes
    r.outcome = None
    r.account_ids = None
    return r


def _mock_async_session(*scalar_results: object, scalar_side_effect=None) -> MagicMock:
    result = MagicMock()
    if scalar_side_effect is not None:
        result.scalar_one_or_none.side_effect = scalar_side_effect
    else:
        result.scalar_one_or_none.side_effect = list(scalar_results) if scalar_results else [None]
    result.scalars.return_value.all.return_value = []
    result.scalar.return_value = 0
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# POST /api/baseline-report
# ---------------------------------------------------------------------------


def test_create_baseline_report_requires_auth_401(client: TestClient) -> None:
    """POST /api/baseline-report without auth returns 401."""
    r = client.post("/api/baseline-report", json={})
    assert r.status_code == 401


def test_create_baseline_report_503_when_not_configured(client: TestClient) -> None:
    """POST /api/baseline-report returns 503 when S3_EXPORT_BUCKET is not set."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    session = _mock_async_session(None)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.baseline_report.settings") as mock_settings:
        mock_settings.S3_EXPORT_BUCKET = ""
        mock_settings.SQS_EXPORT_REPORT_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
        try:
            r = client.post("/api/baseline-report", json={})
        finally:
            pass
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 503
    data = r.json()
    assert "detail" in data
    detail = data["detail"]
    s = str(detail) if not isinstance(detail, dict) else (detail.get("detail", "") + " " + detail.get("error", ""))
    assert "Baseline report" in s or "S3" in s


def test_create_baseline_report_429_rate_limit(client: TestClient) -> None:
    """POST /api/baseline-report returns 429 when tenant has a report in last 24h."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    recent_report = _mock_baseline_report(status=BaselineReportStatus.success)
    recent_report.created_at = datetime.now(timezone.utc)
    recent_report.tenant_id = tenant.id

    session = _mock_async_session(scalar_side_effect=[recent_report])
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.baseline_report.settings") as mock_settings:
        mock_settings.S3_EXPORT_BUCKET = "my-bucket"
        mock_settings.SQS_EXPORT_REPORT_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
        try:
            r = client.post("/api/baseline-report", json={})
        finally:
            pass
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 429
    assert "Retry-After" in r.headers
    data = r.json()
    assert "detail" in data


def test_create_baseline_report_201_created(client: TestClient) -> None:
    """POST /api/baseline-report with auth and config returns 201 and enqueues job."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    report = _mock_baseline_report(status=BaselineReportStatus.pending)
    report.id = uuid.uuid4()
    report.tenant_id = tenant.id
    report.requested_at = datetime.now(timezone.utc)

    session = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.side_effect = [None, report]
    execute_result.scalars.return_value.all.return_value = []
    execute_result.scalar.return_value = 0
    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.baseline_report.settings") as mock_settings:
        mock_settings.S3_EXPORT_BUCKET = "my-bucket"
        mock_settings.SQS_EXPORT_REPORT_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
        with patch("backend.routers.baseline_report.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.client.return_value = mock_sqs
            try:
                r = client.post("/api/baseline-report", json={})
            finally:
                pass
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data.get("status") == "pending"
    assert "requested_at" in data
    assert "48 hours" in data.get("message", "")


def test_create_baseline_report_400_invalid_account_ids(client: TestClient) -> None:
    """POST /api/baseline-report with invalid account_ids returns 400."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    session = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.baseline_report.settings") as mock_settings:
        mock_settings.S3_EXPORT_BUCKET = "my-bucket"
        mock_settings.SQS_EXPORT_REPORT_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
        try:
            r = client.post("/api/baseline-report", json={"account_ids": ["not-12-digits"]})
        finally:
            pass
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/baseline-report/{id}
# ---------------------------------------------------------------------------


def test_get_baseline_report_404_when_not_found(client: TestClient) -> None:
    """GET /api/baseline-report/{id} returns 404 when report not found or wrong tenant."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    session = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=execute_result)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        r = client.get(f"/api/baseline-report/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 404


def test_get_baseline_report_200_with_download_url_when_success(client: TestClient) -> None:
    """GET /api/baseline-report/{id} returns 200 with download_url when status is success."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    report = _mock_baseline_report(
        status=BaselineReportStatus.success,
        s3_bucket="my-bucket",
        s3_key="baseline-reports/tenant-id/report-id/baseline-report.html",
        file_size_bytes=1024,
    )
    report.id = uuid.uuid4()
    report.tenant_id = tenant.id
    report.requested_at = datetime.now(timezone.utc)
    report.completed_at = datetime.now(timezone.utc)
    report.outcome = None

    session = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = report
    session.execute = AsyncMock(return_value=execute_result)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.baseline_report.generate_presigned_url") as mock_presign:
        mock_presign.return_value = "https://s3.example.com/presigned-url"
        try:
            r = client.get(f"/api/baseline-report/{report.id}")
        finally:
            pass
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "success"
    assert data.get("download_url") == "https://s3.example.com/presigned-url"
    assert data.get("file_size_bytes") == 1024
    assert r.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate"


# ---------------------------------------------------------------------------
# GET /api/baseline-report/{id}/data
# ---------------------------------------------------------------------------


def test_get_baseline_report_data_requires_auth_401(client: TestClient) -> None:
    """GET /api/baseline-report/{id}/data without auth returns 401."""
    r = client.get(f"/api/baseline-report/{uuid.uuid4()}/data")
    assert r.status_code == 401


def test_get_baseline_report_data_404_when_not_found(client: TestClient) -> None:
    """GET /api/baseline-report/{id}/data returns 404 when report not found for tenant."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)

    session = MagicMock()
    report_lookup_result = MagicMock()
    report_lookup_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=report_lookup_result)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        r = client.get(f"/api/baseline-report/{uuid.uuid4()}/data")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 404


def test_get_baseline_report_data_409_when_not_ready(client: TestClient) -> None:
    """GET /api/baseline-report/{id}/data returns 409 while report is pending/running."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    report = _mock_baseline_report(status=BaselineReportStatus.pending)
    report.id = uuid.uuid4()
    report.tenant_id = tenant.id

    session = MagicMock()
    report_lookup_result = MagicMock()
    report_lookup_result.scalar_one_or_none.return_value = report
    session.execute = AsyncMock(return_value=report_lookup_result)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        r = client.get(f"/api/baseline-report/{report.id}/data")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 409
    assert r.json()["detail"]["status"] == "pending"


def test_get_baseline_report_data_200_when_success(client: TestClient) -> None:
    """GET /api/baseline-report/{id}/data returns viewer payload for successful report."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    report = _mock_baseline_report(status=BaselineReportStatus.success)
    report.id = uuid.uuid4()
    report.tenant_id = tenant.id
    report.account_ids = ["029037611564"]

    report_lookup_result = MagicMock()
    report_lookup_result.scalar_one_or_none.return_value = report
    tenant_lookup_result = MagicMock()
    tenant_lookup_result.scalar_one_or_none.return_value = "Valens"
    previous_report_lookup_result = MagicMock()
    previous_report_lookup_result.all.return_value = []

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[report_lookup_result, previous_report_lookup_result, tenant_lookup_result]
    )
    session.run_sync = AsyncMock(
        return_value=MagicMock(
            model_dump=MagicMock(
                return_value={
                    "summary": {
                        "total_finding_count": 1,
                        "critical_count": 0,
                        "high_count": 1,
                        "medium_count": 0,
                        "low_count": 0,
                        "informational_count": 0,
                        "open_count": 1,
                        "resolved_count": 0,
                        "narrative": "Example narrative",
                        "report_date": "2026-03-01",
                        "generated_at": "2026-03-01T01:00:00Z",
                        "account_count": 1,
                        "region_count": 1,
                    },
                    "top_risks": [],
                    "recommendations": [],
                    "tenant_name": "Valens",
                    "appendix_findings": None,
                }
            )
        )
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        r = client.get(f"/api/baseline-report/{report.id}/data")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["total_finding_count"] == 1
    assert data["tenant_name"] == "Valens"
    assert r.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate"


# ---------------------------------------------------------------------------
# GET /api/baseline-report (list)
# ---------------------------------------------------------------------------


def test_list_baseline_reports_requires_auth(client: TestClient) -> None:
    """GET /api/baseline-report without auth returns 401."""
    r = client.get("/api/baseline-report")
    assert r.status_code == 401


def test_list_baseline_reports_200(client: TestClient) -> None:
    """GET /api/baseline-report with auth returns 200 with items and total."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    report = _mock_baseline_report()
    report.id = uuid.uuid4()
    report.tenant_id = tenant.id
    report.requested_at = datetime.now(timezone.utc)
    report.completed_at = None

    session = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    execute_result.scalar.return_value = 1
    execute_result.scalars.return_value.all.return_value = [report]
    session.execute = AsyncMock(return_value=execute_result)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        r = client.get("/api/baseline-report?limit=20&offset=0")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "pending"
