"""Helpers for canonical tenant ExternalId usage and mirror-field audits."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.models.aws_account import AwsAccount
from backend.models.tenant import Tenant

logger = logging.getLogger(__name__)


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def canonical_tenant_external_id(session: Session, tenant_id: uuid.UUID) -> str | None:
    """Return the tenant-scoped ExternalId used for all AssumeRole calls."""
    value = session.execute(
        select(Tenant.external_id).where(Tenant.id == tenant_id)
    ).scalar_one_or_none()
    return _clean_text(value)


async def canonical_tenant_external_id_async(db: AsyncSession, tenant_id: uuid.UUID) -> str | None:
    """Async variant of canonical_tenant_external_id()."""
    value = (
        await db.execute(select(Tenant.external_id).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    return _clean_text(value)


def account_assume_role_external_id(
    account: AwsAccount | Any,
    *,
    tenant_external_id: str | None = None,
) -> str | None:
    """
    Resolve the canonical ExternalId for an account-scoped AssumeRole call.

    Preference order:
    1. explicit tenant_external_id passed by caller
    2. loaded account.tenant.external_id relationship
    3. mirrored account.external_id compatibility copy
    """
    explicit = _clean_text(tenant_external_id)
    if explicit is not None:
        return explicit
    tenant = getattr(account, "tenant", None)
    tenant_value = _clean_text(getattr(tenant, "external_id", None))
    if tenant_value is not None:
        return tenant_value
    return _clean_text(getattr(account, "external_id", None))


def count_external_id_mismatches(session: Session) -> int:
    """Count account rows whose mirrored external_id no longer matches their tenant."""
    result = session.execute(
        select(func.count(AwsAccount.id))
        .select_from(AwsAccount)
        .join(Tenant, Tenant.id == AwsAccount.tenant_id)
        .where(AwsAccount.external_id != Tenant.external_id)
    )
    return int(result.scalar_one() or 0)


def sync_account_external_id_mirror(session: Session) -> int:
    """Rewrite mirrored aws_accounts.external_id values to match tenants.external_id."""
    result = session.execute(
        update(AwsAccount)
        .where(
            AwsAccount.tenant_id == Tenant.id,
            AwsAccount.external_id != Tenant.external_id,
        )
        .values(external_id=Tenant.external_id)
    )
    return int(result.rowcount or 0)


async def log_external_id_mismatch_audit_async(db: AsyncSession) -> int:
    """Log the current mismatch count during startup or operator health checks."""
    count = await db.run_sync(count_external_id_mismatches)
    if count:
        logger.warning("account_external_id_mismatch_detected count=%s", count)
    else:
        logger.info("account_external_id_mismatch_detected count=0")
    return count
