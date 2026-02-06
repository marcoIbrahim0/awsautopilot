"""
AWS Accounts API endpoints for registering and managing customer AWS accounts.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.aws_account import AwsAccount
from backend.models.enums import AwsAccountStatus
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.services.aws import assume_role
from backend.utils.sqs import (
    build_ingest_access_analyzer_job_payload,
    build_ingest_inspector_job_payload,
    build_ingest_job_payload,
    parse_queue_region,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aws/accounts", tags=["aws-accounts"])


# Request/Response Models
def _validate_role_arn_format(v: str, field_name: str = "role_arn") -> str:
    """Validate IAM role ARN format. Raises ValueError if invalid."""
    arn_pattern = r"^arn:aws:iam::\d{12}:role/[a-zA-Z0-9+=,.@_-]+$"
    if not re.match(arn_pattern, v):
        raise ValueError(f"{field_name} must be a valid IAM role ARN (arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME)")
    return v


class AccountRegistrationRequest(BaseModel):
    """Request model for registering an AWS account."""

    account_id: str = Field(..., description="AWS account ID (12 digits)")
    role_read_arn: str = Field(..., description="IAM role ARN for read access (ingestion)")
    role_write_arn: str = Field(
        ...,
        description="IAM role ARN for write access (required). Deploy the WriteRole CloudFormation template first, then paste WriteRoleArn here.",
    )
    regions: list[str] = Field(default_factory=list, description="List of AWS regions to monitor")
    tenant_id: str = Field(
        ...,
        description="Tenant ID (UUID). TODO: Replace with auth context when authentication is implemented.",
    )

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, v: str) -> str:
        """Validate AWS account ID is exactly 12 digits."""
        if not re.match(r"^\d{12}$", v):
            raise ValueError("account_id must be exactly 12 digits")
        return v

    @field_validator("role_read_arn")
    @classmethod
    def validate_role_read_arn(cls, v: str) -> str:
        """Validate IAM role ARN format."""
        return _validate_role_arn_format(v, "role_read_arn")

    @field_validator("role_write_arn")
    @classmethod
    def validate_role_write_arn(cls, v: str) -> str:
        """Validate WriteRole ARN format (required)."""
        return _validate_role_arn_format(v, "role_write_arn")

    @field_validator("regions")
    @classmethod
    def validate_regions(cls, v: list[str]) -> list[str]:
        """Validate regions list: 1–5 items, valid region names."""
        if not v:
            raise ValueError("regions list cannot be empty. Provide at least one AWS region (e.g., ['us-east-1'])")
        if len(v) > 5:
            raise ValueError("At most 5 regions allowed. Provide 1 to 5 AWS regions.")
        # Basic validation - AWS region format: us-east-1, eu-west-1, etc.
        region_pattern = r"^[a-z]{2}-[a-z]+-\d+$"
        for region in v:
            if not re.match(region_pattern, region):
                raise ValueError(f"Invalid region format: {region}. Expected format: us-east-1, eu-west-1, etc.")
        return v

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: str) -> str:
        """Validate tenant_id is a valid UUID."""
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("tenant_id must be a valid UUID")
        return v

    @model_validator(mode="after")
    def validate_role_write_arn_matches_account(self):
        """role_write_arn account ID must match account_id."""
        arn_parts = self.role_write_arn.split(":")
        if len(arn_parts) >= 5 and arn_parts[4] != self.account_id:
            raise ValueError(
                f"role_write_arn account ID ({arn_parts[4]}) must match account_id ({self.account_id})"
            )
        return self


class AccountRegistrationResponse(BaseModel):
    """Response model for successful account registration."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "account_id": "123456789012",
                "status": "validated",
                "last_validated_at": "2026-01-29T10:00:00Z",
            }
        }
    )

    id: str
    account_id: str
    status: str
    last_validated_at: datetime | None


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    details: str | None = None


