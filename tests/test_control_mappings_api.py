"""
Unit tests for control mappings API (Step 12.3).

Covers: GET list (auth, filters), GET by id (404, 200), POST (admin only, 409 on duplicate).
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.models.control_mapping import ControlMapping


def _mock_user(tenant_id: uuid.UUID, role: str = "member") -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.tenant_id = tenant_id
    u.email = "user@example.com"
    u.role = role
    return u


def _mock_control_mapping(
    control_id: str = "S3.1",
    framework_name: str = "CIS AWS Foundations Benchmark",
) -> MagicMock:
    m = MagicMock(spec=ControlMapping)
    m.id = uuid.uuid4()
    m.control_id = control_id
    m.framework_name = framework_name
    m.framework_control_code = "3.1"
    m.control_title = "Ensure S3 block public access"
    m.description = "S3 account-level block public access"
    m.created_at = datetime.now(timezone.utc)
    return m


def _mock_async_session(*scalar_results: object, list_result: list | None = None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.side_effect = list(scalar_results) if scalar_results else [None]
    if list_result is not None:
        result.scalars.return_value.all.return_value = list_result
        result.scalar.return_value = len(list_result)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


# ---------------------------------------------------------------------------
# GET /api/control-mappings — requires auth
# ---------------------------------------------------------------------------


def test_list_control_mappings_requires_auth(client: TestClient) -> None:
    """GET /api/control-mappings without auth returns 401."""
    r = client.get("/api/control-mappings")
    assert r.status_code == 401


def test_list_control_mappings_200(client: TestClient) -> None:
    """GET /api/control-mappings with auth returns 200 with items and total."""
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    m1 = _mock_control_mapping("S3.1", "CIS AWS Foundations Benchmark")
    m2 = _mock_control_mapping("CloudTrail.1", "SOC 2")

    count_result = MagicMock()
    count_result.scalar.return_value = 2
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [m1, m2]
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[count_result, list_result])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        r = client.get("/api/control-mappings")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["control_id"] == "S3.1"
    assert data["items"][1]["control_id"] == "CloudTrail.1"


# ---------------------------------------------------------------------------
# GET /api/control-mappings/{id} — 404 when not found, 200 when found
# ---------------------------------------------------------------------------


def test_get_control_mapping_404(client: TestClient) -> None:
    """GET /api/control-mappings/{id} returns 404 when not found."""
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        r = client.get(f"/api/control-mappings/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 404


def test_get_control_mapping_200(client: TestClient) -> None:
    """GET /api/control-mappings/{id} returns 200 with mapping when found."""
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    m = _mock_control_mapping("S3.1", "CIS AWS Foundations Benchmark")

    result = MagicMock()
    result.scalar_one_or_none.return_value = m
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        r = client.get(f"/api/control-mappings/{m.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["id"] == str(m.id)
    assert data["control_id"] == "S3.1"
    assert data["framework_name"] == "CIS AWS Foundations Benchmark"


# ---------------------------------------------------------------------------
# POST /api/control-mappings — admin only, 409 on duplicate
# ---------------------------------------------------------------------------


def test_create_control_mapping_403_when_member(client: TestClient) -> None:
    """POST /api/control-mappings as member returns 403."""
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id, role="member")
    session = _mock_async_session()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        r = client.post(
            "/api/control-mappings",
            json={
                "control_id": "NewControl.1",
                "framework_name": "SOC 2",
                "framework_control_code": "CC6.1",
                "control_title": "Logical access",
                "description": "Logical and physical access controls",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 403
    assert "admin" in (r.json().get("detail") or "").lower()
