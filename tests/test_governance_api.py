from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.models.enums import UserRole


def _mock_user(role: str = "admin") -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    user.email = "admin@example.com"
    user.name = "Admin"
    user.role = UserRole.admin if role == "admin" else UserRole.member
    return user


def _mock_tenant() -> MagicMock:
    tenant = MagicMock()
    tenant.id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    tenant.name = "Tenant One"
    tenant.digest_recipients = ""
    tenant.slack_webhook_url = None
    tenant.slack_digest_enabled = False
    tenant.governance_webhook_url = None
    return tenant


def _mock_run() -> MagicMock:
    run = MagicMock()
    run.id = uuid.UUID("523e4567-e89b-12d3-a456-426614174000")
    run.action = MagicMock()
    run.action.title = "Harden S3 policy"
    return run


def test_notify_remediation_run_stage_success_and_retry_summary() -> None:
    user = _mock_user(role="admin")
    tenant = _mock_tenant()
    run = _mock_run()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, run_result])
    session.commit = AsyncMock()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> MagicMock:
        return user

    class _DispatchSummary:
        delivered = 1
        replayed = 1
        skipped = 0

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with patch("backend.routers.governance.settings") as mock_settings:
            mock_settings.COMMUNICATION_GOVERNANCE_ENABLED = True
            mock_settings.FRONTEND_URL = "https://app.example.com"
            with patch("backend.routers.governance.dispatch_governance_notification", new=AsyncMock(return_value=_DispatchSummary())):
                client = TestClient(app)
                r = client.post(
                    "/api/governance/remediation-runs/523e4567-e89b-12d3-a456-426614174000/notifications",
                    headers={"Idempotency-Key": "notify-1"},
                    json={"stage": "pre_change", "detail": "Queued for approval."},
                )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["stage"] == "pre_change"
    assert data["summary"]["delivered"] == 1
    assert data["summary"]["replayed"] == 1


def test_notify_remediation_run_stage_requires_admin() -> None:
    user = _mock_user(role="member")

    async def _override_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with patch("backend.routers.governance.settings") as mock_settings:
            mock_settings.COMMUNICATION_GOVERNANCE_ENABLED = True
            client = TestClient(app)
            r = client.post(
                "/api/governance/remediation-runs/523e4567-e89b-12d3-a456-426614174000/notifications",
                headers={"Idempotency-Key": "notify-2"},
                json={"stage": "pre_change"},
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 403


def test_notify_remediation_run_stage_requires_auth() -> None:
    with patch("backend.routers.governance.settings") as mock_settings:
        mock_settings.COMMUNICATION_GOVERNANCE_ENABLED = True
        client = TestClient(app)
        r = client.post(
            "/api/governance/remediation-runs/523e4567-e89b-12d3-a456-426614174000/notifications",
            headers={"Idempotency-Key": "notify-3"},
            json={"stage": "pre_change"},
        )
    assert r.status_code == 401


def test_notify_remediation_run_stage_invalid_stage() -> None:
    user = _mock_user(role="admin")
    tenant = _mock_tenant()
    run = _mock_run()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, run_result])

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with patch("backend.routers.governance.settings") as mock_settings:
            mock_settings.COMMUNICATION_GOVERNANCE_ENABLED = True
            client = TestClient(app)
            r = client.post(
                "/api/governance/remediation-runs/523e4567-e89b-12d3-a456-426614174000/notifications",
                headers={"Idempotency-Key": "notify-4"},
                json={"stage": "bad-stage"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
