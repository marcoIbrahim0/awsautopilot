"""
Exception service: expiry checking and exception state for API responses (Step 6.3).

Provides on-read logic so expired exceptions are reflected immediately:
- get_active_exception: returns non-expired exception for an entity (or None).
- get_exception_state_for_response: returns a dict for API responses (exception_id,
  exception_expires_at when active; exception_expired when expired; empty when none).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.enums import EntityType
from backend.models.exception import Exception


async def get_active_exception(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
) -> Exception | None:
    """
    Return the active (non-expired) exception for an entity, or None.

    Used when you only care about "is this entity currently suppressed?"
    """
    now = datetime.now(timezone.utc)
    entity_type_enum = EntityType(entity_type) if isinstance(entity_type, str) else entity_type
    result = await db.execute(
        select(Exception).where(
            Exception.tenant_id == tenant_id,
            Exception.entity_type == entity_type_enum,
            Exception.entity_id == entity_id,
            Exception.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def get_exception_for_entity(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
) -> Exception | None:
    """
    Return any exception for an entity (active or expired), or None.

    Used to build API response state (active vs expired).
    """
    entity_type_enum = EntityType(entity_type) if isinstance(entity_type, str) else entity_type
    result = await db.execute(
        select(Exception).where(
            Exception.tenant_id == tenant_id,
            Exception.entity_type == entity_type_enum,
            Exception.entity_id == entity_id,
        )
    )
    return result.scalar_one_or_none()


async def get_exception_state_for_response(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Return exception state for API response (on-read expiry logic).

    - No exception: {}.
    - Active exception (expires_at > now): {"exception_id": str, "exception_expires_at": str}.
    - Expired exception: {"exception_expired": True}.

    Use in actions and findings APIs so the UI can show "Suppressed until <date>"
    or "Exception expired" without a background job.
    """
    states = await get_exception_states_for_entities(
        db,
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_ids=[entity_id],
    )
    return states.get(entity_id, {})


def _exception_to_state(exc: Exception, now: datetime) -> dict[str, Any]:
    if exc.expires_at > now:
        return {
            "exception_id": str(exc.id),
            "exception_expires_at": exc.expires_at.isoformat(),
        }
    return {"exception_expired": True}


async def get_exception_states_for_entities(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    entity_type: str,
    entity_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict[str, Any]]:
    """
    Batch version of get_exception_state_for_response.

    Returns a map keyed by entity_id for entities that have an exception row.
    Entities with no exception are omitted from the result map.
    """
    if not entity_ids:
        return {}

    entity_type_enum = EntityType(entity_type) if isinstance(entity_type, str) else entity_type
    result = await db.execute(
        select(Exception).where(
            Exception.tenant_id == tenant_id,
            Exception.entity_type == entity_type_enum,
            Exception.entity_id.in_(entity_ids),
        )
    )
    exceptions = result.scalars().all()

    now = datetime.now(timezone.utc)
    return {exc.entity_id: _exception_to_state(exc, now) for exc in exceptions}
