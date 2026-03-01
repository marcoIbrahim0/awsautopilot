"""
Wave 4 contract/regression tests for fixes in Tests 09-12 scope.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.routers.findings import (
    _effective_status_from_values,
    _parse_severity_filter_values,
    finding_to_response,
)


def test_parse_severity_filter_values_rejects_invalid_labels() -> None:
    with pytest.raises(HTTPException) as exc:
        _parse_severity_filter_values("CRITICAL,NOT_REAL")
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Invalid severity"
    assert exc.value.detail["invalid_values"] == ["NOT_REAL"]


def test_parse_severity_filter_values_accepts_multi_value() -> None:
    values = _parse_severity_filter_values("critical,high")
    assert values == ["CRITICAL", "HIGH"]


def test_effective_status_prefers_shadow_resolved() -> None:
    assert _effective_status_from_values("NEW", "RESOLVED") == "RESOLVED"


def test_effective_status_reopens_shadow_open_canonical_resolved() -> None:
    assert _effective_status_from_values("RESOLVED", "OPEN") == "NEW"


def test_finding_response_uses_effective_status_for_badge() -> None:
    now = datetime.now(timezone.utc)
    finding = SimpleNamespace(
        id=uuid.uuid4(),
        finding_id="finding-123",
        tenant_id=uuid.uuid4(),
        account_id="123456789012",
        region="eu-north-1",
        source="security_hub",
        severity_label="HIGH",
        severity_normalized=75,
        status="NEW",
        in_scope=True,
        title="Example finding",
        description="Example description",
        resource_id="arn:aws:s3:::example-bucket",
        resource_type="AwsS3Bucket",
        control_id="S3.2",
        standard_name="AWS Foundational Security Best Practices v1.0.0",
        first_observed_at=now,
        last_observed_at=now,
        resolved_at=None,
        sh_updated_at=now,
        created_at=now,
        updated_at=now,
        raw_json={},
        shadow_status_raw="RESOLVED",
        shadow_status_normalized="RESOLVED",
        shadow_status_reason="shadow signal",
        shadow_last_observed_event_time=now,
        shadow_last_evaluated_at=now,
        shadow_fingerprint="fp-1",
        shadow_source="event_monitor_shadow",
    )

    response = finding_to_response(finding)

    assert response.canonical_status == "NEW"
    assert response.status == "RESOLVED"
    assert response.effective_status == "RESOLVED"
    assert response.display_badge == "resolved"


def test_ingest_progress_includes_compatibility_fields(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    account = MagicMock()
    account.account_id = "123456789012"

    first_result = MagicMock()
    first_result.scalar_one_or_none.return_value = account
    second_result = MagicMock()
    second_result.one.return_value = (0, None)

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=[first_result, second_result])

    user = MagicMock()
    user.tenant_id = tenant_id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        response = client.get(
            "/api/aws/accounts/123456789012/ingest-progress",
            params={"started_after": "2026-02-28T00:00:00Z"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["progress"] == body["percent_complete"]
    assert "estimated_time_remaining" in body