class AccountUpdateRequest(BaseModel):
    """Request model for PATCH /aws/accounts/{account_id}. Updates WriteRole and/or status (stop/resume)."""

    role_write_arn: str | None = Field(
        default=None,
        description="WriteRole ARN to enable direct fixes, or null to remove.",
    )
    status: Literal["disabled", "validated"] | None = Field(
        default=None,
        description="Set to 'disabled' to stop monitoring, or 'validated' to resume.",
    )

    @field_validator("role_write_arn")
    @classmethod
    def validate_role_write_arn_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_role_arn_format(v, "role_write_arn")


class ValidationResponse(BaseModel):
    """Response model for account validation."""

    status: str = Field(..., description="validated or error")
    account_id: str = Field(..., description="AWS account ID (12 digits)")
    last_validated_at: datetime | None = Field(None, description="When validation last ran")
    permissions_ok: bool = Field(
        ...,
        description="True if STS and Security Hub check succeeded (ReadRole); WriteRole is required at registration.",
    )


# Ingest trigger (POST /api/aws/accounts/{account_id}/ingest)
_REGION_PATTERN = re.compile(r"^[a-z]{2}-[a-z]+-\d+$")


class IngestTriggerRequest(BaseModel):
    """Optional request body for triggering ingestion. If omitted, account's stored regions are used."""

    regions: list[str] | None = Field(
        default=None,
        description="Override regions to ingest. Must be a subset of account's configured regions.",
    )

    @field_validator("regions")
    @classmethod
    def validate_regions_format(cls, v: list[str] | None) -> list[str] | None:
        if not v:
            return v
        for region in v:
            if not _REGION_PATTERN.match(region):
                raise ValueError(f"Invalid region format: {region}. Expected format: us-east-1, eu-west-1, etc.")
        return v


