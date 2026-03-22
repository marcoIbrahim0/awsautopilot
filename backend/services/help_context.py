from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.action import Action
from backend.models.aws_account import AwsAccount
from backend.models.finding import Finding
from backend.models.tenant import Tenant
from backend.models.user import User


def _entity_ref(entity_type: str, entity_id: str, label: str) -> dict[str, str]:
    return {"type": entity_type, "id": entity_id, "label": label}


async def _account_context(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_id: str | None,
) -> tuple[dict[str, object] | None, list[dict[str, str]]]:
    if not account_id:
        return None, []
    result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_id,
            AwsAccount.account_id == account_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        return None, []
    payload = {
        "account_id": account.account_id,
        "status": account.status,
        "regions": list(account.regions or []),
        "last_validated_at": account.last_validated_at.isoformat() if account.last_validated_at else None,
    }
    return payload, [_entity_ref("aws_account", account.account_id, f"AWS account {account.account_id}")]


async def _action_context(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action_id: str | None,
) -> tuple[dict[str, object] | None, list[dict[str, str]]]:
    if not action_id:
        return None, []
    try:
        action_uuid = uuid.UUID(action_id)
    except ValueError:
        return None, []
    result = await db.execute(select(Action).where(Action.id == action_uuid, Action.tenant_id == tenant_id))
    action = result.scalar_one_or_none()
    if action is None:
        return None, []
    payload = {
        "id": str(action.id),
        "title": action.title,
        "status": action.status,
        "priority": int(action.priority or 0),
        "account_id": action.account_id,
        "region": action.region,
        "control_id": action.control_id,
    }
    return payload, [_entity_ref("action", str(action.id), action.title)]


async def _finding_context(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    finding_id: str | None,
) -> tuple[dict[str, object] | None, list[dict[str, str]]]:
    if not finding_id:
        return None, []
    try:
        finding_uuid = uuid.UUID(finding_id)
    except ValueError:
        return None, []
    result = await db.execute(select(Finding).where(Finding.id == finding_uuid, Finding.tenant_id == tenant_id))
    finding = result.scalar_one_or_none()
    if finding is None:
        return None, []
    payload = {
        "id": str(finding.id),
        "title": finding.title,
        "status": finding.status,
        "severity_label": finding.severity_label,
        "account_id": finding.account_id,
        "region": finding.region,
        "control_id": finding.control_id,
    }
    return payload, [_entity_ref("finding", str(finding.id), finding.title)]


async def build_help_context(
    db: AsyncSession,
    *,
    current_user: User,
    current_path: str | None,
    account_id: str | None,
    action_id: str | None,
    finding_id: str | None,
) -> dict[str, object]:
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = tenant_result.scalar_one()
    account_ctx, account_refs = await _account_context(db, tenant_id=current_user.tenant_id, account_id=account_id)
    action_ctx, action_refs = await _action_context(db, tenant_id=current_user.tenant_id, action_id=action_id)
    finding_ctx, finding_refs = await _finding_context(db, tenant_id=current_user.tenant_id, finding_id=finding_id)
    refs = [*account_refs, *action_refs, *finding_refs]
    settings_summary = {
        "digest_enabled": bool(getattr(tenant, "digest_enabled", False)),
        "slack_digest_enabled": bool(getattr(tenant, "slack_digest_enabled", False)),
        "governance_notifications_enabled": bool(getattr(tenant, "governance_notifications_enabled", False)),
    }
    return {
        "current_path": current_path,
        "account": account_ctx,
        "action": action_ctx,
        "finding": finding_ctx,
        "tenant_settings": settings_summary,
        "referenced_entities": refs,
    }
