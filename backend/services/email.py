"""
Email service for sending transactional emails.

SMTP is the current delivery path in every environment.
Local development keeps the historical log-only fallback when SMTP is absent.
Step 11.3: send_weekly_digest reuses this service and digest_content (11.2).
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from backend.config import settings
from backend.services.digest_content import (
    DEFAULT_APP_NAME,
    build_email_body_html,
    build_email_body_plain,
    build_email_subject,
    get_view_in_app_url,
)

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email service for sending transactional emails.
    
    In local mode, logs emails instead of sending when SMTP is absent.
    In non-local environments, delivery requires explicit SMTP configuration.
    """
    
    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_starttls: Optional[bool] = None,
    ):
        host = smtp_host if smtp_host is not None else settings.EMAIL_SMTP_HOST
        user = smtp_user if smtp_user is not None else settings.EMAIL_SMTP_USER
        password = smtp_password if smtp_password is not None else settings.EMAIL_SMTP_PASSWORD
        self.smtp_host = (host or "").strip() or None
        self.smtp_port = int(smtp_port if smtp_port is not None else settings.EMAIL_SMTP_PORT)
        self.smtp_user = (user or "").strip() or None
        self.smtp_password = (password or "").strip() or None
        self.smtp_starttls = bool(
            settings.EMAIL_SMTP_STARTTLS if smtp_starttls is None else smtp_starttls
        )
        self.from_address = settings.EMAIL_FROM
        self.frontend_url = settings.FRONTEND_URL

    def _log_only_local(self) -> bool:
        """
        Local mode helper.

        When running local without SMTP configured, keep historical behavior by
        logging email intent and returning success for developer workflows.
        """
        return settings.is_local and not self.smtp_host

    def _uses_placeholder_from_address(self) -> bool:
        from_address = (self.from_address or "").strip().lower()
        return from_address in {"", "noreply@example.com"}

    def can_deliver_transactional_email(self) -> bool:
        if self._log_only_local():
            return True
        return bool(self.smtp_host) and not self._uses_placeholder_from_address()
    
    def _send_smtp(self, to: str, subject: str, html_body: str, text_body: str) -> bool:
        """Send email via SMTP."""
        if not self.can_deliver_transactional_email():
            logger.error(
                "SMTP delivery is not configured. Cannot deliver email to %s: %s",
                to,
                subject,
            )
            return False
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_address
            msg["To"] = to
            
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_starttls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_address, to, msg.as_string())
            
            logger.info(f"Email sent to {to}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False
    
    def send_invite_email(
        self,
        to_email: str,
        invite_token: str,
        tenant_name: str,
        inviter_name: str,
    ) -> bool:
        """
        Send an invitation email to join a tenant.
        
        Args:
            to_email: Recipient email address
            invite_token: UUID token for the invite link
            tenant_name: Name of the tenant/company
            inviter_name: Name of the user who sent the invite
        
        Returns:
            True if email was sent successfully, False otherwise
        """
        invite_url = f"{self.frontend_url}/accept-invite?token={invite_token}"
        subject = f"You've been invited to join {tenant_name} on AWS Security Autopilot"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #070B10; color: #C7D0D8; padding: 40px; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #101720; border-radius: 12px; padding: 32px; border: 1px solid #1F2A35; }}
                h1 {{ color: #C7D0D8; font-size: 24px; margin-bottom: 16px; }}
                p {{ color: #8F9BA6; line-height: 1.6; margin-bottom: 16px; }}
                .button {{ display: inline-block; background-color: #5B87AD; color: #070B10; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 16px 0; }}
                .button:hover {{ background-color: #7FA6C6; }}
                .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #1F2A35; font-size: 12px; color: #8F9BA6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>You're invited!</h1>
                <p><strong>{inviter_name}</strong> has invited you to join <strong>{tenant_name}</strong> on AWS Security Autopilot.</p>
                <p>AWS Security Autopilot helps teams secure their AWS infrastructure by operationalizing Security Hub findings.</p>
                <a href="{invite_url}" class="button">Accept Invitation</a>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; font-size: 12px;">{invite_url}</p>
                <div class="footer">
                    <p>This invitation link will expire in 7 days. If you didn't expect this email, you can safely ignore it.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
You're invited to join {tenant_name} on AWS Security Autopilot!

{inviter_name} has invited you to join their team.

AWS Security Autopilot helps teams secure their AWS infrastructure by operationalizing Security Hub findings.

Click here to accept the invitation:
{invite_url}

This invitation link will expire in 7 days.

If you didn't expect this email, you can safely ignore it.
        """
        
        # In local mode, just log the invite URL
        if self._log_only_local():
            logger.info(f"[LOCAL MODE] Invite email for {to_email}:")
            logger.info(f"  Tenant: {tenant_name}")
            logger.info(f"  Inviter: {inviter_name}")
            logger.info(f"  Accept URL: {invite_url}")
            return True
        
        return self._send_smtp(to_email, subject, html_body, text_body)

    def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
    ) -> bool:
        """
        Send password reset email with one-time token link.
        """
        reset_url = f"{self.frontend_url}/reset-password?token={reset_token}"
        subject = "Reset your AWS Security Autopilot password"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #070B10; color: #C7D0D8; padding: 40px; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #101720; border-radius: 12px; padding: 32px; border: 1px solid #1F2A35; }}
                h1 {{ color: #C7D0D8; font-size: 24px; margin-bottom: 16px; }}
                p {{ color: #8F9BA6; line-height: 1.6; margin-bottom: 16px; }}
                .button {{ display: inline-block; background-color: #5B87AD; color: #070B10; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 16px 0; }}
                .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #1F2A35; font-size: 12px; color: #8F9BA6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Reset your password</h1>
                <p>We received a request to reset your password.</p>
                <a href="{reset_url}" class="button">Reset password</a>
                <p>If you did not request this change, you can ignore this email.</p>
                <div class="footer">
                    <p>This reset link expires in 1 hour.</p>
                </div>
            </div>
        </body>
        </html>
        """
        text_body = f"""
We received a request to reset your password.

Reset password:
{reset_url}

If you did not request this change, you can ignore this email.
This reset link expires in 1 hour.
        """.strip()

        if self._log_only_local():
            logger.info("[LOCAL MODE] Password reset email for %s", to_email)
            logger.info("  Reset URL: %s", reset_url)
            return True

        return self._send_smtp(to_email, subject, html_body, text_body)

    def _absolute_help_url(self, path_or_url: str) -> str:
        value = (path_or_url or "").strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return f"{self.frontend_url}{value}"

    def send_help_case_admin_email(
        self,
        *,
        subject: str,
        summary: str,
        case_id: str,
        case_subject: str,
        help_url: str,
    ) -> tuple[int, int]:
        recipients = sorted(settings.saas_admin_emails_list)
        if not recipients:
            return 0, 0
        url = self._absolute_help_url(help_url)
        html_body = (
            f"<p>{summary}</p><p><strong>Case:</strong> {case_subject}</p>"
            f"<p><strong>Case ID:</strong> {case_id}</p><p><a href=\"{url}\">Open support inbox</a></p>"
        )
        text_body = f"{summary}\n\nCase: {case_subject}\nCase ID: {case_id}\nOpen: {url}"
        sent = 0
        failed = 0
        for recipient in recipients:
            if self._log_only_local():
                logger.info("[LOCAL MODE] Help admin email for %s -> %s", recipient, subject)
                sent += 1
                continue
            if self._send_smtp(recipient, subject, html_body, text_body):
                sent += 1
            else:
                failed += 1
        return sent, failed

    def send_help_case_requester_email(
        self,
        *,
        to_email: str,
        subject: str,
        summary: str,
        case_id: str,
        case_subject: str,
        help_url: str,
        now: object | None = None,
    ) -> bool:
        del now
        url = self._absolute_help_url(help_url)
        html_body = (
            f"<p>{summary}</p><p><strong>Case:</strong> {case_subject}</p>"
            f"<p><strong>Case ID:</strong> {case_id}</p><p><a href=\"{url}\">Open your support case</a></p>"
        )
        text_body = f"{summary}\n\nCase: {case_subject}\nCase ID: {case_id}\nOpen: {url}"
        if self._log_only_local():
            logger.info("[LOCAL MODE] Help requester email for %s -> %s", to_email, subject)
            return True
        return self._send_smtp(to_email, subject, html_body, text_body)

    def send_verification_link_email(
        self,
        *,
        to_email: str,
        verification_link: str,
    ) -> bool:
        """
        Send an email-verification CTA link.
        """
        subject = "Verify your email - AWS Security Autopilot"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #070B10; color: #C7D0D8; padding: 40px; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #101720; border-radius: 12px; padding: 32px; border: 1px solid #1F2A35; }}
                h1 {{ color: #C7D0D8; font-size: 24px; margin-bottom: 16px; }}
                p {{ color: #8F9BA6; line-height: 1.6; margin-bottom: 16px; }}
                .button {{ display: inline-block; background-color: #5B87AD; color: #070B10; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 16px 0; }}
                .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #1F2A35; font-size: 12px; color: #8F9BA6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Verify your email</h1>
                <p>Click the button below to activate your AWS Security Autopilot account.</p>
                <a href="{verification_link}" class="button">Verify Email</a>
                <p>If the button does not work, copy and paste this link into your browser:</p>
                <p style="word-break: break-all; font-size: 12px;">{verification_link}</p>
                <div class="footer">
                    <p>If you did not create this account, you can safely ignore this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        text_body = (
            "Verify your AWS Security Autopilot email address.\n\n"
            f"Open this link to activate your account:\n{verification_link}\n\n"
            "If you did not create this account, you can safely ignore this email."
        )

        if self._log_only_local():
            logger.info("[LOCAL MODE] Verification email for %s", to_email)
            logger.info("  Verify URL: %s", verification_link)
            return True

        return self._send_smtp(to_email, subject, html_body, text_body)

    def send_security_code_email(
        self,
        *,
        to_email: str,
        code: str,
        purpose: str,
    ) -> bool:
        """
        Send a 6-digit security code for account verification or MFA.
        """
        purpose_text = purpose.strip() or "security verification"
        subject = f"Your AWS Security Autopilot {purpose_text} code"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #070B10; color: #C7D0D8; padding: 40px; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #101720; border-radius: 12px; padding: 32px; border: 1px solid #1F2A35; }}
                h1 {{ color: #C7D0D8; font-size: 24px; margin-bottom: 16px; }}
                p {{ color: #8F9BA6; line-height: 1.6; margin-bottom: 16px; }}
                .code {{ font-size: 32px; letter-spacing: 8px; font-weight: 700; color: #C7D0D8; background-color: #070B10; padding: 16px; border-radius: 8px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Security code</h1>
                <p>Use this one-time code to complete your {purpose_text} step.</p>
                <div class="code">{code}</div>
                <p>This code expires in 10 minutes.</p>
            </div>
        </body>
        </html>
        """
        text_body = (
            f"Your AWS Security Autopilot {purpose_text} code is: {code}\n\n"
            "This code expires in 10 minutes."
        )

        if self._log_only_local():
            logger.info("[LOCAL MODE] Security code email for %s", to_email)
            logger.info("  Purpose: %s", purpose_text)
            logger.info("  Code: %s", code)
            return True

        return self._send_smtp(to_email, subject, html_body, text_body)

    def send_phone_security_code(
        self,
        *,
        to_phone: str,
        code: str,
        purpose: str,
        fallback_email: str | None = None,
    ) -> bool:
        """
        Send a phone security code.

        SMS provider integration is not available yet, so this logs in all
        environments and optionally sends a fallback email for deliverability.
        """
        purpose_text = purpose.strip() or "security verification"
        logger.info("Phone security code [%s] to %s: %s", purpose_text, to_phone, code)
        if fallback_email:
            return self.send_security_code_email(
                to_email=fallback_email,
                code=code,
                purpose=f"{purpose_text} (phone {to_phone})",
            )
        return True

    def send_weekly_digest(
        self,
        tenant_name: str,
        to_emails: list[str],
        payload: dict[str, Any],
        frontend_url: Optional[str] = None,
        app_name: str = DEFAULT_APP_NAME,
    ) -> tuple[int, int]:
        """
        Send weekly digest email to each recipient (Step 11.3).

        Renders subject and body (plain + HTML) via digest_content (11.2), then
        sends one email per address. Respect DIGEST_ENABLED in config before calling.

        Args:
            tenant_name: Tenant/organization name for subject and body.
            to_emails: List of recipient email addresses (no duplicates required).
            payload: Digest payload from worker (open_action_count, top_5_actions, etc.).
            frontend_url: Base URL for "View in app" link; defaults to settings.FRONTEND_URL.
            app_name: App name for subject and footer; defaults to DEFAULT_APP_NAME.

        Returns:
            (sent_count, failed_count).
        """
        if not to_emails:
            return 0, 0

        url = (frontend_url or self.frontend_url or "").strip() or "http://localhost:3000"
        view_url = get_view_in_app_url(url)
        subject = build_email_subject(tenant_name, app_name)
        text_body = build_email_body_plain(tenant_name, payload, view_url, app_name)
        html_body = build_email_body_html(tenant_name, payload, view_url, app_name)

        if self._log_only_local():
            logger.info(
                "[LOCAL MODE] Weekly digest for %s: would send to %s recipients",
                tenant_name,
                len(to_emails),
            )
            logger.info("  Subject: %s", subject)
            logger.info("  View in app: %s", view_url)
            return len(to_emails), 0

        sent = 0
        failed = 0
        for to in to_emails:
            to = (to or "").strip()
            if not to:
                continue
            if self._send_smtp(to, subject, html_body, text_body):
                sent += 1
            else:
                failed += 1
        return sent, failed

    def send_governance_notification(
        self,
        *,
        tenant_name: str,
        to_emails: list[str],
        subject: str,
        text_body: str,
        html_body: str,
    ) -> tuple[int, int]:
        """
        Send one governance notification email body to a list of recipients.

        Idempotency and dedupe are handled by governance_notifications service.
        """
        recipients = [(email or "").strip() for email in to_emails if (email or "").strip()]
        if not recipients:
            return 0, 0

        if settings.is_local:
            logger.info(
                "[LOCAL MODE] Governance email for %s: recipients=%s subject=%s",
                tenant_name,
                len(recipients),
                (subject or "").strip()[:120],
            )
            return len(recipients), 0

        sent = 0
        failed = 0
        for recipient in recipients:
            if self._send_smtp(recipient, subject, html_body, text_body):
                sent += 1
            else:
                failed += 1
        return sent, failed

    def send_baseline_report_ready(
        self,
        to_email: str,
        tenant_name: str,
        download_url: str,
        app_name: str = DEFAULT_APP_NAME,
    ) -> bool:
        """
        Send "Your baseline security report is ready" email (Step 13.3).

        Args:
            to_email: Recipient email (e.g. requested_by user).
            tenant_name: Tenant/organization name.
            download_url: Presigned URL or app link to download the report.
            app_name: App name for subject/footer.

        Returns:
            True if sent (or logged in local), False on failure.
        """
        subject = f"Your baseline security report is ready — {app_name}"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #070B10; color: #C7D0D8; padding: 40px; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #101720; border-radius: 12px; padding: 32px; border: 1px solid #1F2A35; }}
                h1 {{ color: #C7D0D8; font-size: 24px; margin-bottom: 16px; }}
                p {{ color: #8F9BA6; line-height: 1.6; margin-bottom: 16px; }}
                .button {{ display: inline-block; background-color: #5B87AD; color: #070B10; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 16px 0; }}
                .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #1F2A35; font-size: 12px; color: #8F9BA6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Your baseline security report is ready</h1>
                <p>Hi,</p>
                <p>Your baseline security report for <strong>{tenant_name}</strong> is ready. You can download it using the link below (valid for 1 hour).</p>
                <a href="{download_url}" class="button">Download report</a>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; font-size: 12px;">{download_url}</p>
                <div class="footer">
                    <p>This report was generated by {app_name}. If you didn't request this report, you can safely ignore this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        text_body = f"""
Your baseline security report is ready.

Your baseline security report for {tenant_name} is ready.

Download your report (link valid for 1 hour):
{download_url}

This report was generated by {app_name}. If you didn't request this report, you can safely ignore this email.
        """.strip()

        if self._log_only_local():
            logger.info(
                "[LOCAL MODE] Baseline report ready email for %s (tenant: %s)",
                to_email,
                tenant_name,
            )
            logger.info("  Download URL: %s...", (download_url or "")[:80])
            return True
        return self._send_smtp(to_email, subject, html_body, text_body)


# Singleton instance
email_service = EmailService()
