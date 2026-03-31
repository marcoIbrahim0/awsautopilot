from __future__ import annotations

import uuid
from unittest.mock import patch

from backend.models.tenant_integration_setting import TenantIntegrationSetting
from backend.services.jira_admin import JiraAdminError, sync_jira_webhook, validate_jira_configuration


def _setting(*, config_json: dict | None = None, secret_json: dict | None = None) -> TenantIntegrationSetting:
    return TenantIntegrationSetting(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        provider="jira",
        enabled=True,
        outbound_enabled=True,
        inbound_enabled=True,
        auto_create=True,
        reopen_on_regression=True,
        config_json=config_json or {},
        secret_json=secret_json
        or {
            "user_email": "jira-user@example.com",
            "api_token": "token",
            "webhook_secret": "existing-secret",
        },
    )


def test_validate_jira_configuration_flags_transition_map_mismatch() -> None:
    setting = _setting(
        config_json={
            "base_url": "https://example.atlassian.net",
            "project_key": "SEC",
            "issue_type": "Task",
            "transition_map": {"resolved": "Done", "open": "To Do"},
        }
    )

    with patch(
        "backend.services.jira_admin._jira_json_request",
        side_effect=[
            {"accountId": "acct-1"},
            {"id": "10000", "name": "Security"},
            [{"name": "Task"}],
            [{"statuses": [{"name": "Done"}, {"name": "In Progress"}]}],
        ],
    ):
        snapshot = validate_jira_configuration(setting)

    assert snapshot.status == "warning"
    assert snapshot.credentials_valid is True
    assert snapshot.project_valid is True
    assert snapshot.issue_type_valid is True
    assert snapshot.transition_map_valid is False
    assert setting.config_json["health"]["transition_map_valid"] is False


def test_sync_jira_webhook_rotates_secret_and_recreates_missing_webhook() -> None:
    setting = _setting(
        config_json={
            "base_url": "https://example.atlassian.net",
            "project_key": "SEC",
            "webhook_id": "old-hook",
        },
        secret_json={
            "user_email": "jira-user@example.com",
            "api_token": "token",
            "webhook_secret": "old-secret",
        },
    )

    with patch(
        "backend.services.jira_admin._jira_json_request",
        side_effect=[
            JiraAdminError("jira_resource_not_found", "missing"),
            [],
            {"id": "new-hook", "isSigned": True},
        ],
    ):
        result = sync_jira_webhook(setting, rotate_secret=True)

    assert result.created is True
    assert result.rotated_secret is True
    assert result.webhook_id == "new-hook"
    assert result.webhook_url.endswith("/api/integrations/webhooks/jira")
    assert setting.secret_json["webhook_secret"] != "old-secret"
    assert setting.config_json["webhook_id"] == "new-hook"
    assert setting.config_json["webhook_url"].endswith("/api/integrations/webhooks/jira")