class IngestTriggerResponse(BaseModel):
    """Response for successful ingest trigger (202 Accepted)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "account_id": "123456789012",
                "jobs_queued": 2,
                "regions": ["us-east-1", "us-west-2"],
                "message_ids": ["abc-123", "def-456"],
                "message": "Ingestion jobs queued successfully",
            }
        }
    )

    account_id: str = Field(..., description="AWS account ID (12 digits)")
    jobs_queued: int = Field(..., description="Number of SQS messages enqueued (one per region)")
    regions: list[str] = Field(..., description="Regions for which jobs were queued")
    message_ids: list[str] = Field(..., description="SQS MessageId for each enqueued job")
    message: str = Field(..., description="Human-readable status message")


class IngestTriggerErrorResponse(BaseModel):
    """Error body for ingest trigger (404, 400, 409, 503)."""

    error: str = Field(..., description="Error code or short message")
    detail: str = Field(..., description="Detailed message for client")


# Helper: get tenant by ID
async def get_tenant(tenant_id: uuid.UUID, db: AsyncSession) -> Tenant:
    """
    Get tenant by ID.
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant with id {tenant_id} not found",
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
    
    Supports backward compatibility: existing API callers can still pass tenant_id
    when not authenticated.
    """
    if current_user is not None:
        # Authenticated: use user's tenant
        return current_user.tenant_id
    
    # Not authenticated: require tenant_id from request
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
            detail="tenant_id must be a valid UUID",
        )


# Helper: account lookup by tenant + account_id (reused by validate_account, trigger_ingest)
async def get_account_for_tenant(
    tenant_id: uuid.UUID,
    account_id: str,
    db: AsyncSession,
) -> AwsAccount | None:
    """Return AWS account for tenant if found, else None."""
    result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_id,
            AwsAccount.account_id == account_id,
        )
    )
    return result.scalar_one_or_none()


def _enqueue_ingest_jobs(tenant_id: uuid.UUID, account_id: str, regions: list[str]) -> list[str]:
    """
    Send one SQS message per region (multi-region ingestion — Step 2.7).

    For each region in the account's configured list, enqueues one ingest_findings job.
    The worker processes each message independently (one region per job). Multi-region
    is the default: no separate "multi-region mode" is required.

    Returns message_ids. Raises on first SQS failure (all-or-nothing enqueue).
    Caller must ensure settings.has_ingest_queue and queue URL is set.
    Uses shared parse_queue_region and build_ingest_job_payload (worker contract).
    """
    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=region)
    message_ids: list[str] = []
    now = datetime.now(timezone.utc).isoformat()
    for r in regions:
        payload = build_ingest_job_payload(tenant_id, account_id, r, now)
        resp = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
        message_ids.append(resp["MessageId"])
    return message_ids


def _enqueue_ingest_access_analyzer_jobs(
    tenant_id: uuid.UUID, account_id: str, regions: list[str]
) -> list[str]:
    """
    Send one SQS message per region for IAM Access Analyzer ingestion (Step 2B.1).

    Same queue and pattern as Security Hub ingest; job_type is ingest_access_analyzer.
    Returns message_ids. Raises on first SQS failure.
    """
    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=region)
    message_ids: list[str] = []
    now = datetime.now(timezone.utc).isoformat()
    for r in regions:
        payload = build_ingest_access_analyzer_job_payload(tenant_id, account_id, r, now)
        resp = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
        message_ids.append(resp["MessageId"])
    return message_ids


def _enqueue_ingest_inspector_jobs(
    tenant_id: uuid.UUID, account_id: str, regions: list[str]
) -> list[str]:
    """
    Send one SQS message per region for Amazon Inspector v2 ingestion (Step 2B.2).

    Same queue and pattern as Security Hub ingest; job_type is ingest_inspector.
    Returns message_ids. Raises on first SQS failure.
    """
    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=region)
    message_ids: list[str] = []
    now = datetime.now(timezone.utc).isoformat()
    for r in regions:
        payload = build_ingest_inspector_job_payload(tenant_id, account_id, r, now)
        resp = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
        message_ids.append(resp["MessageId"])
    return message_ids


# List accounts response model
class AccountListItem(BaseModel):
    """Single account item in list response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    role_read_arn: str
    role_write_arn: str | None
    regions: list[str]
    status: str
    last_validated_at: datetime | None
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=list[AccountListItem])
async def list_accounts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> list[AccountListItem]:
    """
    List all AWS accounts for a tenant.

    Returns all connected AWS accounts with their current status,
    regions, and last validation time.

    **Authentication:**
    - If Bearer token is provided, tenant is resolved from the token.
    - Otherwise, tenant_id query parameter is required.

    **Response:**
    Array of account objects with id, account_id, role ARNs, regions, status, timestamps.
    """
    # Resolve tenant from auth or request
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)

    # Verify tenant exists
    tenant = await get_tenant(tenant_uuid, db)

    # Query accounts for this tenant
    result = await db.execute(
        select(AwsAccount)
        .where(AwsAccount.tenant_id == tenant.id)
        .order_by(AwsAccount.created_at.desc())
    )
    accounts = result.scalars().all()

    # Convert to response
    return [
        AccountListItem(
            id=str(acc.id),
            account_id=acc.account_id,
            role_read_arn=acc.role_read_arn,
            role_write_arn=acc.role_write_arn,
            regions=acc.regions or [],
            status=acc.status.value if hasattr(acc.status, "value") else str(acc.status),
            last_validated_at=acc.last_validated_at,
            created_at=acc.created_at,
            updated_at=acc.updated_at,
        )
        for acc in accounts
    ]


