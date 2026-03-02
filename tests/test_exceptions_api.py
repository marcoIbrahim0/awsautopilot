"""
Unit tests for Exceptions API (Step 6.2).

Tests cover:
- POST /api/exceptions: create exception with validation
- GET /api/exceptions: list with filters and pagination
- GET /api/exceptions/{id}: get single exception
- DELETE /api/exceptions/{id}: revoke exception
- Authentication requirements
- Tenant isolation
- Expiry validation
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.models.enums import EntityType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_session_with_user(
    user: object | None = None,
    tenant: object | None = None,
    entity: object | None = None,
    exception: object | None = None,
) -> MagicMock:
    """Build mock AsyncSession for DB queries."""
    result = MagicMock()
    # Configure side_effect based on what's being queried
    results = []
    if tenant:
        results.append(tenant)
    if entity:
        results.append(entity)
    if exception is not None:
        results.append(exception)
    
    result.scalar_one_or_none.side_effect = results if results else [None]
    result.scalar.return_value = 0
    result.scalars.return_value.unique.return_value.all.return_value = []
    
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    return session


def _mock_tenant(tenant_id: str = "123e4567-e89b-12d3-a456-426614174000") -> MagicMock:
    """Create mock tenant."""
    tenant = MagicMock()
    tenant.id = uuid.UUID(tenant_id)
    tenant.name = "Test Tenant"
    return tenant


def _mock_user(
    user_id: str = "223e4567-e89b-12d3-a456-426614174000",
    tenant_id: str = "123e4567-e89b-12d3-a456-426614174000",
) -> MagicMock:
    """Create mock user."""
    user = MagicMock()
    user.id = uuid.UUID(user_id)
    user.tenant_id = uuid.UUID(tenant_id)
    user.email = "test@example.com"
    user.name = "Test User"
    user.tenant = _mock_tenant(tenant_id)
    return user


def _mock_finding(
    finding_id: str = "323e4567-e89b-12d3-a456-426614174000",
    tenant_id: str = "123e4567-e89b-12d3-a456-426614174000",
) -> MagicMock:
    """Create mock finding."""
    finding = MagicMock()
    finding.id = uuid.UUID(finding_id)
    finding.tenant_id = uuid.UUID(tenant_id)
    finding.finding_id = "arn:aws:securityhub:us-east-1:123456789012:finding/test"
    finding.title = "Test Finding"
    return finding


def _mock_action(
    action_id: str = "423e4567-e89b-12d3-a456-426614174000",
    tenant_id: str = "123e4567-e89b-12d3-a456-426614174000",
) -> MagicMock:
    """Create mock action."""
    action = MagicMock()
    action.id = uuid.UUID(action_id)
    action.tenant_id = uuid.UUID(tenant_id)
    action.title = "Test Action"
    action.status = "open"
    return action


def _mock_exception(
    exception_id: str = "523e4567-e89b-12d3-a456-426614174000",
    entity_type: str = "finding",
    entity_id: str = "323e4567-e89b-12d3-a456-426614174000",
    tenant_id: str = "123e4567-e89b-12d3-a456-426614174000",
    approved_by_id: str = "223e4567-e89b-12d3-a456-426614174000",
) -> MagicMock:
    """Create mock exception."""
    exc = MagicMock()
    exc.id = uuid.UUID(exception_id)
    exc.tenant_id = uuid.UUID(tenant_id)
    exc.entity_type = EntityType(entity_type)
    exc.entity_id = uuid.UUID(entity_id)
    exc.reason = "Test suppression reason"
    exc.approved_by_user_id = uuid.UUID(approved_by_id)
    exc.ticket_link = "https://jira.example.com/TICKET-123"
    exc.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    exc.owner_user_id = None
    exc.owner = None
    exc.approval_metadata = None
    exc.reminder_interval_days = None
    exc.next_reminder_at = None
    exc.last_reminded_at = None
    exc.revalidation_interval_days = None
    exc.next_revalidation_at = None
    exc.last_revalidated_at = None
    exc.created_at = datetime.now(timezone.utc)
    exc.updated_at = datetime.now(timezone.utc)
    exc.approved_by = _mock_user(approved_by_id, tenant_id)
    return exc


def _valid_create_request(
    entity_type: str = "finding",
    entity_id: str = "323e4567-e89b-12d3-a456-426614174000",
) -> dict:
    """Valid create exception request."""
    future_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "reason": "This is a valid suppression reason with enough characters",
        "expires_at": future_date,
        "ticket_link": "https://jira.example.com/TICKET-123",
    }


# ---------------------------------------------------------------------------
# POST /api/exceptions - Create exception
# ---------------------------------------------------------------------------

def test_create_exception_success_finding() -> None:
    """Successfully create exception for a finding."""
    user = _mock_user()
    finding = _mock_finding()
    exc = _mock_exception()
    result_entity = MagicMock()
    result_entity.scalar_one_or_none.return_value = finding
    result_existing = MagicMock()
    result_existing.scalar_one_or_none.return_value = None
    result_requery = MagicMock()
    result_requery.scalar_one.return_value = exc
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[result_entity, result_existing, result_requery])
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def _override_get_current_user() -> MagicMock:
        return user

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        req = _valid_create_request()
        r = client.post("/api/exceptions", json=req)
        assert r.status_code == 201
        data = r.json()
        assert data["entity_type"] == "finding"
        assert "id" in data
        assert "approved_by_email" in data
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
    data = r.json()
    assert data["entity_type"] == "finding"
    assert "id" in data
    assert "approved_by_email" in data


def test_create_exception_invalid_entity_id() -> None:
    """Reject invalid entity_id (not a UUID)."""
    user = _mock_user()
    session = _mock_session_with_user(user=user)
    async def _override_get_current_user() -> MagicMock:
        return user
    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        req = _valid_create_request()
        req["entity_id"] = "not-a-uuid"
        r = client.post("/api/exceptions", json=req)
        assert r.status_code == 400
        assert "entity_id" in r.json()["detail"]["error"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_create_exception_expires_in_past() -> None:
    """Reject expires_at in the past."""
    user = _mock_user()
    session = _mock_session_with_user(user=user)
    async def _override_get_current_user() -> MagicMock:
        return user
    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        req = _valid_create_request()
        req["expires_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        r = client.post("/api/exceptions", json=req)
        assert r.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
    assert "future" in r.json()["detail"]["detail"].lower()


def test_create_exception_entity_not_found() -> None:
    """Reject when entity (finding/action) not found."""
    user = _mock_user()
    session = _mock_session_with_user(user=user, tenant=None, entity=None)
    async def _override_get_current_user() -> MagicMock:
        return user
    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        req = _valid_create_request()
        r = client.post("/api/exceptions", json=req)
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
    assert "not found" in r.json()["detail"]["error"].lower()


def test_create_exception_duplicate() -> None:
    """Reject when exception already exists for entity."""
    user = _mock_user()
    tenant = _mock_tenant()
    finding = _mock_finding()
    existing_exc = _mock_exception()
    session = _mock_session_with_user(user=user, tenant=tenant, entity=finding, exception=existing_exc)
    async def _override_get_current_user() -> MagicMock:
        return user
    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        req = _valid_create_request()
        r = client.post("/api/exceptions", json=req)
        assert r.status_code == 409
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
    assert "already exists" in r.json()["detail"]["error"].lower()


def test_create_exception_requires_auth() -> None:
    """POST /api/exceptions requires authentication."""
    client = TestClient(app)
    req = _valid_create_request()
    r = client.post("/api/exceptions", json=req)
    
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/exceptions - List exceptions
# ---------------------------------------------------------------------------

@patch("backend.routers.exceptions.resolve_tenant_id")
@patch("backend.routers.exceptions.get_tenant", new_callable=AsyncMock)
def test_list_exceptions_success(mock_get_tenant, mock_resolve_tenant) -> None:
    """Successfully list exceptions."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    mock_resolve_tenant.return_value = tenant_id
    mock_get_tenant.return_value = _mock_tenant(str(tenant_id))
    exc1 = _mock_exception()
    exc2 = _mock_exception(
        exception_id="623e4567-e89b-12d3-a456-426614174000",
        entity_type="action",
        entity_id="423e4567-e89b-12d3-a456-426614174000",
    )
    result = MagicMock()
    result.scalar.return_value = 2
    result.scalars.return_value.unique.return_value.all.return_value = [exc1, exc2]
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        r = client.get("/api/exceptions?tenant_id=123e4567-e89b-12d3-a456-426614174000")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
    finally:
        app.dependency_overrides.pop(get_db, None)


