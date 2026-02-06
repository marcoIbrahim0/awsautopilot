"""
Findings API endpoints for listing and retrieving Security Hub findings.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_optional_user
from backend.database import get_db
from backend.models.finding import Finding
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.services.exception_service import get_exception_state_for_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/findings", tags=["findings"])


# ============================================
# Response Models
# ============================================

class FindingResponse(BaseModel):
    """Response model for a single finding."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    finding_id: str
    tenant_id: str
    account_id: str
    region: str
    source: str = "security_hub"  # Step 2B.1: security_hub | access_analyzer
    severity_label: str
    severity_normalized: int
    status: str
    title: str
    description: str | None
    resource_id: str | None
    resource_type: str | None
    control_id: str | None
    standard_name: str | None
    first_observed_at: str | None
    last_observed_at: str | None
    updated_at: str | None
    created_at: str
    updated_at_db: str
    raw_json: dict | None = None
    # Step 6.3: exception state (on-read expiry)
    exception_id: str | None = None
    exception_expires_at: str | None = None
    exception_expired: bool | None = None


class FindingsListResponse(BaseModel):
    """Paginated response for findings list."""
    
    items: list[FindingResponse]
    total: int


# ============================================
# Helper Functions
# ============================================

def finding_to_response(
    finding: Finding,
    include_raw: bool = False,
    exception_state: dict | None = None,
) -> FindingResponse:
    """Convert a Finding model to a FindingResponse."""
    state = exception_state or {}
    return FindingResponse(
        id=str(finding.id),
        finding_id=finding.finding_id,
        tenant_id=str(finding.tenant_id),
        account_id=finding.account_id,
        region=finding.region,
        source=getattr(finding, "source", "security_hub"),
        severity_label=finding.severity_label,
        severity_normalized=finding.severity_normalized,
        status=finding.status,
        title=finding.title,
        description=finding.description,
        resource_id=finding.resource_id,
        resource_type=finding.resource_type,
        control_id=finding.control_id,
        standard_name=finding.standard_name,
        first_observed_at=finding.first_observed_at.isoformat() if finding.first_observed_at else None,
        last_observed_at=finding.last_observed_at.isoformat() if finding.last_observed_at else None,
        updated_at=finding.sh_updated_at.isoformat() if finding.sh_updated_at else None,
        created_at=finding.created_at.isoformat() if finding.created_at else "",
        updated_at_db=finding.updated_at.isoformat() if finding.updated_at else "",
        raw_json=finding.raw_json if include_raw else None,
        exception_id=state.get("exception_id"),
        exception_expires_at=state.get("exception_expires_at"),
        exception_expired=state.get("exception_expired"),
    )


