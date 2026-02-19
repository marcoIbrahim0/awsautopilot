"""
Weekly digest job handler (Step 11.1 + 11.3).

Picks up weekly_digest jobs from SQS, checks idempotency (last_digest_sent_at within 7 days),
builds digest payload (open actions, new findings last 7d, exceptions expiring next 14d, top 5 actions),
updates last_digest_sent_at, and sends digest email (11.3) when enabled.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.models.action import Action
from backend.models.enums import ActionStatus, EntityType, UserRole
from backend.models.exception import Exception as ExceptionModel
from backend.models.finding import Finding
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.services.email import email_service
from backend.services.slack_digest import send_slack_digest
from backend.workers.database import session_scope

logger = logging.getLogger("worker.jobs.weekly_digest")

# Contract: job dict must have job_type, tenant_id, created_at
WEEKLY_DIGEST_REQUIRED_FIELDS = {"job_type", "tenant_id", "created_at"}

# Idempotency: do not run digest again if last sent within this many days
DIGEST_COOLDOWN_DAYS = 7


def _get_digest_recipients(tenant: Tenant, session) -> list[str]:
    """
    Resolve digest recipients for a tenant (Step 11.3 preferences).

    If tenant.digest_recipients is set (comma-separated emails), use that;
    otherwise return emails of all tenant users with role admin.
    """
    if getattr(tenant, "digest_recipients", None) and (tenant.digest_recipients or "").strip():
        return [e.strip() for e in tenant.digest_recipients.split(",") if e.strip()]
    result = session.execute(
        select(User.email).where(
            User.tenant_id == tenant.id,
            User.role == UserRole.admin,
        )
    )
    return [row[0] for row in result.all() if row[0]]


def build_digest_payload(session, tenant_id: uuid.UUID) -> dict:
    """
    Build digest payload for a tenant: counts and top 5 actions.
    Used by execute_weekly_digest_job; payload will be used by 11.3 (email) and 11.4 (Slack).
    """
    now = datetime.now(timezone.utc)
    since_7d = now - timedelta(days=7)
    until_14d = now + timedelta(days=14)

    # Open action count
    open_count_result = session.execute(
        select(func.count(Action.id)).where(
            Action.tenant_id == tenant_id,
            Action.status == ActionStatus.open.value,
        )
    )
    open_action_count = open_count_result.scalar() or 0

    # New/updated findings in last 7 days
    new_findings_result = session.execute(
        select(func.count(Finding.id)).where(
            Finding.tenant_id == tenant_id,
            Finding.updated_at >= since_7d,
        )
    )
    new_findings_count_7d = new_findings_result.scalar() or 0

    # Exceptions expiring in next 14 days
    expiring_result = session.execute(
        select(func.count(ExceptionModel.id)).where(
            ExceptionModel.tenant_id == tenant_id,
            ExceptionModel.expires_at >= now,
            ExceptionModel.expires_at <= until_14d,
        )
    )
    exceptions_expiring_14d_count = expiring_result.scalar() or 0

    # Top 5 open actions by priority
    top_actions_result = session.execute(
        select(Action)
        .where(
            Action.tenant_id == tenant_id,
            Action.status == ActionStatus.open.value,
        )
        .order_by(Action.priority.desc())
        .limit(5)
        .options(selectinload(Action.action_finding_links))
    )
    top_actions_rows = top_actions_result.scalars().all()
    top_5_actions = [
        {
            "id": str(a.id),
            "title": a.title,
            "priority": a.priority,
            "action_type": a.action_type,
        }
        for a in top_actions_rows
    ]

    # Exceptions expiring in next 14 days (list for 11.2 content: entity, expiry, link)
    expiring_exceptions_result = session.execute(
        select(ExceptionModel)
        .where(
            ExceptionModel.tenant_id == tenant_id,
            ExceptionModel.expires_at >= now,
            ExceptionModel.expires_at <= until_14d,
        )
        .order_by(ExceptionModel.expires_at.asc())
        .limit(10)
    )
    expiring_exception_rows = expiring_exceptions_result.scalars().all()
    expiring_exceptions = []
    for exc in expiring_exception_rows:
        expires_at_iso = exc.expires_at.isoformat() if exc.expires_at else ""
        if exc.entity_type == EntityType.action:
            action_row = session.execute(
                select(Action).where(Action.id == exc.entity_id, Action.tenant_id == tenant_id)
            ).scalar_one_or_none()
            label = action_row.title if action_row else f"Action {exc.entity_id}"
        else:
            reason = (exc.reason or "").strip()[:60]
            label = f"Finding: {reason}" if reason else "Finding exception"
        expiring_exceptions.append({
            "entity_type": exc.entity_type.value,
            "entity_id": str(exc.entity_id),
            "expires_at_iso": expires_at_iso,
            "label": label,
        })

    return {
        "open_action_count": open_action_count,
        "new_findings_count_7d": new_findings_count_7d,
        "exceptions_expiring_14d_count": exceptions_expiring_14d_count,
        "top_5_actions": top_5_actions,
        "expiring_exceptions": expiring_exceptions,
        "generated_at": now.isoformat(),
    }


def execute_weekly_digest_job(job: dict) -> None:
    """
    Process a weekly_digest job: idempotency check, build payload, update last_digest_sent_at.

    Idempotent: skips if last_digest_sent_at is within the last DIGEST_COOLDOWN_DAYS.
    Actual sending (email/Slack) is implemented in Step 11.3/11.4.
    """
    tenant_id_str = job.get("tenant_id")
    if not tenant_id_str:
        raise ValueError("job missing tenant_id")

    try:
        tenant_uuid = uuid.UUID(tenant_id_str)
    except (TypeError, ValueError) as e:
        raise ValueError(f"invalid tenant_id: {e}") from e

    with session_scope() as session:
        tenant = session.execute(
            select(Tenant).where(Tenant.id == tenant_uuid)
        ).scalar_one_or_none()
        if not tenant:
            raise ValueError(f"tenant not found: tenant_id={tenant_id_str}")

        now = datetime.now(timezone.utc)
        last_sent = getattr(tenant, "last_digest_sent_at", None)
        if last_sent:
            last_sent_utc = last_sent if last_sent.tzinfo else last_sent.replace(tzinfo=timezone.utc)
            if (now - last_sent_utc).days < DIGEST_COOLDOWN_DAYS:
                logger.info(
                    "weekly_digest idempotent skip tenant_id=%s last_sent=%s",
                    tenant_id_str,
                    last_sent_utc.isoformat(),
                )
                return

        payload = build_digest_payload(session, tenant_uuid)
        tenant.last_digest_sent_at = now
        session.flush()

        logger.info(
            "weekly_digest built tenant_id=%s open=%s new_findings_7d=%s expiring_14d=%s",
            tenant_id_str,
            payload["open_action_count"],
            payload["new_findings_count_7d"],
            payload["exceptions_expiring_14d_count"],
        )

        # Step 11.3: send digest email when enabled (config + tenant preference)
        if getattr(settings, "DIGEST_ENABLED", True) and getattr(tenant, "digest_enabled", True):
            to_emails = _get_digest_recipients(tenant, session)
            if to_emails:
                tenant_name = getattr(tenant, "name", "") or "Your organization"
                sent, failed = email_service.send_weekly_digest(
                    tenant_name=tenant_name,
                    to_emails=to_emails,
                    payload=payload,
                    frontend_url=getattr(settings, "FRONTEND_URL", None),
                )
                logger.info(
                    "weekly_digest email tenant_id=%s sent=%s failed=%s",
                    tenant_id_str,
                    sent,
                    failed,
                )
            else:
                logger.info(
                    "weekly_digest email skipped tenant_id=%s (no recipients)",
                    tenant_id_str,
                )
        else:
            logger.info(
                "weekly_digest email skipped tenant_id=%s (digest disabled)",
                tenant_id_str,
            )

        # Step 11.4: send digest to Slack when webhook configured and enabled
        webhook_url = getattr(tenant, "slack_webhook_url", None) or ""
        slack_enabled = getattr(tenant, "slack_digest_enabled", False)
        if webhook_url.strip() and slack_enabled:
            tenant_name = getattr(tenant, "name", "") or "Your organization"
            ok = send_slack_digest(
                webhook_url=webhook_url.strip(),
                tenant_name=tenant_name,
                payload=payload,
                frontend_url=getattr(settings, "FRONTEND_URL", None),
            )
            logger.info(
                "weekly_digest slack tenant_id=%s sent=%s",
                tenant_id_str,
                ok,
            )
        elif webhook_url.strip() and not slack_enabled:
            logger.info(
                "weekly_digest slack skipped tenant_id=%s (Slack digest disabled)",
                tenant_id_str,
            )