@patch("backend.routers.exceptions.resolve_tenant_id")
@patch("backend.routers.exceptions.get_tenant", new_callable=AsyncMock)
def test_list_exceptions_filter_by_entity_type(mock_get_tenant, mock_resolve_tenant) -> None:
    """Filter exceptions by entity_type."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    mock_resolve_tenant.return_value = tenant_id
    mock_get_tenant.return_value = _mock_tenant(str(tenant_id))
    result = MagicMock()
    result.scalar.return_value = 0
    result.scalars.return_value.unique.return_value.all.return_value = []
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        r = client.get("/api/exceptions?tenant_id=123e4567-e89b-12d3-a456-426614174000&entity_type=finding")
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)


@patch("backend.routers.exceptions.resolve_tenant_id")
@patch("backend.routers.exceptions.get_tenant", new_callable=AsyncMock)
def test_list_exceptions_invalid_entity_type(mock_get_tenant, mock_resolve_tenant) -> None:
    """Reject invalid entity_type filter."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    mock_resolve_tenant.return_value = tenant_id
    mock_get_tenant.return_value = _mock_tenant(str(tenant_id))
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock())
    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        r = client.get("/api/exceptions?tenant_id=123e4567-e89b-12d3-a456-426614174000&entity_type=invalid")
        assert r.status_code == 400
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# GET /api/exceptions/{id} - Get single exception
# ---------------------------------------------------------------------------

