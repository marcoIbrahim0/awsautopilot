"""
Control mappings API (Step 12.3).

Lists and manages control_id → framework mappings used in compliance pack exports.
Global v1 mapping; GET requires auth; POST (add) requires admin.
"""
from __future__ import annotations

import logging
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.auth import get_current_user
from backend.database import get_db
from backend.models.control_mapping import ControlMapping
from backend.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/control-mappings", tags=["control-mappings"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ControlMappingResponse(BaseModel):
    """Single control mapping for API responses."""

    id: str
    control_id: str
    framework_name: str
    framework_control_code: str
    control_title: str
    description: str
    created_at: str


class ControlMappingListResponse(BaseModel):
    """Paginated list of control mappings."""

    items: list[ControlMappingResponse]
    total: int


class CreateControlMappingRequest(BaseModel):
    """Request body for POST (add mapping)."""

    control_id: str = Field(..., min_length=1, max_length=64)
    framework_name: str = Field(..., min_length=1, max_length=128)
    framework_control_code: str = Field(..., min_length=1, max_length=64)
    control_title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# GET /control-mappings — List mappings (auth required)
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=ControlMappingListResponse,
    summary="List control mappings",
    description="List control_id → framework mappings used in compliance pack. Optional filters.",
)
async def list_control_mappings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    control_id: Annotated[Optional[str], Query(description="Filter by control_id")] = None,
    framework_name: Annotated[Optional[str], Query(description="Filter by framework_name")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ControlMappingListResponse:
    """List control mappings with optional filters and pagination."""
    base = select(ControlMapping)
    if control_id is not None and control_id.strip():
        base = base.where(ControlMapping.control_id == control_id.strip())
    if framework_name is not None and framework_name.strip():
        base = base.where(ControlMapping.framework_name == framework_name.strip())

    count_query = select(func.count(ControlMapping.id)).select_from(ControlMapping)
    if control_id is not None and control_id.strip():
        count_query = count_query.where(ControlMapping.control_id == control_id.strip())
    if framework_name is not None and framework_name.strip():
        count_query = count_query.where(ControlMapping.framework_name == framework_name.strip())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = base.order_by(ControlMapping.control_id, ControlMapping.framework_name).offset(offset).limit(limit)
    result = await db.execute(query)
    rows = list(result.scalars().all())

    items = [
        ControlMappingResponse(
            id=str(m.id),
            control_id=m.control_id or "",
            framework_name=m.framework_name or "",
            framework_control_code=m.framework_control_code or "",
            control_title=m.control_title or "",
            description=m.description or "",
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m in rows
    ]
    return ControlMappingListResponse(items=items, total=total)


# ---------------------------------------------------------------------------
# GET /control-mappings/{id} — Get one mapping
# ---------------------------------------------------------------------------

@router.get(
    "/{mapping_id}",
    response_model=ControlMappingResponse,
    summary="Get control mapping by ID",
)
async def get_control_mapping(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    mapping_id: Annotated[str, Path(description="Control mapping UUID")],
) -> ControlMappingResponse:
    """Get a single control mapping by id."""
    try:
        mapping_uuid = uuid.UUID(mapping_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control mapping not found")
    result = await db.execute(select(ControlMapping).where(ControlMapping.id == mapping_uuid))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control mapping not found")
    return ControlMappingResponse(
        id=str(m.id),
        control_id=m.control_id or "",
        framework_name=m.framework_name or "",
        framework_control_code=m.framework_control_code or "",
        control_title=m.control_title or "",
        description=m.description or "",
        created_at=m.created_at.isoformat() if m.created_at else "",
    )


# ---------------------------------------------------------------------------
# POST /control-mappings — Add mapping (admin only)
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ControlMappingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add control mapping",
    description="Add a control_id → framework mapping. Admin only. Duplicate (control_id, framework_name) returns 409.",
)
async def create_control_mapping(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: CreateControlMappingRequest,
) -> ControlMappingResponse:
    """Add a new control mapping. Requires admin role."""
    if getattr(current_user.role, "value", current_user.role) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can add control mappings",
        )
    mapping = ControlMapping(
        control_id=body.control_id.strip(),
        framework_name=body.framework_name.strip(),
        framework_control_code=body.framework_control_code.strip(),
        control_title=body.control_title.strip(),
        description=body.description.strip(),
    )
    db.add(mapping)
    try:
        await db.commit()
        await db.refresh(mapping)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A mapping for this control_id and framework_name already exists",
        )
    return ControlMappingResponse(
        id=str(mapping.id),
        control_id=mapping.control_id or "",
        framework_name=mapping.framework_name or "",
        framework_control_code=mapping.framework_control_code or "",
        control_title=mapping.control_title or "",
        description=mapping.description or "",
        created_at=mapping.created_at.isoformat() if mapping.created_at else "",
    )