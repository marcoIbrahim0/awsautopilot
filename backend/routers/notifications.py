from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models.user import User
from backend.services.notification_center import (
    apply_state_action,
    fetch_notification_rows,
    serialize_notification,
    upsert_job_notification,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])
STATE_ACTIONS = {"read", "unread", "archive", "mark_all_read"}


class NotificationItemResponse(BaseModel):
    id: str
    kind: str
    source: str
    severity: str
    status: str
    title: str
    message: str
    detail: str | None
    progress: int | None
    action_url: str | None
    target_type: str | None
    target_id: str | None
    client_key: str | None = None
    created_at: str
    updated_at: str | None
    read_at: str | None
    archived_at: str | None


class NotificationListResponse(BaseModel):
    items: list[NotificationItemResponse]
    total: int
    unread_total: int


class NotificationJobUpsertRequest(BaseModel):
    status: str = Field(..., description="queued|running|partial|success|error|timed_out|canceled")
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    severity: str | None = Field(default=None)
    detail: str | None = Field(default=None)
    progress: int | None = Field(default=None, ge=0, le=100)
    action_url: str | None = Field(default=None)
    target_type: str | None = Field(default=None)
    target_id: str | None = Field(default=None)


class NotificationStateRequest(BaseModel):
    action: str = Field(..., description="read|unread|archive|mark_all_read")
    notification_ids: list[str] | None = Field(default=None)


class NotificationStateResponse(BaseModel):
    updated: int


def parse_notification_ids(raw_ids: list[str] | None) -> list[uuid.UUID] | None:
    if raw_ids is None:
        return None
    parsed: list[uuid.UUID] = []
    for value in raw_ids:
        try:
            parsed.append(uuid.UUID(value))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid notification id") from exc
    return parsed


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_archived: Annotated[bool, Query()] = False,
) -> NotificationListResponse:
    rows, total, unread_total = await fetch_notification_rows(
        db,
        current_user=current_user,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
    )
    now = datetime.now(timezone.utc)
    items = [NotificationItemResponse.model_validate(serialize_notification(item, state, now)) for item, state in rows]
    return NotificationListResponse(items=items, total=total, unread_total=unread_total)


@router.put("/jobs/{client_key}", response_model=NotificationItemResponse)
async def upsert_job(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    client_key: Annotated[str, Path(min_length=1, max_length=191)],
    body: Annotated[NotificationJobUpsertRequest, Body(...)],
) -> NotificationItemResponse:
    payload = body.model_dump()
    item = await upsert_job_notification(db, current_user=current_user, client_key=client_key, payload=payload)
    await db.commit()
    await db.refresh(item)
    return NotificationItemResponse.model_validate(serialize_notification(item, None, datetime.now(timezone.utc)))


@router.patch("/state", response_model=NotificationStateResponse)
async def update_notification_state(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: Annotated[NotificationStateRequest, Body(...)],
) -> NotificationStateResponse:
    if body.action not in STATE_ACTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state action")
    ids = parse_notification_ids(body.notification_ids)
    if body.action != "mark_all_read" and not ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="notification_ids required")
    updated = await apply_state_action(db, current_user=current_user, action=body.action, ids=ids)
    await db.commit()
    return NotificationStateResponse(updated=updated)
