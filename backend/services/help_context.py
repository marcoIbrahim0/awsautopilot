from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.action import Action
from backend.models.aws_account import AwsAccount
from backend.models.finding import Finding
from backend.models.tenant import Tenant
from backend.models.user import User

_TOP_RISK_CRITICAL_WEIGHT = 10
_TOP_RISK_HIGH_WEIGHT = 4


def _entity_ref(entity_type: str, entity_id: str, label: str) -> dict[str, str]:
    return {"type": entity_type, "id": entity_id, "label": label}


_IAM_RESOURCE_TYPES = {
    "AwsAccount",
    "AwsIamAccessKey",
    "AwsIamGroup",
    "AwsIamInstanceProfile",
    "AwsIamPolicy",
    "AwsIamRole",
    "AwsIamUser",
}
_MAX_SECURITY_REFERENCES = 3


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
        "ai_live_lookup_enabled": bool(getattr(account, "ai_live_lookup_enabled", False)),
        "ai_live_lookup_scope": getattr(account, "ai_live_lookup_scope", None),
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


def _is_iam_action_filter() -> object:
    return or_(
        Action.control_id.ilike("IAM.%"),
        Action.action_type.ilike("iam%"),
        Action.resource_type.in_(tuple(_IAM_RESOURCE_TYPES)),
        Action.resource_id.ilike("%:iam::%"),
    )


def _is_iam_finding_filter() -> object:
    return or_(
        Finding.control_id.ilike("IAM.%"),
        Finding.canonical_control_id.ilike("IAM.%"),
        Finding.resource_type.in_(tuple(_IAM_RESOURCE_TYPES)),
        Finding.resource_id.ilike("%:iam::%"),
        Finding.title.ilike("%IAM%"),
    )


def _top_risk_score(*, critical_count: int, high_count: int) -> int:
    raw = (critical_count * _TOP_RISK_CRITICAL_WEIGHT) + (high_count * _TOP_RISK_HIGH_WEIGHT)
    return min(100, raw)


async def _platform_security_summary(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_id: str | None,
) -> dict[str, object]:
    finding_query = select(Finding).where(Finding.tenant_id == tenant_id)
    if account_id:
        finding_query = finding_query.where(Finding.account_id == account_id)
    finding_query = finding_query.where(Finding.status.in_(["NEW", "NOTIFIED"]))
    critical_query = finding_query.where(Finding.severity_label == "CRITICAL")
    high_query = finding_query.where(Finding.severity_label == "HIGH")
    critical_count = int((await db.execute(select(func.count()).select_from(critical_query.subquery()))).scalar() or 0)
    high_count = int((await db.execute(select(func.count()).select_from(high_query.subquery()))).scalar() or 0)
    result = await db.execute(
        finding_query.where(Finding.severity_label.in_(["CRITICAL", "HIGH"]))
        .order_by(Finding.severity_normalized.desc(), Finding.sh_updated_at.desc().nullslast())
        .limit(_MAX_SECURITY_REFERENCES)
    )
    findings = list(result.scalars().all())
    return {
        "account_id": account_id,
        "actionable_risk_score": _top_risk_score(critical_count=critical_count, high_count=high_count),
        "critical_open_findings": critical_count,
        "high_open_findings": high_count,
        "score_basis": "Top Risks formula: min(100, critical * 10 + high * 4).",
        "visible_findings": [
            {
                "id": str(finding.id),
                "title": finding.title,
                "status": finding.status,
                "severity_label": finding.severity_label,
                "control_id": finding.control_id,
                "resource_id": finding.resource_id,
                "resource_type": finding.resource_type,
            }
            for finding in findings
        ],
        "references": [
            _entity_ref("finding", str(finding.id), finding.title) for finding in findings
        ],
    }


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
    action_ctx, action_refs = await _action_context(db, tenant_id=current_user.tenant_id, action_id=action_id)
    finding_ctx, finding_refs = await _finding_context(db, tenant_id=current_user.tenant_id, finding_id=finding_id)
    resolved_account_id = account_id or (action_ctx or {}).get("account_id") or (finding_ctx or {}).get("account_id")
    account_ctx, account_refs = await _account_context(db, tenant_id=current_user.tenant_id, account_id=resolved_account_id)
    refs = [*account_refs, *action_refs, *finding_refs]
    settings_summary = {
        "digest_enabled": bool(getattr(tenant, "digest_enabled", False)),
        "slack_digest_enabled": bool(getattr(tenant, "slack_digest_enabled", False)),
        "governance_notifications_enabled": bool(getattr(tenant, "governance_notifications_enabled", False)),
    }
    platform_summary = await _platform_security_summary(
        db,
        tenant_id=current_user.tenant_id,
        account_id=resolved_account_id,
    )
    refs.extend(list(platform_summary.get("references") or []))
    return {
        "current_path": current_path,
        "resolved_account_id": resolved_account_id,
        "account": account_ctx,
        "action": action_ctx,
        "finding": finding_ctx,
        "tenant_settings": settings_summary,
        "referenced_entities": refs,
        "platform_summary": platform_summary,
    }