@router.patch(
    "/{account_id}",
    response_model=AccountListItem,
    status_code=status.HTTP_200_OK,
    summary="Update AWS account (WriteRole)",
)
async def update_account(
    account_id: Annotated[
        str,
        Path(..., description="AWS account ID (12 digits)", pattern=r"^\d{12}$"),
    ],
    request: AccountUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> AccountListItem:
    """
    Update an AWS account. Supports updating the WriteRole ARN and/or status (stop/resume).

    - **role_write_arn**: Required for direct fixes. Set to null for administrative correction only.
    - **status**: Set to `disabled` to stop monitoring (no ingestion/remediation); set to `validated`
      to resume. Ingestion endpoints require status=validated.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AWS account {account_id} not found for tenant",
        )

    updates = request.model_dump(exclude_unset=True)
    if "role_write_arn" in updates:
        if updates["role_write_arn"] is not None:
            arn = updates["role_write_arn"]
            arn_parts = arn.split(":")
            if len(arn_parts) < 5 or arn_parts[4] != account_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"role_write_arn account ID must match account_id {account_id}",
                )
            acc.role_write_arn = arn
        else:
            acc.role_write_arn = None
    if "status" in updates:
        new_status = updates["status"]
        if new_status == "disabled":
            acc.status = AwsAccountStatus.disabled
        elif new_status == "validated":
            acc.status = AwsAccountStatus.validated
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="status must be 'disabled' or 'validated'",
            )

    await db.commit()
    await db.refresh(acc)

    return AccountListItem(
        id=str(acc.id),
        account_id=acc.account_id,
        role_read_arn=acc.role_read_arn,
        role_write_arn=acc.role_write_arn,
        regions=acc.regions or [],
        status=acc.status.value if hasattr(acc.status, "value") else str(acc.status),
        last_validated_at=acc.last_validated_at,
        created_at=acc.created_at,
        updated_at=acc.updated_at,
    )


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove AWS account",
)
async def delete_account(
    account_id: Annotated[
        str,
        Path(..., description="AWS account ID (12 digits)", pattern=r"^\d{12}$"),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> None:
    """
    Remove an AWS account from the tenant. The account record and its association
    are deleted; existing findings for this account_id remain in the database.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AWS account {account_id} not found for tenant",
        )
    await db.delete(acc)
    await db.commit()


