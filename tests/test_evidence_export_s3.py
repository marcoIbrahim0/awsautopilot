"""
Tests for Step 10.5 + IMP-009 tenant isolation coverage.

Asserts key pattern, presigned URL expiry, tenant path isolation, and cross-tenant
negative authorization behavior for exports APIs.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth import get_current_user, get_optional_user
from backend.database import get_db
from backend.models.enums import EvidenceExportStatus
from backend.routers.exports import router as exports_router
from backend.services.evidence_export_s3 import (
    BASELINE_REPORT_FILENAME,
    BASELINE_REPORT_KEY_PREFIX,
    EVIDENCE_PACK_FILENAME,
    EXPORT_KEY_PREFIX,
    PRESIGNED_URL_EXPIRES_IN,
    build_baseline_report_s3_key,
    build_export_s3_key,
)


app = FastAPI()
app.include_router(exports_router, prefix="/api")


@pytest.fixture
def export_client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = tenant_id
    user.email = "user@example.com"
    return user


def _mock_tenant(tenant_id: uuid.UUID) -> MagicMock:
    tenant = MagicMock()
    tenant.id = tenant_id
    return tenant


def _mock_export_row(tenant_id: uuid.UUID) -> MagicMock:
    export = MagicMock()
    export.id = uuid.uuid4()
    export.tenant_id = tenant_id
    export.status = EvidenceExportStatus.success
    export.pack_type = "evidence"
    export.created_at = datetime.now(timezone.utc)
    export.completed_at = datetime.now(timezone.utc)
    return export


@pytest.fixture
def multi_tenant_setup() -> dict[str, object]:
    """Fixture with two tenants and users for spoofing attempts."""
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    return {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "tenant_a_user": _mock_user(tenant_a_id),
        "tenant_b_user": _mock_user(tenant_b_id),
    }


def test_build_export_s3_key_tenant_isolation() -> None:
    """Key pattern isolates tenants by path: exports/{tenant_id}/{export_id}/evidence-pack.zip."""
    tenant_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    export_id = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    key = build_export_s3_key(tenant_id, export_id)
    assert key.startswith(EXPORT_KEY_PREFIX + "/")
    assert str(tenant_id) in key
    assert str(export_id) in key
    assert key.endswith("/" + EVIDENCE_PACK_FILENAME)
    assert key == f"exports/{tenant_id}/{export_id}/evidence-pack.zip"


def test_build_export_s3_key_different_tenants_different_paths() -> None:
    """Different tenant_id produces different path prefix."""
    export_id = uuid.uuid4()
    key1 = build_export_s3_key(uuid.uuid4(), export_id)
    key2 = build_export_s3_key(uuid.uuid4(), export_id)
    assert key1 != key2
    parts1 = key1.split("/")
    parts2 = key2.split("/")
    assert parts1[0] == parts2[0] == EXPORT_KEY_PREFIX
    assert parts1[1] != parts2[1]  # tenant_id differs


def test_presigned_url_expiry_one_hour() -> None:
    """Presigned URL expiry is 3600 seconds (1 hour) per Step 10.5."""
    assert PRESIGNED_URL_EXPIRES_IN == 3600


def test_build_baseline_report_s3_key_pattern() -> None:
    """Baseline report key: baseline-reports/{tenant_id}/{report_id}/baseline-report.html (Step 13.2)."""
    tenant_id = uuid.uuid4()
    report_id = uuid.uuid4()
    key = build_baseline_report_s3_key(tenant_id, report_id)
    assert key.startswith(BASELINE_REPORT_KEY_PREFIX + "/")
    assert str(tenant_id) in key
    assert str(report_id) in key
    assert key.endswith("/" + BASELINE_REPORT_FILENAME)
    assert key == f"baseline-reports/{tenant_id}/{report_id}/baseline-report.html"


def test_get_export_cross_tenant_read_attempt_returns_404(
    export_client: TestClient,
    multi_tenant_setup: dict[str, object],
) -> None:
    """Authenticated tenant cannot read another tenant's export even if tenant_id is spoofed."""
    tenant_a_id = multi_tenant_setup["tenant_a_id"]
    tenant_b_id = multi_tenant_setup["tenant_b_id"]
    user = multi_tenant_setup["tenant_a_user"]
    victim_export_id = uuid.uuid4()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = _mock_tenant(tenant_a_id)
    export_result = MagicMock()
    export_result.scalar_one_or_none.return_value = None
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, export_result])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        response = export_client.get(f"/api/exports/{victim_export_id}?tenant_id={tenant_b_id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 404
    tenant_query = session.execute.call_args_list[0].args[0]
    export_query = session.execute.call_args_list[1].args[0]
    assert tenant_query.compile().params["id_1"] == tenant_a_id
    assert export_query.compile().params["tenant_id_1"] == tenant_a_id
    assert export_query.compile().params["id_1"] == victim_export_id


def test_list_exports_cross_tenant_query_param_is_ignored_for_authenticated_user(
    export_client: TestClient,
    multi_tenant_setup: dict[str, object],
) -> None:
    """Authenticated tenant listing ignores spoofed tenant_id query parameter."""
    tenant_a_id = multi_tenant_setup["tenant_a_id"]
    tenant_b_id = multi_tenant_setup["tenant_b_id"]
    user = multi_tenant_setup["tenant_a_user"]

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = _mock_tenant(tenant_a_id)
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [_mock_export_row(tenant_a_id)]
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, count_result, list_result])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        response = export_client.get(f"/api/exports?tenant_id={tenant_b_id}&limit=20&offset=0")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    count_query = session.execute.call_args_list[1].args[0]
    list_query = session.execute.call_args_list[2].args[0]
    assert tenant_a_id in count_query.compile().params.values()
    assert tenant_a_id in list_query.compile().params.values()