async def get_tenant_by_uuid(db: AsyncSession, tenant_uuid: uuid.UUID) -> Tenant:
    """Retrieve and validate tenant by UUID."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Tenant not found", "detail": f"No tenant found with ID {tenant_uuid}"},
        )

    return tenant


def resolve_tenant_id(
    current_user: Optional[User],
    request_tenant_id: Optional[str],
) -> uuid.UUID:
    """
    Resolve tenant_id from auth (preferred) or request (fallback).
    
    If user is authenticated → use user.tenant_id, ignore request.
    If user is None → require and parse request tenant_id.
    """
    if current_user is not None:
        return current_user.tenant_id
    
    if not request_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required or tenant_id must be provided",
        )
    
    try:
        return uuid.UUID(request_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid tenant_id", "detail": "tenant_id must be a valid UUID"},
        )


# ============================================
# Endpoints
# ============================================

@router.get("", response_model=FindingsListResponse)
async def list_findings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    account_id: Annotated[str | None, Query(description="Filter by AWS account ID")] = None,
    region: Annotated[str | None, Query(description="Filter by AWS region")] = None,
    severity: Annotated[str | None, Query(description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL)")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="Filter by status (NEW, NOTIFIED, RESOLVED, SUPPRESSED)")] = None,
    source: Annotated[str | None, Query(description="Filter by source (security_hub, access_analyzer, inspector; comma-separated)")] = None,
    first_observed_since: Annotated[datetime | None, Query(description="Filter findings first observed at or after this datetime (ISO8601)")] = None,
    last_observed_since: Annotated[datetime | None, Query(description="Filter findings last observed at or after this datetime (ISO8601)")] = None,
    updated_since: Annotated[datetime | None, Query(description="Filter findings updated (by Security Hub) at or after this datetime (ISO8601)")] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Maximum number of findings to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of findings to skip")] = 0,
) -> FindingsListResponse:
    """
    List findings with optional filters and pagination.
    
    Returns findings scoped to the specified tenant with optional filtering
    by account, region, severity, status, and time ranges. Results are paginated.
    
    **Authentication:**
    - If Bearer token is provided, tenant is resolved from the token.
    - Otherwise, tenant_id query parameter is required.
    
    **Query Parameters:**
    - `tenant_id` (optional when authenticated): Tenant UUID for multi-tenant isolation
    - `account_id` (optional): Filter by AWS account ID
    - `region` (optional): Filter by AWS region (e.g., us-east-1)
    - `severity` (optional): Filter by severity level (comma-separated: CRITICAL,HIGH)
    - `status` (optional): Filter by finding status (comma-separated: NEW,NOTIFIED)
    - `first_observed_since` (optional): ISO8601 datetime; only findings first observed at or after this time
    - `last_observed_since` (optional): ISO8601 datetime; only findings last observed at or after this time
    - `updated_since` (optional): ISO8601 datetime; only findings updated (by Security Hub) at or after this time
    - `limit` (optional): Max results per page (1-200, default 50)
    - `offset` (optional): Number of results to skip (default 0)
    
    **Response:**
    - `items`: Array of finding objects
    - `total`: Total count of findings matching the filters
    """
    # Resolve tenant from auth or request
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant_by_uuid(db, tenant_uuid)

    # Build query with tenant isolation
    query = select(Finding).where(Finding.tenant_id == tenant.id)

    # Apply optional filters
    if account_id:
        query = query.where(Finding.account_id == account_id)
    if region:
        query = query.where(Finding.region == region)
    if severity:
        # Support comma-separated severities (e.g., "CRITICAL,HIGH")
        severities = [s.strip().upper() for s in severity.split(",")]
        query = query.where(Finding.severity_label.in_(severities))
    if status_filter:
        # Support comma-separated statuses (e.g., "NEW,NOTIFIED")
        statuses = [s.strip().upper() for s in status_filter.split(",")]
        query = query.where(Finding.status.in_(statuses))
    if source:
        # Step 2B.1: filter by source (security_hub, access_analyzer)
        sources = [s.strip().lower() for s in source.split(",")]
        query = query.where(Finding.source.in_(sources))

    # Apply time-range filters (for Top Risks time tabs)
    if first_observed_since:
        query = query.where(Finding.first_observed_at >= first_observed_since)
    if last_observed_since:
        query = query.where(Finding.last_observed_at >= last_observed_since)
    if updated_since:
        query = query.where(Finding.sh_updated_at >= updated_since)

    # Get total count (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply ordering and pagination
    query = query.order_by(
        Finding.severity_normalized.desc(),  # Most severe first
        Finding.sh_updated_at.desc().nullslast(),  # Most recently updated
    )
    query = query.limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    findings = result.scalars().all()

    # Convert to response with exception state (Step 6.3)
    items = []
    for f in findings:
        exception_state = await get_exception_state_for_response(
            db, tenant_uuid, "finding", f.id
        )
        items.append(finding_to_response(f, include_raw=False, exception_state=exception_state))

    logger.info(
        "Listed %d findings for tenant %s (total: %d, limit: %d, offset: %d)",
        len(items),
        str(tenant_uuid),
        total,
        limit,
        offset,
    )

    return FindingsListResponse(items=items, total=total)


@router.get("/{finding_id}", response_model=FindingResponse)
async def get_finding(
    finding_id: Annotated[str, Path(description="Finding UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    include_raw: Annotated[bool, Query(description="Include raw Security Hub JSON")] = True,
) -> FindingResponse:
    """
    Get a single finding by ID.
    
    Returns the full finding details including raw Security Hub JSON
    if requested. Scoped to the specified tenant.
    
    **Authentication:**
    - If Bearer token is provided, tenant is resolved from the token.
    - Otherwise, tenant_id query parameter is required.
    
    **Path Parameters:**
    - `finding_id`: The internal UUID of the finding
    
    **Query Parameters:**
    - `tenant_id` (optional when authenticated): Tenant UUID for multi-tenant isolation
    - `include_raw` (optional): Include raw_json field (default true)
    
    **Response:**
    Full finding object with all fields.
    
    **Errors:**
    - 404: Finding not found or not accessible by this tenant
    """
    # Resolve tenant from auth or request
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant_by_uuid(db, tenant_uuid)

    # Parse finding UUID
    try:
        finding_uuid = uuid.UUID(finding_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid finding_id", "detail": "finding_id must be a valid UUID"},
        )

    # Query finding with tenant isolation
    result = await db.execute(
        select(Finding).where(
            Finding.id == finding_uuid,
            Finding.tenant_id == tenant.id,
        )
    )
    finding = result.scalar_one_or_none()

    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Finding not found", "detail": f"No finding found with ID {finding_id}"},
        )

    exception_state = await get_exception_state_for_response(
        db, tenant_uuid, "finding", finding.id
    )
    logger.info(f"Retrieved finding {finding_id} for tenant {tenant_id}")

    return finding_to_response(finding, include_raw=include_raw, exception_state=exception_state)