@router.post("", response_model=AccountRegistrationResponse, status_code=status.HTTP_201_CREATED)
async def register_account(
    request: AccountRegistrationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
) -> AccountRegistrationResponse:
    """
    Register a new AWS account or update an existing one.

    This endpoint:
    1. Validates the request (account_id format, ARN format, regions)
    2. Gets the tenant from the database
    3. Creates/updates the aws_accounts record
    4. Tests the STS assume-role connection
    5. Verifies account_id matches via sts.get_caller_identity()
    6. Updates status to "validated" on success

    **Authentication:**
    - If Bearer token is provided, tenant is resolved from the token.
    - Otherwise, tenant_id in request body is required.
    """
    # Resolve tenant from auth or request
    tenant_uuid = resolve_tenant_id(current_user, request.tenant_id)

    # Get tenant and verify it exists
    tenant = await get_tenant(tenant_uuid, db)

    # Verify account_id in ARNs matches the provided account_id
    # ARN format: arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME
    for arn_name, arn_value in [("role_read_arn", request.role_read_arn), ("role_write_arn", request.role_write_arn)]:
        arn_parts = arn_value.split(":")
        if len(arn_parts) < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid {arn_name} format: {arn_value}",
            )
        if arn_parts[4] != request.account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"account_id {request.account_id} does not match the account ID in {arn_name} ({arn_parts[4]})",
            )

    # Check if account already exists for this tenant
    result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_uuid,
            AwsAccount.account_id == request.account_id,
        )
    )
    existing_account = result.scalar_one_or_none()

    # Prepare account data
    account_data = {
        "tenant_id": tenant_uuid,
        "account_id": request.account_id,
        "role_read_arn": request.role_read_arn,
        "role_write_arn": request.role_write_arn,  # Required for account connection and direct fixes
        "external_id": tenant.external_id,  # Must match tenant.external_id
        "regions": request.regions,
        "status": AwsAccountStatus.pending,
    }

    try:
        # Validate ReadRole: assume and verify account_id
        logger.info(f"Validating ReadRole for account {request.account_id}")
        read_session = assume_role(
            role_arn=request.role_read_arn,
            external_id=tenant.external_id,
        )
        sts_client = read_session.client("sts")
        identity = sts_client.get_caller_identity()
        caller_account_id = identity.get("Account")
        if caller_account_id != request.account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Account ID mismatch (ReadRole): expected {request.account_id}, got {caller_account_id}",
            )

        # Validate WriteRole: assume and verify account_id (required for direct fixes)
        logger.info(f"Validating WriteRole for account {request.account_id}")
        write_session = assume_role(
            role_arn=request.role_write_arn,
            external_id=tenant.external_id,
        )
        write_sts = write_session.client("sts")
        write_identity = write_sts.get_caller_identity()
        write_caller_account_id = write_identity.get("Account")
        if write_caller_account_id != request.account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Account ID mismatch (WriteRole): expected {request.account_id}, got {write_caller_account_id}",
            )

        # Both roles validated
        account_data["status"] = AwsAccountStatus.validated
        account_data["last_validated_at"] = datetime.now(timezone.utc)
        logger.info(f"Successfully validated account {request.account_id} (ReadRole + WriteRole) for tenant {tenant_uuid}")

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        logger.error(f"Failed to assume role for account {request.account_id}: {error_code} - {error_message}")

        # Set status to error
        account_data["status"] = AwsAccountStatus.error

        # If account doesn't exist yet, we still want to create it with error status
        # so the user can see what went wrong
        if existing_account:
            existing_account.status = AwsAccountStatus.error
            existing_account.role_read_arn = request.role_read_arn
            existing_account.role_write_arn = request.role_write_arn
            existing_account.regions = request.regions
            await db.commit()
            await db.refresh(existing_account)

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to assume role: {error_message}. Ensure (1) the backend runs with credentials from the SaaS account (SAAS_AWS_ACCOUNT_ID in .env), (2) that principal has sts:AssumeRole permission on the role, (3) the role trust policy allows your SaaS account and the ExternalId matches.",
            )

        # Create new account with error status
        new_account = AwsAccount(**account_data)
        db.add(new_account)
        await db.commit()
        await db.refresh(new_account)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to assume role: {error_message}. Ensure (1) the backend runs with credentials from the SaaS account (SAAS_AWS_ACCOUNT_ID in .env), (2) that principal has sts:AssumeRole permission on the role, (3) the role trust policy allows your SaaS account and the ExternalId matches.",
        )

    except Exception as e:
        logger.exception(f"Unexpected error during account registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during account registration",
        )

    # Create or update account
    if existing_account:
        # Update existing account
        existing_account.role_read_arn = request.role_read_arn
        existing_account.role_write_arn = request.role_write_arn
        existing_account.regions = request.regions
        existing_account.external_id = tenant.external_id
        existing_account.status = account_data["status"]
        existing_account.last_validated_at = account_data["last_validated_at"]
        await db.commit()
        await db.refresh(existing_account)

        return AccountRegistrationResponse(
            id=str(existing_account.id),
            account_id=existing_account.account_id,
            status=existing_account.status.value,
            last_validated_at=existing_account.last_validated_at,
        )
    else:
        # Create new account
        new_account = AwsAccount(**account_data)
        db.add(new_account)
        await db.commit()
        await db.refresh(new_account)

        return AccountRegistrationResponse(
            id=str(new_account.id),
            account_id=new_account.account_id,
            status=new_account.status.value,
            last_validated_at=new_account.last_validated_at,
        )


