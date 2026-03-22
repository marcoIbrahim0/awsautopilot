from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.app_notification import AppNotification
from backend.models.help_case import HelpCase
from backend.models.user import User
from backend.services.email import email_service

HELP_SOURCE = "help_desk"
HELP_KIND = "help_case"


def _notification_title(case: HelpCase, event: str) -> str:
    if event == "created":
        return "Support case created"
    if event == "reply":
        return "Support case updated"
    return "Support case status changed"


async def create_help_case_notification(
    db: AsyncSession,
    *,
    recipient: User,
    case: HelpCase,
    event: str,
    message: str,
) -> AppNotification:
    item = AppNotification(
        tenant_id=recipient.tenant_id,
        actor_user_id=recipient.id,
        kind=HELP_KIND,
        source=HELP_SOURCE,
        severity="info",
        status=event,
        title=_notification_title(case, event),
        message=message,
        detail=case.subject,
        action_url=f"/help?tab=cases&case={case.id}",
        target_type="help_case",
        target_id=case.id,
    )
    db.add(item)
    await db.flush()
    return item


def send_help_case_admin_email(
    *,
    case: HelpCase,
    subject: str,
    summary: str,
) -> tuple[int, int]:
    return email_service.send_help_case_admin_email(
        subject=subject,
        summary=summary,
        case_id=str(case.id),
        case_subject=case.subject,
        help_url=f"/admin/help?case={case.id}",
    )


def send_help_case_requester_email(
    *,
    requester_email: str,
    case: HelpCase,
    subject: str,
    summary: str,
) -> bool:
    return email_service.send_help_case_requester_email(
        to_email=requester_email,
        subject=subject,
        summary=summary,
        case_id=str(case.id),
        case_subject=case.subject,
        help_url=f"/help?tab=cases&case={case.id}",
        now=datetime.now(timezone.utc),
    )
