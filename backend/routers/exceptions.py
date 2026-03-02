"""
Exceptions API: create, list, get, revoke (Step 6.2).

Exceptions suppress findings or actions with reason, approver, and expiry.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_current_user, get_optional_user
from backend.database import get_db
from backend.models.action import Action
from backend.models.enums import EntityType
from backend.models.exception import Exception
from backend.models.finding import Finding
from backend.models.user import User
from backend.routers.aws_accounts import get_tenant, resolve_tenant_id
from backend.services.exception_governance import (
    get_exception_lifecycle_status,
    schedule_next_revalidation_at,
    schedule_next_reminder_at,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exceptions", tags=["exceptions"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CreateExceptionRequest(BaseModel):
    """Request body for creating an exception."""

    entity_type: Literal["finding", "action"] = Field(..., description="Type of entity to suppress")
    entity_id: str = Field(..., description="UUID of finding or action to suppress")
    reason: str = Field(..., min_length=10, description="Reason for suppression (min 10 characters)")
    expires_at: str = Field(..., description="ISO8601 datetime when exception expires")
    ticket_link: Optional[str] = Field(default=None, max_length=500, description="Optional link to ticket/issue")
    owner_user_id: str | None = Field(default=None, description="Optional owner user UUID (same tenant)")
    approval_metadata: dict[str, Any] | None = Field(default=None, description="Optional approval metadata")
    reminder_interval_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="Optional reminder interval in days",
    )
    revalidation_interval_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="Optional revalidation cycle interval in days",
    )


class ExceptionResponse(BaseModel):
    """Full exception details."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    entity_type: str
    entity_id: str
    reason: str
    approved_by_user_id: str
    approved_by_email: str | None
    owner_user_id: str | None = None
    owner_email: str | None = None
    approval_metadata: dict[str, Any] | None = None
    ticket_link: str | None
    expires_at: str
    reminder_interval_days: int | None = None
    next_reminder_at: str | None = None
    revalidation_interval_days: int | None = None
    next_revalidation_at: str | None = None
    lifecycle_status: str
    created_at: str
    updated_at: str