@router.post(
    "/{account_id}/validate",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate AWS account role",
    description="Re-test STS assume-role and optionally Security Hub access. Updates last_validated_at and status.",
)
async def validate_account(
    account_id: Annotated[
        str,
        Path(..., description="AWS account ID (12 digits)", pattern=r"^\d{12}$"),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> ValidationResponse:
    """
    Validate an existing AWS account.

    Looks up the account by tenant_id + account_id, calls STS assume-role with stored
    role ARN and ExternalId, verifies get_caller_identity, optionally tests Security Hub
    access, then updates last_validated_at and status.

    **Authentication:**
    - If Bearer token is provided, tenant is resolved from the token.
    - Otherwise, tenant_id query parameter is required.
    """
    # Resolve tenant from auth or request
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant(tenant_uuid, db)
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AWS account {account_id} not found for tenant",
        )

    now = datetime.now(timezone.utc)
    permissions_ok = False

    try:
        logger.info(f"Validating account {account_id} for tenant {tenant_uuid}")
        session = assume_role(
            role_arn=acc.role_read_arn,
            external_id=tenant.external_id,
        )
        sts_client = session.client("sts")
        identity = sts_client.get_caller_identity()
        caller_account_id = identity.get("Account")
        if caller_account_id != account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Account ID mismatch: expected {account_id}, got {caller_account_id}",
            )

        permissions_ok = True

        # Optionally test Security Hub access (limit 1)
        region = (acc.regions or ["us-east-1"])[0] if acc.regions else "us-east-1"
        try:
            sh = session.client("securityhub", region_name=region)
            sh.get_findings(MaxResults=1)
        except ClientError as e:
            logger.warning(f"Security Hub check failed for account {account_id}: {e}")
            permissions_ok = False

        acc.status = AwsAccountStatus.validated
        acc.last_validated_at = now
        await db.commit()
        await db.refresh(acc)
        return ValidationResponse(
            status="validated",
            account_id=acc.account_id,
            last_validated_at=acc.last_validated_at,
            permissions_ok=permissions_ok,
        )

    except HTTPException:
        raise
    except ClientError as e:
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.warning(f"Validation failed for account {account_id}: {error_message}")
        acc.status = AwsAccountStatus.error
        acc.last_validated_at = now
        await db.commit()
        await db.refresh(acc)
        return ValidationResponse(
            status="error",
            account_id=acc.account_id,
            last_validated_at=acc.last_validated_at,
            permissions_ok=False,
        )
    except Exception as e:
        logger.exception(f"Unexpected error validating account {account_id}: {e}")
        acc.status = AwsAccountStatus.error
        acc.last_validated_at = now
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during validation",
        )


@router.post(
    "/{account_id}/ingest",
    response_model=IngestTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger ingestion",
    description="Enqueue Security Hub ingestion jobs for the given account (one per region). Use optional body to restrict regions.",
    responses={
        404: {"model": IngestTriggerErrorResponse, "description": "Tenant or account not found"},
        400: {"model": IngestTriggerErrorResponse, "description": "No regions or invalid regions"},
        409: {"model": IngestTriggerErrorResponse, "description": "Account not validated"},
        503: {"model": IngestTriggerErrorResponse, "description": "Ingest queue unavailable or SQS send failed"},
    },
)
async def trigger_ingest(
    account_id: Annotated[
        str,
        Path(..., description="AWS account ID (12 digits)", pattern=r"^\d{12}$"),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    body: IngestTriggerRequest | None = Body(default=None),
) -> IngestTriggerResponse:
    """
    Trigger ingestion jobs for an AWS account.

    Resolves tenant, looks up account, determines regions (from body override or account config),
    enqueues one SQS message per region, returns 202 with message IDs. All-or-nothing enqueue.

    **Authentication:**
    - If Bearer token is provided, tenant is resolved from the token.
    - Otherwise, tenant_id query parameter is required.
    """
    if not settings.has_ingest_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Ingestion service unavailable", "detail": "Ingest queue URL not configured. Set SQS_INGEST_QUEUE_URL."},
        )
    
    # Resolve tenant from auth or request
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    
    try:
        await get_tenant(tenant_uuid, db)
    except HTTPException as e:
        if e.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Tenant not found", "detail": "No tenant found for the given ID."},
            ) from e
        raise
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Account not found", "detail": "No AWS account found with the given ID for this tenant."},
        )
    if acc.status != AwsAccountStatus.validated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "Account not validated", "detail": "Validate the AWS account connection before triggering ingestion."},
        )
    account_regions = list(acc.regions or [])
    if body and body.regions is not None:
        if not body.regions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Bad request", "detail": "regions override cannot be empty. Omit to use account regions."},
            )
        allowed = set(account_regions)
        for r in body.regions:
            if r not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Bad request", "detail": "regions must be a subset of the account's configured regions."},
                )
        regions = body.regions
    else:
        regions = account_regions
    if not regions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Bad request", "detail": "No regions configured for this account. Add regions in account settings."},
        )
    try:
        message_ids = _enqueue_ingest_jobs(tenant_uuid, account_id, regions)
    except ClientError as e:
        logger.exception("SQS send_message failed for ingest trigger: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Ingestion service unavailable", "detail": "Could not enqueue ingestion jobs. Please try again later."},
        )
    return IngestTriggerResponse(
        account_id=account_id,
        jobs_queued=len(regions),
        regions=regions,
        message_ids=message_ids,
        message="Ingestion jobs queued successfully",
    )


