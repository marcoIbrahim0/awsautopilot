from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.models.app_notification import AppNotification
from backend.models.user import User
from backend.services.notification_center import serialize_notification


def _mock_user() -> MagicMock:
    user = MagicMock(spec=User)
    user.id = uuid.UUID("123e4567-e89b-12d3-a456-426614174001")
    user.tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    user.email = "admin@example.com"
    user.name = "Admin"
    return user


def _build_job_notification(status: str = "running", minutes_ago: int = 1) -> AppNotification:
    now = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    item = AppNotification(
        id=uuid.UUID("223e4567-e89b-12d3-a456-426614174000"),
        tenant_id=uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
        actor_user_id=uuid.UUID("123e4567-e89b-12d3-a456-426614174001"),
        kind="job",
        source="background_job",
        severity="info",
        status=status,
        title="Findings refresh",
        message="Refresh running.",
        detail=None,
        progress=45,
        client_key="job-1",
        created_at=now,
        updated_at=now,
    )
    return item


def test_list_notifications_requires_auth() -> None:
    client = TestClient(app)
    response = client.get("/api/notifications")
    assert response.status_code == 401


def test_list_notifications_returns_items_from_service() -> None:
    user = _mock_user()
    session = MagicMock()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> MagicMock:
        return user

    notification = _build_job_notification()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with patch(
            "backend.routers.notifications.fetch_notification_rows",
            new=AsyncMock(return_value=([(notification, None)], 1, 1)),
        ):
            client = TestClient(app)
            response = client.get("/api/notifications")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["unread_total"] == 1
    assert payload["items"][0]["client_key"] == "job-1"


def test_upsert_job_notification_commits_and_returns_item() -> None:
    user = _mock_user()
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> MagicMock:
        return user

    notification = _build_job_notification(status="success")
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with patch(
            "backend.routers.notifications.upsert_job_notification",
            new=AsyncMock(return_value=notification),
        ) as mock_upsert:
            client = TestClient(app)
            response = client.put(
                "/api/notifications/jobs/job-1",
                json={
                    "status": "success",
                    "title": "Findings refresh",
                    "message": "Refresh complete.",
                    "progress": 100,
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once()
    assert mock_upsert.await_args.kwargs["client_key"] == "job-1"


def test_patch_notification_state_requires_ids_for_archive() -> None:
    user = _mock_user()
    session = MagicMock()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        client = TestClient(app)
        response = client.patch("/api/notifications/state", json={"action": "archive"})
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 400


def test_patch_notification_state_marks_all_read() -> None:
    user = _mock_user()
    session = MagicMock()
    session.commit = AsyncMock()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with patch(
            "backend.routers.notifications.apply_state_action",
            new=AsyncMock(return_value=4),
        ):
            client = TestClient(app)
            response = client.patch("/api/notifications/state", json={"action": "mark_all_read"})
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json()["updated"] == 4
    session.commit.assert_awaited_once()


def test_serialize_notification_marks_stale_active_jobs_as_timed_out() -> None:
    notification = _build_job_notification(minutes_ago=25)
    serialized = serialize_notification(notification, None, datetime.now(timezone.utc))
    assert serialized["status"] == "timed_out"
    assert serialized["severity"] == "error"
    assert serialized["progress"] == 100


def test_governance_dispatch_mirrors_in_app_notification() -> None:
    session = MagicMock()
    existing = MagicMock()
    existing.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=existing)
    session.flush = AsyncMock()
    tenant = MagicMock()
    tenant.id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    tenant.name = "Tenant One"
    with patch(
        "backend.services.governance_notifications._resolve_channels",
        return_value=["in_app"],
    ), patch(
        "backend.services.governance_notifications._deliver_channel",
        new=AsyncMock(return_value=("sent", None)),
    ), patch(
        "backend.services.governance_notifications.mirror_governance_notification",
        new=AsyncMock(),
    ) as mock_mirror:
        from backend.services.governance_notifications import dispatch_governance_notification

        result = asyncio.run(
            dispatch_governance_notification(
                session,
                tenant=tenant,
                stage="in_progress",
                target_type="remediation_run",
                target_id=uuid.UUID("323e4567-e89b-12d3-a456-426614174000"),
                target_label="Fix bucket policy",
                detail="Applying fix",
                action_url="https://app.example.com/actions/1",
                idempotency_key="k1",
            )
        )

    assert result.delivered == 1
    assert mock_mirror.await_count == 1