class ExceptionListItem(BaseModel):
    """Exception summary for list view."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    reason: str
    approved_by_user_id: str
    approved_by_email: str | None
    owner_user_id: str | None = None
    owner_email: str | None = None
    ticket_link: str | None
    expires_at: str
    created_at: str
    next_reminder_at: str | None = None
    next_revalidation_at: str | None = None
    lifecycle_status: str
    is_expired: bool


class ExceptionsListResponse(BaseModel):
    """Paginated list of exceptions."""

    items: list[ExceptionListItem]
    total: int


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _exception_to_response(exception: Exception) -> ExceptionResponse:
    """Convert Exception model to response. Requires approved_by relationship loaded."""
    approved_by_email = exception.approved_by.email if exception.approved_by else None
    owner_email = exception.owner.email if exception.owner else None
    return ExceptionResponse(
        id=str(exception.id),
        tenant_id=str(exception.tenant_id),
        entity_type=exception.entity_type.value,
        entity_id=str(exception.entity_id),
        reason=exception.reason,
        approved_by_user_id=str(exception.approved_by_user_id),
        approved_by_email=approved_by_email,
        owner_user_id=str(exception.owner_user_id) if exception.owner_user_id else None,
        owner_email=owner_email,
        approval_metadata=exception.approval_metadata if isinstance(exception.approval_metadata, dict) else None,
        ticket_link=exception.ticket_link,
        expires_at=exception.expires_at.isoformat(),
        reminder_interval_days=exception.reminder_interval_days,
        next_reminder_at=exception.next_reminder_at.isoformat() if exception.next_reminder_at else None,
        revalidation_interval_days=exception.revalidation_interval_days,
        next_revalidation_at=exception.next_revalidation_at.isoformat() if exception.next_revalidation_at else None,
        lifecycle_status=get_exception_lifecycle_status(exception),
        created_at=exception.created_at.isoformat(),
        updated_at=exception.updated_at.isoformat(),
    )


def _exception_to_list_item(exception: Exception) -> ExceptionListItem:
    """Convert Exception model to list item. Requires approved_by relationship loaded."""
    approved_by_email = exception.approved_by.email if exception.approved_by else None
    owner_email = exception.owner.email if exception.owner else None
    now = datetime.now(timezone.utc)
    is_expired = exception.expires_at <= now
    return ExceptionListItem(
        id=str(exception.id),
        entity_type=exception.entity_type.value,
        entity_id=str(exception.entity_id),
        reason=exception.reason,
        approved_by_user_id=str(exception.approved_by_user_id),
        approved_by_email=approved_by_email,
        owner_user_id=str(exception.owner_user_id) if exception.owner_user_id else None,
        owner_email=owner_email,
        ticket_link=exception.ticket_link,
        expires_at=exception.expires_at.isoformat(),
        created_at=exception.created_at.isoformat(),
        next_reminder_at=exception.next_reminder_at.isoformat() if exception.next_reminder_at else None,
        next_revalidation_at=exception.next_revalidation_at.isoformat() if exception.next_revalidation_at else None,
        lifecycle_status=get_exception_lifecycle_status(exception, now=now),
        is_expired=is_expired,
    )


# ---------------------------------------------------------------------------
# POST /exceptions - Create exception (requires auth)
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ExceptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create exception",
    description="Suppress a finding or action with reason, approver, and expiry. Requires authentication.",
    responses={
        400: {"description": "Invalid entity_id, expires_at in past, or entity not found"},
        401: {"description": "Not authenticated"},
        404: {"description": "Tenant or entity not found"},
        409: {"description": "Exception already exists for this entity"},
    },
)
async def create_exception(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: CreateExceptionRequest = Body(...),
) -> ExceptionResponse:
    """
    Create an exception (suppression) for a finding or action.
    Authenticated user becomes the approver.
    """
    tenant_uuid = current_user.tenant_id

    # Validate entity_id is UUID
    try:
        entity_uuid = uuid.UUID(body.entity_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid entity_id", "detail": "entity_id must be a valid UUID"},
        )

    # Parse and validate expires_at
    try:
        expires_at = datetime.fromisoformat(body.expires_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid expires_at", "detail": "expires_at must be a valid ISO8601 datetime"},
        )

    # Ensure expires_at is in the future
    now = datetime.now(timezone.utc)
    if expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid expires_at", "detail": "expires_at must be in the future"},
        )

    owner_user_id = current_user.id
    if body.owner_user_id:
        try:
            owner_uuid = uuid.UUID(body.owner_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid owner_user_id", "detail": "owner_user_id must be a valid UUID"},
            )

        owner_result = await db.execute(
            select(User).where(
                User.id == owner_uuid,
                User.tenant_id == tenant_uuid,
            )
        )
        owner = owner_result.scalar_one_or_none()
        if not owner:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid owner_user_id", "detail": "owner_user_id must belong to the tenant"},
            )
        owner_user_id = owner.id

    # Validate entity exists and belongs to tenant
    if body.entity_type == "finding":
        result = await db.execute(
            select(Finding).where(Finding.id == entity_uuid, Finding.tenant_id == tenant_uuid)
        )
        entity = result.scalar_one_or_none()
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Finding not found", "detail": f"No finding found with ID {body.entity_id}"},
            )
    elif body.entity_type == "action":
        result = await db.execute(
            select(Action).where(Action.id == entity_uuid, Action.tenant_id == tenant_uuid)
        )
        entity = result.scalar_one_or_none()
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Action not found", "detail": f"No action found with ID {body.entity_id}"},
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid entity_type", "detail": "entity_type must be 'finding' or 'action'"},
        )

    # Check if exception already exists
    existing = await db.execute(
        select(Exception).where(
            Exception.tenant_id == tenant_uuid,
            Exception.entity_type == EntityType(body.entity_type),
            Exception.entity_id == entity_uuid,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Exception already exists",
                "detail": "An exception already exists for this item. Revoke or update it first.",
            },
        )

    # Create exception
    approval_metadata = body.approval_metadata if isinstance(body.approval_metadata, dict) else None
    if approval_metadata is not None:
        approval_metadata = dict(approval_metadata)
        approval_metadata.setdefault("approved_at", now.isoformat())
        approval_metadata.setdefault("approved_by_user_id", str(current_user.id))

    exception = Exception(
        tenant_id=tenant_uuid,
        entity_type=EntityType(body.entity_type),
        entity_id=entity_uuid,
        reason=body.reason,
        approved_by_user_id=current_user.id,
        owner_user_id=owner_user_id,
        approval_metadata=approval_metadata,
        ticket_link=body.ticket_link,
        expires_at=expires_at,
        reminder_interval_days=body.reminder_interval_days,
        revalidation_interval_days=body.revalidation_interval_days,
        next_reminder_at=schedule_next_reminder_at(
            expires_at=expires_at,
            interval_days=body.reminder_interval_days,
            now=now,
            last_reminded_at=None,
        ),
        next_revalidation_at=schedule_next_revalidation_at(
            expires_at=expires_at,
            interval_days=body.revalidation_interval_days,
            now=now,
            last_revalidated_at=None,
        ),
    )
    db.add(exception)
    await db.commit()

    # Optionally update action status to suppressed
    if body.entity_type == "action":
        entity.status = "suppressed"
        await db.commit()

    # Re-query with relationships for response
    result = await db.execute(
        select(Exception)
        .where(Exception.id == exception.id)
        .options(selectinload(Exception.approved_by), selectinload(Exception.owner))
    )
    exception = result.scalar_one()

    logger.info(
        "Created exception %s for %s %s by user %s (tenant %s)",
        exception.id,
        body.entity_type,
        body.entity_id,
        current_user.id,
        tenant_uuid,
    )

    return _exception_to_response(exception)


# ---------------------------------------------------------------------------
# GET /exceptions - List exceptions
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=ExceptionsListResponse,
    summary="List exceptions",
    description="List exceptions with optional filters. Supports pagination.",
)
async def list_exceptions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    entity_type: Annotated[
        Optional[str],
        Query(description="Filter by entity type (finding or action)"),
    ] = None,
    entity_id: Annotated[
        Optional[str],
        Query(description="Filter by specific entity UUID"),
    ] = None,
    active_only: Annotated[
        bool,
        Query(description="Only return non-expired exceptions"),
    ] = True,
    limit: Annotated[int, Query(ge=1, le=200, description="Max items per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
) -> ExceptionsListResponse:
    """
    List exceptions with optional filters and pagination.
    Returns exceptions scoped to the tenant.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    query = (
        select(Exception)
        .where(Exception.tenant_id == tenant_uuid)
        .options(selectinload(Exception.approved_by), selectinload(Exception.owner))
    )

    # Apply filters
    if entity_type is not None:
        if entity_type not in ["finding", "action"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid entity_type", "detail": "entity_type must be 'finding' or 'action'"},
            )
        query = query.where(Exception.entity_type == EntityType(entity_type))

    if entity_id is not None:
        try:
            entity_uuid = uuid.UUID(entity_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid entity_id", "detail": "entity_id must be a valid UUID"},
            )
        query = query.where(Exception.entity_id == entity_uuid)

    if active_only:
        now = datetime.now(timezone.utc)
        query = query.where(Exception.expires_at > now)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(Exception.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    exceptions = result.scalars().unique().all()

    items = [_exception_to_list_item(e) for e in exceptions]
    logger.info("Listed %d exceptions for tenant %s (total=%d)", len(items), tenant_uuid, total)
    return ExceptionsListResponse(items=items, total=total)


# ---------------------------------------------------------------------------
# GET /exceptions/{id} - Get single exception
# ---------------------------------------------------------------------------

@router.get(
    "/{exception_id}",
    response_model=ExceptionResponse,
    summary="Get exception",
    description="Get a single exception by ID. Tenant-scoped.",
    responses={
        400: {"description": "Invalid exception_id"},
        404: {"description": "Exception not found"},
    },
)
async def get_exception(
    exception_id: Annotated[str, Path(description="Exception UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> ExceptionResponse:
    """
    Get a single exception by ID with full details.
    Tenant-scoped; 404 if not found.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    try:
        exception_uuid = uuid.UUID(exception_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid exception_id", "detail": "exception_id must be a valid UUID"},
        )

    result = await db.execute(
        select(Exception)
        .where(Exception.id == exception_uuid, Exception.tenant_id == tenant_uuid)
        .options(selectinload(Exception.approved_by), selectinload(Exception.owner))
    )
    exception = result.scalar_one_or_none()
    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Exception not found", "detail": f"No exception found with ID {exception_id}"},
        )

    return _exception_to_response(exception)


# ---------------------------------------------------------------------------
# DELETE /exceptions/{id} - Revoke exception
# ---------------------------------------------------------------------------

@router.delete(
    "/{exception_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke exception",
    description="Delete an exception (revoke suppression). Tenant-scoped.",
    responses={
        400: {"description": "Invalid exception_id"},
        404: {"description": "Exception not found"},
    },
)
async def revoke_exception(
    exception_id: Annotated[str, Path(description="Exception UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> None:
    """
    Revoke (delete) an exception.
    If the exception was for an action with status 'suppressed', the action status is NOT automatically changed.
    Use the action PATCH endpoint to update status if needed.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    try:
        exception_uuid = uuid.UUID(exception_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid exception_id", "detail": "exception_id must be a valid UUID"},
        )

    result = await db.execute(
        select(Exception).where(Exception.id == exception_uuid, Exception.tenant_id == tenant_uuid)
    )
    exception = result.scalar_one_or_none()
    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Exception not found", "detail": f"No exception found with ID {exception_id}"},
        )

    await db.delete(exception)
    await db.commit()

    logger.info("Revoked exception %s for tenant %s", exception_id, tenant_uuid)