@router.post(
    "/{account_id}/ingest-access-analyzer",
    response_model=IngestTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger IAM Access Analyzer ingestion",
    description="Enqueue IAM Access Analyzer ingestion jobs for the given account (one per region). Step 2B.1. Requires ReadRole to have access-analyzer:ListAnalyzers, access-analyzer:ListFindings.",
    responses={
        404: {"model": IngestTriggerErrorResponse, "description": "Tenant or account not found"},
        400: {"model": IngestTriggerErrorResponse, "description": "No regions or invalid regions"},
        409: {"model": IngestTriggerErrorResponse, "description": "Account not validated"},
        503: {"model": IngestTriggerErrorResponse, "description": "Ingest queue unavailable or SQS send failed"},
    },
)
async def trigger_ingest_access_analyzer(
    account_id: Annotated[
        str,
        Path(..., description="AWS account ID (12 digits)", pattern=r"^\d{12}$"),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    body: IngestTriggerRequest | None = Body(default=None),
) -> IngestTriggerResponse:
    """
    Trigger IAM Access Analyzer ingestion jobs (Step 2B.1).

    Resolves tenant, looks up account, determines regions (from body override or account config),
    enqueues one ingest_access_analyzer message per region. Findings are stored with source='access_analyzer'.
    """
    if not settings.has_ingest_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Ingestion service unavailable", "detail": "Ingest queue URL not configured. Set SQS_INGEST_QUEUE_URL."},
        )
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    try:
        await get_tenant(tenant_uuid, db)
    except HTTPException as e:
        if e.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Tenant not found", "detail": "No tenant found for the given ID."},
            ) from e
        raise
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Account not found", "detail": "No AWS account found with the given ID for this tenant."},
        )
    if acc.status != AwsAccountStatus.validated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "Account not validated", "detail": "Validate the AWS account connection before triggering ingestion."},
        )
    account_regions = list(acc.regions or [])
    if body and body.regions is not None:
        if not body.regions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Bad request", "detail": "regions override cannot be empty. Omit to use account regions."},
            )
        allowed = set(account_regions)
        for r in body.regions:
            if r not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Bad request", "detail": "regions must be a subset of the account's configured regions."},
                )
        regions = body.regions
    else:
        regions = account_regions
    if not regions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Bad request", "detail": "No regions configured for this account. Add regions in account settings."},
        )
    try:
        message_ids = _enqueue_ingest_access_analyzer_jobs(tenant_uuid, account_id, regions)
    except ClientError as e:
        logger.exception("SQS send_message failed for ingest-access-analyzer: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Ingestion service unavailable", "detail": "Could not enqueue Access Analyzer ingestion jobs. Please try again later."},
        )
    return IngestTriggerResponse(
        account_id=account_id,
        jobs_queued=len(regions),
        regions=regions,
        message_ids=message_ids,
        message="Access Analyzer ingestion jobs queued successfully",
    )


