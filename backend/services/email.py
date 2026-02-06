"""
Email service for sending transactional emails.

Supports SMTP in local/dev and SES in production.
For MVP, uses a simple SMTP approach; production should use AWS SES (future).
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
    
    In local/dev mode, logs emails instead of sending (unless SMTP is configured).
    In production, should use AWS SES (future enhancement).
    """
    
    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_address = settings.EMAIL_FROM
        self.frontend_url = settings.FRONTEND_URL
    
    def _send_smtp(self, to: str, subject: str, html_body: str, text_body: str) -> bool:
        """Send email via SMTP."""
        if not self.smtp_host:
            logger.warning(f"SMTP not configured. Would send email to {to}: {subject}")
            return True  # Pretend success in dev
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_address
            msg["To"] = to
            
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
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
        if settings.is_local:
            logger.info(f"[LOCAL MODE] Invite email for {to_email}:")
            logger.info(f"  Tenant: {tenant_name}")
            logger.info(f"  Inviter: {inviter_name}")
            logger.info(f"  Accept URL: {invite_url}")
            return True
        
        return self._send_smtp(to_email, subject, html_body, text_body)

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

        if settings.is_local:
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

        if settings.is_local:
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
