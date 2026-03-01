"""Tests for weekly digest Slack webhook runtime validation."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from backend.workers.jobs import weekly_digest


class _SessionScope:
    """Minimal context manager wrapper for a fake worker DB session."""

    def __init__(self, session: MagicMock) -> None:
        self._session = session

    def __enter__(self) -> MagicMock:
        return self._session

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _mock_tenant(tenant_id: uuid.UUID, webhook_url: str, enabled: bool) -> MagicMock:
    tenant = MagicMock()
    tenant.id = tenant_id
    tenant.name = "Tenant A"
    tenant.last_digest_sent_at = None
    tenant.digest_enabled = False
    tenant.slack_webhook_url = webhook_url
    tenant.slack_digest_enabled = enabled
    return tenant


def test_execute_weekly_digest_job_clears_invalid_stored_webhook() -> None:
    """Invalid stored webhook is cleared and Slack send is skipped."""
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant(
        tenant_id,
        webhook_url="https://example.com/webhook",
        enabled=True,
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute.return_value = result
    session.flush = MagicMock()

    with patch.object(weekly_digest, "session_scope", return_value=_SessionScope(session)):
        with patch.object(
            weekly_digest,
            "build_digest_payload",
            return_value={
                "open_action_count": 0,
                "new_findings_count_7d": 0,
                "exceptions_expiring_14d_count": 0,
                "top_5_actions": [],
                "expiring_exceptions": [],
                "generated_at": "2026-03-01T00:00:00+00:00",
            },
        ):
            with patch.object(weekly_digest, "send_slack_digest") as mock_send:
                weekly_digest.execute_weekly_digest_job({"tenant_id": str(tenant_id)})

    assert tenant.slack_webhook_url is None
    assert tenant.slack_digest_enabled is False
    mock_send.assert_not_called()


def test_execute_weekly_digest_job_sends_for_valid_stored_webhook() -> None:
    """Valid stored webhook is used when Slack digest is enabled."""
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant(
        tenant_id,
        webhook_url="https://hooks.slack.com/services/T00/B00/XXX",
        enabled=True,
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute.return_value = result
    session.flush = MagicMock()

    payload = {
        "open_action_count": 0,
        "new_findings_count_7d": 0,
        "exceptions_expiring_14d_count": 0,
        "top_5_actions": [],
        "expiring_exceptions": [],
        "generated_at": "2026-03-01T00:00:00+00:00",
    }
    with patch.object(weekly_digest, "session_scope", return_value=_SessionScope(session)):
        with patch.object(weekly_digest, "build_digest_payload", return_value=payload):
            with patch.object(weekly_digest, "send_slack_digest", return_value=True) as mock_send:
                weekly_digest.execute_weekly_digest_job({"tenant_id": str(tenant_id)})

    mock_send.assert_called_once_with(
        webhook_url="https://hooks.slack.com/services/T00/B00/XXX",
        tenant_name="Tenant A",
        payload=payload,
        frontend_url=weekly_digest.settings.FRONTEND_URL,
    )