@router.post(
    "/{account_id}/ingest-inspector",
    response_model=IngestTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Amazon Inspector v2 ingestion",
    description="Enqueue Amazon Inspector v2 (vulnerability) ingestion jobs for the given account (one per region). Step 2B.2. Requires ReadRole to have inspector2:ListFindings and optional inspector2:GetFinding.",
    responses={
        404: {"model": IngestTriggerErrorResponse, "description": "Tenant or account not found"},
        400: {"model": IngestTriggerErrorResponse, "description": "No regions or invalid regions"},
        409: {"model": IngestTriggerErrorResponse, "description": "Account not validated"},
        503: {"model": IngestTriggerErrorResponse, "description": "Ingest queue unavailable or SQS send failed"},
    },
)
async def trigger_ingest_inspector(
    account_id: Annotated[
        str,
        Path(..., description="AWS account ID (12 digits)", pattern=r"^\d{12}$"),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    body: IngestTriggerRequest | None = Body(default=None),
) -> IngestTriggerResponse:
    """
    Trigger Amazon Inspector v2 ingestion jobs (Step 2B.2).

    Resolves tenant, looks up account, determines regions (from body override or account config),
    enqueues one ingest_inspector message per region. Findings are stored with source='inspector'.
    """
    if not settings.has_ingest_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Ingestion service unavailable", "detail": "Ingest queue URL not configured. Set SQS_INGEST_QUEUE_URL."},
        )
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    try:
        await get_tenant(tenant_uuid, db)
    except HTTPException as e:
        if e.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Tenant not found", "detail": "No tenant found for the given ID."},
            ) from e
        raise
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Account not found", "detail": "No AWS account found with the given ID for this tenant."},
        )
    if acc.status != AwsAccountStatus.validated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "Account not validated", "detail": "Validate the AWS account connection before triggering ingestion."},
        )
    account_regions = list(acc.regions or [])
    if body and body.regions is not None:
        if not body.regions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Bad request", "detail": "regions override cannot be empty. Omit to use account regions."},
            )
        allowed = set(account_regions)
        for r in body.regions:
            if r not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Bad request", "detail": "regions must be a subset of the account's configured regions."},
                )
        regions = body.regions
    else:
        regions = account_regions
    if not regions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Bad request", "detail": "No regions configured for this account. Add regions in account settings."},
        )
    try:
        message_ids = _enqueue_ingest_inspector_jobs(tenant_uuid, account_id, regions)
    except ClientError as e:
        logger.exception("SQS send_message failed for ingest-inspector: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Ingestion service unavailable", "detail": "Could not enqueue Inspector ingestion jobs. Please try again later."},
        )
    return IngestTriggerResponse(
        account_id=account_id,
        jobs_queued=len(regions),
        regions=regions,
        message_ids=message_ids,
        message="Inspector ingestion jobs queued successfully",
    )


class IngestSyncResponse(BaseModel):
    """Response for synchronous ingest (local dev only)."""
    account_id: str
    regions: list[str]
    message: str


@router.post(
    "/{account_id}/ingest-sync",
    response_model=IngestSyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Run ingestion synchronously (local only)",
)
async def trigger_ingest_sync(
    account_id: Annotated[str, Path(description="AWS account ID (12 digits)")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    body: IngestTriggerRequest | None = Body(default=None),
) -> IngestSyncResponse:
    """
    Run Security Hub ingestion **synchronously** in the API process (no SQS/worker).

    **Only available when ENV=local.** Use this when the worker is not running and you want
    to populate findings for testing. Resolves tenant and regions the same way as POST .../ingest.
    """
    if not settings.is_local:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ingest-sync is only available when ENV=local",
        )
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    try:
        await get_tenant(tenant_uuid, db)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Tenant not found"},
            ) from e
        raise
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Account not found"},
        )
    if acc.status != AwsAccountStatus.validated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "Account not validated", "detail": "Validate the account first."},
        )
    regions = list(acc.regions or [])
    if body and body.regions is not None:
        if not body.regions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "regions override cannot be empty"},
            )
        allowed = set(regions)
        for r in body.regions:
            if r not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "regions must be a subset of account regions"},
                )
        regions = body.regions
    if not regions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "No regions configured for this account"},
        )
    now = datetime.now(timezone.utc).isoformat()
    from worker.jobs.ingest_findings import execute_ingest_job

    for r in regions:
        job = build_ingest_job_payload(tenant_uuid, account_id, r, now)
        await asyncio.to_thread(execute_ingest_job, job)
    return IngestSyncResponse(
        account_id=account_id,
        regions=regions,
        message="Ingestion completed. Refresh GET /api/findings to see results.",
    )


@router.get("/ping")
async def ping():
    """Health check endpoint."""
    return {"status": "ok"}
