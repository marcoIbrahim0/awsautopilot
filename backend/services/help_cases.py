from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.help_case import HelpCase
from backend.models.help_case_attachment import HelpCaseAttachment
from backend.models.help_case_message import HelpCaseMessage
from backend.models.user import User

HELP_CASE_CATEGORIES = {
    "onboarding",
    "aws_connection",
    "findings_actions",
    "exceptions",
    "remediation_pr_bundles",
    "notifications_integrations",
    "shared_files",
    "other",
}
HELP_CASE_PRIORITIES = {"low", "normal", "high", "urgent"}
HELP_CASE_STATUSES = {"new", "triaging", "waiting_on_customer", "resolved", "closed"}
HELP_CASE_SOURCES = {"manual", "ai_escalation", "contextual_cta"}
HELP_MESSAGE_ROLES = {"requester", "support", "assistant", "system"}
HELP_OVERDUE_AFTER = timedelta(hours=24)


def validate_case_category(value: str) -> str:
    normalized = (value or "other").strip().lower()
    if normalized not in HELP_CASE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid help case category")
    return normalized


def validate_case_priority(value: str | None) -> str:
    normalized = (value or "normal").strip().lower()
    if normalized not in HELP_CASE_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid help case priority")
    return normalized


def validate_case_status(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in HELP_CASE_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid help case status")
    return normalized


def validate_case_source(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in HELP_CASE_SOURCES:
        raise HTTPException(status_code=400, detail="Invalid help case source")
    return normalized


def validate_message_role(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in HELP_MESSAGE_ROLES:
        raise HTTPException(status_code=400, detail="Invalid help case message role")
    return normalized


def compute_help_case_sla_state(case: HelpCase) -> str:
    now = datetime.now(timezone.utc)
    if case.status == "waiting_on_customer":
        return "awaiting_customer"
    if case.status in {"resolved", "closed"}:
        return "resolved"
    last_message_at = case.last_message_at
    if isinstance(last_message_at, datetime) and now - last_message_at > HELP_OVERDUE_AFTER:
        return "overdue"
    return "awaiting_support"


def serialize_help_case_attachment(attachment: HelpCaseAttachment) -> dict[str, object]:
    return {
        "id": str(attachment.id),
        "message_id": str(attachment.message_id),
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
        "internal_only": bool(attachment.internal_only),
        "created_at": attachment.created_at.isoformat() if attachment.created_at else "",
        "uploaded_at": attachment.uploaded_at.isoformat() if attachment.uploaded_at else None,
    }


def serialize_help_case_message(
    message: HelpCaseMessage,
    *,
    include_internal: bool,
) -> dict[str, object] | None:
    if message.internal_only and not include_internal:
        return None
    visible_attachments = [
        serialize_help_case_attachment(item)
        for item in message.attachments
        if include_internal or not item.internal_only
    ]
    return {
        "id": str(message.id),
        "role": message.role,
        "body": message.body,
        "internal_only": bool(message.internal_only),
        "created_by_user_id": str(message.created_by_user_id) if message.created_by_user_id else None,
        "created_by_email": message.created_by.email if message.created_by else None,
        "created_at": message.created_at.isoformat() if message.created_at else "",
        "attachments": visible_attachments,
    }


def serialize_help_case(
    case: HelpCase,
    *,
    include_internal: bool,
) -> dict[str, object]:
    messages = [
        payload
        for payload in (
            serialize_help_case_message(message, include_internal=include_internal)
            for message in sorted(case.messages, key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc))
        )
        if payload is not None
    ]
    return {
        "id": str(case.id),
        "tenant_id": str(case.tenant_id),
        "requester_user_id": str(case.requester_user_id),
        "requester_email": case.requester.email if case.requester else None,
        "assigned_saas_admin_user_id": str(case.assigned_saas_admin_user_id) if case.assigned_saas_admin_user_id else None,
        "assigned_saas_admin_email": case.assignee.email if case.assignee else None,
        "subject": case.subject,
        "category": case.category,
        "priority": case.priority,
        "status": case.status,
        "source": case.source,
        "current_path": case.current_path,
        "referenced_entities": list(case.referenced_entities or []),
        "first_response_at": case.first_response_at.isoformat() if case.first_response_at else None,
        "resolved_at": case.resolved_at.isoformat() if case.resolved_at else None,
        "closed_at": case.closed_at.isoformat() if case.closed_at else None,
        "last_message_at": case.last_message_at.isoformat() if case.last_message_at else None,
        "created_at": case.created_at.isoformat() if case.created_at else "",
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        "sla_state": compute_help_case_sla_state(case),
        "messages": messages,
    }


def _case_query():
    return (
        select(HelpCase)
        .options(
            selectinload(HelpCase.requester),
            selectinload(HelpCase.assignee),
            selectinload(HelpCase.messages).selectinload(HelpCaseMessage.created_by),
            selectinload(HelpCase.messages).selectinload(HelpCaseMessage.attachments),
        )
    )


async def get_customer_case_or_404(
    db: AsyncSession,
    *,
    case_id: str,
    current_user: User,
) -> HelpCase:
    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="case_id must be a valid UUID") from exc
    result = await db.execute(
        _case_query().where(
            HelpCase.id == case_uuid,
            HelpCase.tenant_id == current_user.tenant_id,
            HelpCase.requester_user_id == current_user.id,
        )
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Help case not found")
    return case


async def get_admin_case_or_404(
    db: AsyncSession,
    *,
    case_id: str,
) -> HelpCase:
    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="case_id must be a valid UUID") from exc
    result = await db.execute(_case_query().where(HelpCase.id == case_uuid))
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Help case not found")
    return case


async def list_customer_cases(
    db: AsyncSession,
    *,
    current_user: User,
) -> list[HelpCase]:
    result = await db.execute(
        _case_query()
        .where(HelpCase.tenant_id == current_user.tenant_id, HelpCase.requester_user_id == current_user.id)
        .order_by(HelpCase.last_message_at.desc().nullslast(), HelpCase.created_at.desc())
    )
    return list(result.scalars().all())


async def list_admin_cases(
    db: AsyncSession,
    *,
    status: str | None,
    priority: str | None,
    tenant_id: str | None,
    assigned_saas_admin_user_id: str | None,
) -> list[HelpCase]:
    query = _case_query().order_by(HelpCase.last_message_at.desc().nullslast(), HelpCase.created_at.desc())
    if status:
        query = query.where(HelpCase.status == validate_case_status(status))
    if priority:
        query = query.where(HelpCase.priority == validate_case_priority(priority))
    if tenant_id:
        try:
            tenant_uuid = uuid.UUID(tenant_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="tenant_id must be a valid UUID") from exc
        query = query.where(HelpCase.tenant_id == tenant_uuid)
    if assigned_saas_admin_user_id:
        try:
            assignee_uuid = uuid.UUID(assigned_saas_admin_user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="assigned_saas_admin_user_id must be a valid UUID") from exc
        query = query.where(HelpCase.assigned_saas_admin_user_id == assignee_uuid)
    result = await db.execute(query)
    return list(result.scalars().all())


async def count_admin_cases(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(HelpCase))
    return int(result.scalar() or 0)
