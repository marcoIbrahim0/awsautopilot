"""Tenant audit-log API (Wave 8 Test 32)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models.audit_log import AuditLog
from backend.models.user import User

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


class AuditLogRecordResponse(BaseModel):
    id: str
    tenant_id: str
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str
    timestamp: str | None
    created_at: str | None
    payload: dict[str, Any] | None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRecordResponse]
    total: int
    limit: int
    offset: int


def _role_value(user: User) -> str:
    role = getattr(user.role, "value", user.role)
    return role if isinstance(role, str) else str(role)


def _ensure_admin(user: User) -> None:
    if _role_value(user) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant admins can view audit logs.",
        )


def _iso_or_none(value: object) -> str | None:
    if value is None:
        return None
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        return str(iso())
    return str(value)


def _parse_iso_datetime(raw: str, field_name: str) -> datetime:
    text = (raw or "").strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be a valid ISO-8601 datetime",
        ) from exc


@router.get("", response_model=AuditLogListResponse)
async def list_audit_log(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    actor_user_id: Annotated[str | None, Query()] = None,
    resource_type: Annotated[str | None, Query()] = None,
    resource_id: Annotated[str | None, Query()] = None,
    from_date: Annotated[str | None, Query()] = None,
    to_date: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditLogListResponse:
    _ensure_admin(current_user)

    filters = [AuditLog.tenant_id == current_user.tenant_id]
    if actor_user_id:
        try:
            actor_uuid = uuid.UUID(actor_user_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="actor_user_id must be a valid UUID",
            ) from exc
        filters.append(AuditLog.user_id == actor_uuid)
    if resource_type:
        filters.append(AuditLog.entity_type == resource_type.strip())
    if resource_id:
        try:
            entity_uuid = uuid.UUID(resource_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="resource_id must be a valid UUID",
            ) from exc
        filters.append(AuditLog.entity_id == entity_uuid)
    if from_date:
        filters.append(AuditLog.timestamp >= _parse_iso_datetime(from_date, "from_date"))
    if to_date:
        filters.append(AuditLog.timestamp <= _parse_iso_datetime(to_date, "to_date"))

    count_stmt = select(func.count()).select_from(AuditLog).where(*filters)
    total = int((await db.execute(count_stmt)).scalar_one() or 0)

    stmt = (
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        AuditLogRecordResponse(
            id=str(row.id),
            tenant_id=str(row.tenant_id),
            actor_user_id=str(row.user_id) if row.user_id else None,
            action=row.event_type,
            resource_type=row.entity_type,
            resource_id=str(row.entity_id),
            timestamp=_iso_or_none(row.timestamp),
            created_at=_iso_or_none(row.timestamp),
            payload=None,
        )
        for row in rows
    ]
    return AuditLogListResponse(items=items, total=total, limit=limit, offset=offset)
