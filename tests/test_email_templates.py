from __future__ import annotations

from unittest.mock import PropertyMock, patch

from backend.config import settings
from backend.services.email import EmailService


def _service() -> EmailService:
    service = EmailService(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password="pass",
    )
    service.frontend_url = "https://app.example.com"
    service.from_address = "noreply@example.com"
    return service


def test_send_invite_email_uses_branded_template() -> None:
    service = _service()
    with patch.object(service, "_send_smtp", return_value=True) as mock_send:
        delivered = service.send_invite_email(
            to_email="user@example.com",
            invite_token="invite-token",
            tenant_name="Acme Corp",
            inviter_name="Marco",
        )
    assert delivered is True
    _, subject, html_body, text_body = mock_send.call_args[0]
    assert "invited to join Acme Corp" in subject
    assert "Accept invitation" in html_body
    assert "Direct link" in html_body
    assert "https://app.example.com/accept-invite?token=invite-token" in html_body
    assert "Marco invited you to join Acme Corp" in text_body


def test_send_security_code_email_renders_code_block() -> None:
    service = _service()
    with patch.object(service, "_send_smtp", return_value=True) as mock_send:
        delivered = service.send_security_code_email(
            to_email="user@example.com",
            code="123456",
            purpose="MFA verification",
        )
    assert delivered is True
    _, subject, html_body, text_body = mock_send.call_args[0]
    assert "MFA verification code" in subject
    assert "One-time code" in html_body
    assert "123456" in html_body
    assert "This code expires in 10 minutes." in text_body


def test_send_password_reset_email_uses_shared_layout() -> None:
    service = _service()
    with patch.object(service, "_send_smtp", return_value=True) as mock_send:
        delivered = service.send_password_reset_email(
            to_email="user@example.com",
            reset_token="reset-token",
        )
    assert delivered is True
    _, subject, html_body, text_body = mock_send.call_args[0]
    assert "Reset your AWS Security Autopilot password" == subject
    assert "Reset password" in html_body
    assert "https://app.example.com/reset-password?token=reset-token" in html_body
    assert "This reset link expires in 1 hour." in text_body


def test_send_verification_link_email_uses_shared_layout() -> None:
    service = _service()
    with patch.object(service, "_send_smtp", return_value=True) as mock_send:
        delivered = service.send_verification_link_email(
            to_email="user@example.com",
            verification_link="https://verify.example.com/token",
        )
    assert delivered is True
    _, subject, html_body, text_body = mock_send.call_args[0]
    assert "Verify your email" in subject
    assert "Verify email" in html_body
    assert "https://verify.example.com/token" in html_body
    assert "Confirm your email address" in text_body


def test_send_help_case_requester_email_uses_shared_layout() -> None:
    service = _service()
    with patch.object(service, "_send_smtp", return_value=True) as mock_send:
        delivered = service.send_help_case_requester_email(
            to_email="user@example.com",
            subject="Support replied to your help case",
            summary="A support response is available for your case.",
            case_id="case-123",
            case_subject="Export problem",
            help_url="/help?tab=cases&case=case-123",
        )
    assert delivered is True
    _, subject, html_body, text_body = mock_send.call_args[0]
    assert "Support replied to your help case" == subject
    assert "Case details" in html_body
    assert "Open your support case" in html_body
    assert "https://app.example.com/help?tab=cases&amp;case=case-123" in html_body
    assert "Case ID: case-123" in text_body


def test_send_help_case_admin_email_uses_shared_layout() -> None:
    service = _service()
    with patch.object(type(settings), "saas_admin_emails_list", new_callable=PropertyMock) as mock_recipients:
        mock_recipients.return_value = ["admin@example.com"]
        with patch.object(service, "_send_smtp", return_value=True) as mock_send:
            sent, failed = service.send_help_case_admin_email(
                subject="New help case created",
                summary="user@example.com created a help case from /actions/123.",
                case_id="case-123",
                case_subject="Export issue",
                help_url="/admin/help?case=case-123",
            )
    assert sent == 1
    assert failed == 0
    _, subject, html_body, text_body = mock_send.call_args[0]
    assert subject == "New help case created"
    assert "Open support inbox" in html_body
    assert "Case ID: case-123" in text_body


def test_send_baseline_report_ready_uses_shared_layout() -> None:
    service = _service()
    with patch.object(service, "_send_smtp", return_value=True) as mock_send:
        delivered = service.send_baseline_report_ready(
            to_email="user@example.com",
            tenant_name="Acme Corp",
            download_url="https://downloads.example.com/report.pdf",
        )
    assert delivered is True
    _, subject, html_body, text_body = mock_send.call_args[0]
    assert "baseline security report is ready" in subject
    assert "Download report" in html_body
    assert "https://downloads.example.com/report.pdf" in html_body
    assert "This report was generated by AWS Security Autopilot." in text_body
