"""API contract tests for /api/audit-log (Wave 8 Test 32)."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app


def _mock_user(role: str = "admin") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        email=f"{role}@example.com",
        role=role,
    )


def _mock_session_with_audit_rows(rows: list[SimpleNamespace], total: int) -> MagicMock:
    count_result = MagicMock()
    count_result.scalar_one.return_value = total

    list_result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = rows
    list_result.scalars.return_value = scalars

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[count_result, list_result])
    return session


def test_audit_log_admin_can_read_events(client: TestClient) -> None:
    user = _mock_user(role="admin")
    row = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        user_id=user.id,
        event_type="control_plane_token_rotated",
        entity_type="tenant",
        entity_id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
    )
    session = _mock_session_with_audit_rows([row], total=1)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        response = client.get("/api/audit-log")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["action"] == "control_plane_token_rotated"
    assert payload["items"][0]["payload"] is None


def test_audit_log_member_is_forbidden(client: TestClient) -> None:
    user = _mock_user(role="member")
    session = _mock_session_with_audit_rows([], total=0)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        response = client.get("/api/audit-log")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403


def test_audit_log_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/audit-log")
    assert response.status_code == 401