@patch("backend.routers.exceptions.resolve_tenant_id")
@patch("backend.routers.exceptions.get_tenant", new_callable=AsyncMock)
def test_get_exception_success(mock_get_tenant, mock_resolve_tenant) -> None:
    """Successfully get single exception."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    exception_id = "523e4567-e89b-12d3-a456-426614174000"
    mock_resolve_tenant.return_value = tenant_id
    mock_get_tenant.return_value = _mock_tenant(str(tenant_id))
    exc = _mock_exception(exception_id=exception_id)
    result = MagicMock()
    result.scalar_one_or_none.return_value = exc
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        r = client.get(f"/api/exceptions/{exception_id}?tenant_id=123e4567-e89b-12d3-a456-426614174000")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == exception_id
        assert "reason" in data
    finally:
        app.dependency_overrides.pop(get_db, None)


@patch("backend.routers.exceptions.resolve_tenant_id")
@patch("backend.routers.exceptions.get_tenant", new_callable=AsyncMock)
def test_get_exception_not_found(mock_get_tenant, mock_resolve_tenant) -> None:
    """Return 404 when exception not found."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    exception_id = "523e4567-e89b-12d3-a456-426614174000"
    mock_resolve_tenant.return_value = tenant_id
    mock_get_tenant.return_value = _mock_tenant(str(tenant_id))
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        r = client.get(f"/api/exceptions/{exception_id}?tenant_id=123e4567-e89b-12d3-a456-426614174000")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@patch("backend.routers.exceptions.resolve_tenant_id")
@patch("backend.routers.exceptions.get_tenant", new_callable=AsyncMock)
def test_get_exception_invalid_id(mock_get_tenant, mock_resolve_tenant) -> None:
    """Reject invalid exception_id (not UUID)."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    mock_resolve_tenant.return_value = tenant_id
    mock_get_tenant.return_value = _mock_tenant(str(tenant_id))
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock())
    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        r = client.get("/api/exceptions/not-a-uuid?tenant_id=123e4567-e89b-12d3-a456-426614174000")
        assert r.status_code == 400
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# DELETE /api/exceptions/{id} - Revoke exception
# ---------------------------------------------------------------------------

@patch("backend.routers.exceptions.resolve_tenant_id")
@patch("backend.routers.exceptions.get_tenant", new_callable=AsyncMock)
def test_revoke_exception_success(mock_get_tenant, mock_resolve_tenant) -> None:
    """Successfully revoke exception."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    exception_id = "523e4567-e89b-12d3-a456-426614174000"
    mock_resolve_tenant.return_value = tenant_id
    mock_get_tenant.return_value = _mock_tenant(str(tenant_id))
    exc = _mock_exception(exception_id=exception_id)
    result = MagicMock()
    result.scalar_one_or_none.return_value = exc
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        r = client.delete(f"/api/exceptions/{exception_id}?tenant_id=123e4567-e89b-12d3-a456-426614174000")
        assert r.status_code == 204
    finally:
        app.dependency_overrides.pop(get_db, None)


@patch("backend.routers.exceptions.resolve_tenant_id")
@patch("backend.routers.exceptions.get_tenant", new_callable=AsyncMock)
def test_revoke_exception_not_found(mock_get_tenant, mock_resolve_tenant) -> None:
    """Return 404 when exception to revoke not found."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    exception_id = "523e4567-e89b-12d3-a456-426614174000"
    mock_resolve_tenant.return_value = tenant_id
    mock_get_tenant.return_value = _mock_tenant(str(tenant_id))
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        r = client.delete(f"/api/exceptions/{exception_id}?tenant_id=123e4567-e89b-12d3-a456-426614174000")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
