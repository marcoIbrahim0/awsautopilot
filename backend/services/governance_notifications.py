"""Governance notification dispatch with tenant-scoped idempotency and channel routing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import uuid
import urllib.error
import urllib.request
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.enums import UserRole
from backend.models.governance_notification import GovernanceNotification
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.services.email import email_service
from backend.services.governance_templates import GOVERNANCE_STAGES, render_governance_template
from backend.services.slack_digest import is_valid_slack_webhook_url

logger = logging.getLogger(__name__)

CHANNEL_IN_APP = "in_app"
CHANNEL_EMAIL = "email"
CHANNEL_SLACK = "slack"
CHANNEL_WEBHOOK = "webhook"
SUPPORTED_CHANNELS = {CHANNEL_IN_APP, CHANNEL_EMAIL, CHANNEL_SLACK, CHANNEL_WEBHOOK}

STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

_SECRET_TOKENS = ("password", "secret", "token", "authorization", "access_key", "session_key", "webhook")


class GovernanceNotificationError(RuntimeError):
    """Raised when dispatch fails and caller must fail-closed."""


@dataclass
class GovernanceDispatchResult:
    delivered: int = 0
    replayed: int = 0
    skipped: int = 0


def mask_webhook_url(url: str | None) -> str:
    raw = (url or "").strip()
    if not raw:
        return "..."
    parsed = urlparse(raw)
    host = parsed.hostname or "unknown-host"
    return f"webhook://{host}/..."


def is_valid_governance_webhook_url(url: str | None) -> bool:
    raw = (url or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https":
        return False
    if parsed.username or parsed.password:
        return False
    if not parsed.hostname:
        return False
    if parsed.port not in (None, 443):
        return False
    if parsed.query or parsed.fragment:
        return False
    return True


def _safe_error_message(exc: Exception) -> str:
    text = str(exc).strip()
    return text[:300] if text else type(exc).__name__


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in _SECRET_TOKENS)


def _redact_value(value):
    if isinstance(value, dict):
        redacted = {}
        for key, inner in value.items():
            if _is_secret_key(str(key)):
                redacted[key] = "<redacted>"
            else:
                redacted[key] = _redact_value(inner)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


async def _resolve_email_recipients(db: AsyncSession, tenant: Tenant) -> list[str]:
    digest_recipients = (getattr(tenant, "digest_recipients", None) or "").strip()
    if digest_recipients:
        return [email.strip() for email in digest_recipients.split(",") if email.strip()]

    result = await db.execute(
        select(User.email).where(
            User.tenant_id == tenant.id,
            User.role == UserRole.admin,
        )
    )
    return [row[0] for row in result.all() if row and row[0]]


def _notification_key(
    *,
    target_type: str,
    target_id: uuid.UUID | None,
    stage: str,
    idempotency_key: str,
) -> str:
    target = str(target_id) if target_id else "none"
    return f"{target_type}:{target}:{stage}:{idempotency_key}"[:160]


def _resolve_channels(tenant: Tenant, requested: list[str] | None) -> list[str]:
    if requested:
        channels = [channel for channel in requested if channel in SUPPORTED_CHANNELS]
    else:
        channels = [CHANNEL_IN_APP, CHANNEL_EMAIL]
        if (getattr(tenant, "slack_webhook_url", None) or "").strip() and getattr(tenant, "slack_digest_enabled", False):
            channels.append(CHANNEL_SLACK)
        if (getattr(tenant, "governance_webhook_url", None) or "").strip():
            channels.append(CHANNEL_WEBHOOK)
    deduped: list[str] = []
    for channel in channels:
        if channel not in deduped:
            deduped.append(channel)
    return deduped


def _send_json_payload(url: str, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        if response.status // 100 != 2:
            raise RuntimeError(f"webhook_unexpected_status:{response.status}")


async def _deliver_channel(
    *,
    db: AsyncSession,
    tenant: Tenant,
    channel: str,
    template: dict,
) -> tuple[str, str | None]:
    if channel == CHANNEL_IN_APP:
        return STATUS_SENT, None

    if channel == CHANNEL_EMAIL:
        recipients = await _resolve_email_recipients(db, tenant)
        if not recipients:
            return STATUS_SKIPPED, "email_recipients_not_configured"
        sent, failed = email_service.send_governance_notification(
            tenant_name=tenant.name,
            to_emails=recipients,
            subject=template["subject"],
            text_body=template["text"],
            html_body=template["html"],
        )
        if sent > 0 and failed == 0:
            return STATUS_SENT, None
        raise GovernanceNotificationError(f"email_delivery_failed sent={sent} failed={failed}")

    if channel == CHANNEL_SLACK:
        webhook = (getattr(tenant, "slack_webhook_url", None) or "").strip()
        if not webhook or not getattr(tenant, "slack_digest_enabled", False):
            return STATUS_SKIPPED, "slack_not_configured"
        if not is_valid_slack_webhook_url(webhook):
            raise GovernanceNotificationError("slack_webhook_invalid")
        payload = {"text": template["text"]}
        _send_json_payload(webhook, payload)
        return STATUS_SENT, None

    if channel == CHANNEL_WEBHOOK:
        webhook = (getattr(tenant, "governance_webhook_url", None) or "").strip()
        if not webhook:
            return STATUS_SKIPPED, "webhook_not_configured"
        if not is_valid_governance_webhook_url(webhook):
            raise GovernanceNotificationError("governance_webhook_invalid")
        _send_json_payload(webhook, template["webhook"])
        return STATUS_SENT, None

    raise GovernanceNotificationError(f"unsupported_channel:{channel}")


async def dispatch_governance_notification(
    db: AsyncSession,
    *,
    tenant: Tenant,
    stage: str,
    target_type: str,
    target_id: uuid.UUID | None,
    target_label: str,
    detail: str | None,
    action_url: str | None,
    idempotency_key: str,
    channels: list[str] | None = None,
    escalation_context: dict | None = None,
) -> GovernanceDispatchResult:
    """Dispatch tenant-scoped stage notifications with idempotent replay safety."""
    if stage not in GOVERNANCE_STAGES:
        raise GovernanceNotificationError(f"unsupported_stage:{stage}")

    template = render_governance_template(
        stage=stage,
        tenant_name=tenant.name,
        target_label=target_label,
        detail=detail,
        action_url=action_url,
        escalation_context=escalation_context,
    )
    redacted_payload = _redact_value(template)
    result = GovernanceDispatchResult()
    now = datetime.now(timezone.utc)

    for channel in _resolve_channels(tenant, channels):
        key = _notification_key(
            target_type=target_type,
            target_id=target_id,
            stage=stage,
            idempotency_key=idempotency_key,
        )
        existing = await db.execute(
            select(GovernanceNotification).where(
                GovernanceNotification.tenant_id == tenant.id,
                GovernanceNotification.notification_key == key,
                GovernanceNotification.channel == channel,
            )
        )
        row = existing.scalar_one_or_none()
        if row and row.status in {STATUS_SENT, STATUS_SKIPPED}:
            result.replayed += 1
            continue

        if row is None:
            row = GovernanceNotification(
                tenant_id=tenant.id,
                notification_key=key,
                stage=stage,
                channel=channel,
                target_type=target_type,
                target_id=target_id,
                status=STATUS_PENDING,
                payload=redacted_payload,
            )
            db.add(row)
            await db.flush()

        try:
            status_value, skip_reason = await _deliver_channel(
                db=db,
                tenant=tenant,
                channel=channel,
                template=template,
            )
            row.status = status_value
            row.last_error = skip_reason
            row.payload = redacted_payload
            row.delivered_at = now if status_value == STATUS_SENT else None
            await db.flush()
            if status_value == STATUS_SENT:
                result.delivered += 1
            if status_value == STATUS_SKIPPED:
                result.skipped += 1
        except (GovernanceNotificationError, urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            row.status = STATUS_FAILED
            row.last_error = _safe_error_message(exc)
            row.payload = redacted_payload
            row.delivered_at = None
            await db.flush()
            if channel in {CHANNEL_WEBHOOK, CHANNEL_SLACK}:
                logger.warning(
                    "Governance notification failed tenant=%s channel=%s target=%s url=%s",
                    tenant.id,
                    channel,
                    target_type,
                    mask_webhook_url(
                        getattr(tenant, "governance_webhook_url", None)
                        if channel == CHANNEL_WEBHOOK
                        else getattr(tenant, "slack_webhook_url", None)
                    ),
                )
            raise GovernanceNotificationError(f"dispatch_failed:{channel}") from exc

    return result
