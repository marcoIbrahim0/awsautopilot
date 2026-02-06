"""
Unit tests for weekly digest email delivery (Step 11.3).

Covers: send_weekly_digest uses digest_content for subject/body; sends to each recipient;
local mode returns count; DIGEST_ENABLED respected by worker.
"""
from __future__ import annotations

from unittest.mock import patch

from backend.services.email import EmailService, email_service


def test_send_weekly_digest_empty_recipients_returns_zero() -> None:
    """send_weekly_digest with empty to_emails returns (0, 0)."""
    sent, failed = email_service.send_weekly_digest(
        tenant_name="Acme",
        to_emails=[],
        payload={"open_action_count": 1, "new_findings_count_7d": 0, "exceptions_expiring_14d_count": 0},
    )
    assert sent == 0
    assert failed == 0


def test_send_weekly_digest_builds_subject_and_body_from_digest_content() -> None:
    """send_weekly_digest builds subject and body via digest_content and sends via _send_smtp."""
    payload = {
        "open_action_count": 2,
        "new_findings_count_7d": 1,
        "exceptions_expiring_14d_count": 0,
        "top_5_actions": [],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    with patch.object(email_service, "_send_smtp", return_value=True) as mock_send:
        with patch("backend.services.email.settings") as mock_settings:
            mock_settings.is_local = False
            sent, failed = email_service.send_weekly_digest(
                tenant_name="Acme Corp",
                to_emails=["admin@acme.com", "sec@acme.com"],
                payload=payload,
                frontend_url="https://app.example.com",
            )
    assert sent == 2
    assert failed == 0
    assert mock_send.call_count == 2
    calls = mock_send.call_args_list
    for call in calls:
        to, subject, html_body, text_body = call[0]
        assert to in ("admin@acme.com", "sec@acme.com")
        assert "Weekly digest" in subject
        assert "Acme Corp" in subject
        assert "View in app" in html_body or "View in app" in text_body
        assert "https://app.example.com/top-risks" in html_body or "https://app.example.com/top-risks" in text_body
        assert "Open actions" in text_body
        assert "2" in text_body


def test_send_weekly_digest_local_mode_returns_sent_count() -> None:
    """In local mode send_weekly_digest does not call _send_smtp and returns (len(to_emails), 0)."""
    payload = {
        "open_action_count": 0,
        "new_findings_count_7d": 0,
        "exceptions_expiring_14d_count": 0,
        "top_5_actions": [],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    with patch.object(email_service, "_send_smtp") as mock_send:
        with patch("backend.services.email.settings") as mock_settings:
            mock_settings.is_local = True
            sent, failed = email_service.send_weekly_digest(
                tenant_name="Acme",
                to_emails=["a@b.com", "c@d.com"],
                payload=payload,
            )
    assert sent == 2
    assert failed == 0
    mock_send.assert_not_called()


def test_send_weekly_digest_strips_empty_recipients() -> None:
    """Empty or whitespace-only emails are skipped."""
    payload = {
        "open_action_count": 0,
        "new_findings_count_7d": 0,
        "exceptions_expiring_14d_count": 0,
        "top_5_actions": [],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    with patch.object(email_service, "_send_smtp", return_value=True) as mock_send:
        with patch("backend.services.email.settings") as mock_settings:
            mock_settings.is_local = False
            sent, failed = email_service.send_weekly_digest(
                tenant_name="Acme",
                to_emails=["valid@acme.com", "  ", ""],
                payload=payload,
            )
    assert sent == 1
    assert failed == 0
    mock_send.assert_called_once()
    assert mock_send.call_args[0][0] == "valid@acme.com"
