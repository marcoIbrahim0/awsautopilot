from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app
from backend.models.tenant_integration_setting import TenantIntegrationSetting


def _setting() -> TenantIntegrationSetting:
    return TenantIntegrationSetting(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        provider="jira",
        enabled=True,
        outbound_enabled=True,
        inbound_enabled=True,
        auto_create=True,
        reopen_on_regression=True,
        config_json={"base_url": "https://example.atlassian.net", "project_key": "SEC"},
        secret_json={"webhook_secret": "signed-secret"},
    )


def test_jira_webhook_accepts_signed_request_without_legacy_token() -> None:
    setting = _setting()
    sync_result = SimpleNamespace(
        provider="jira",
        replayed=False,
        applied=True,
        action_id=uuid.uuid4(),
        action_status="open",
        owner_key="acct-42",
        receipt_status="processed",
    )
    session = MagicMock()
    db = MagicMock()
    db.run_sync = AsyncMock(side_effect=lambda fn: fn(session))
    db.commit = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db

    app.dependency_overrides[get_db] = mock_get_db
    try:
        with patch("backend.routers.integrations.resolve_jira_setting_for_signature", return_value=setting) as resolve:
            with patch("backend.routers.integrations.process_inbound_event", return_value=sync_result) as process:
                client = TestClient(app)
                response = client.post(
                    "/api/integrations/webhooks/jira",
                    json={"issue": {"id": "10001"}},
                    headers={"X-Hub-Signature": "sha256=test-signature"},
                )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["provider"] == "jira"
    assert response.json()["applied"] is True
    resolve.assert_called_once()
    process.assert_called_once()
    assert process.call_args.kwargs["setting"] == setting
    assert process.call_args.kwargs["webhook_token"] == ""