def test_create_export_cross_tenant_mutation_spoof_uses_authenticated_tenant(
    export_client: TestClient,
    multi_tenant_setup: dict[str, object],
) -> None:
    """Create export always enqueues with auth tenant_id, not spoofed query tenant_id."""
    tenant_a_id = multi_tenant_setup["tenant_a_id"]
    tenant_b_id = multi_tenant_setup["tenant_b_id"]
    user = multi_tenant_setup["tenant_a_user"]

    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    export_id = uuid.uuid4()
    created_at = datetime.now(timezone.utc)

    async def refresh_side_effect(export_obj: object) -> None:
        export_obj.id = export_id
        export_obj.created_at = created_at

    session.refresh = AsyncMock(side_effect=refresh_side_effect)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.exports.settings") as mock_settings:
        mock_settings.S3_EXPORT_BUCKET = "ci-export-bucket"
        mock_settings.SQS_EXPORT_REPORT_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
        mock_settings.S3_EXPORT_BUCKET_REGION = "us-east-1"
        mock_settings.AWS_REGION = "us-east-1"
        with patch("backend.routers.exports.build_generate_export_job_payload") as mock_payload:
            mock_payload.return_value = {
                "job_type": "generate_export",
                "export_id": str(export_id),
                "tenant_id": str(tenant_a_id),
                "created_at": created_at.isoformat(),
                "pack_type": "evidence",
            }
            with patch("backend.routers.exports.boto3") as mock_boto3:
                mock_boto3.client.return_value = MagicMock()
                try:
                    response = export_client.post(
                        f"/api/exports?tenant_id={tenant_b_id}",
                        json={"pack_type": "evidence"},
                    )
                finally:
                    app.dependency_overrides.pop(get_db, None)
                    app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 202
    assert response.json()["id"] == str(export_id)
    assert mock_payload.called
    payload_args = mock_payload.call_args.args
    assert payload_args[1] == tenant_a_id
    assert payload_args[1] != tenant_b_id
