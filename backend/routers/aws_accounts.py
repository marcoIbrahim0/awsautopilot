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
from backend.models.control_plane_event_ingest_status import ControlPlaneEventIngestStatus
from backend.models.enums import AwsAccountStatus
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.services.aws_account_cleanup import AwsCleanupError, cleanup_account_resources
from backend.services.aws_account_orchestration import (
    IngestRegionResolutionError,
    assume_and_verify_role_account,
    collect_service_readiness,
    resolve_ingest_regions,
    run_validation_probes,
    validate_registration_role_accounts,
)
from backend.services.aws import assume_role
from backend.services.cloudformation_templates import get_latest_template_version
from backend.utils.sqs import (
    build_compute_actions_job_payload,
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
    role_write_arn: str | None = Field(
        default=None,
        description="IAM role ARN for write access (optional). Provide to enable direct fixes.",
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
    def validate_role_write_arn(cls, v: str | None) -> str | None:
        """Validate WriteRole ARN format when provided."""
        if v is None:
            return v
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
        """role_write_arn account ID must match account_id when provided."""
        if not self.role_write_arn:
            return self
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
        description=(
            "True if ReadRole passed baseline permission probes for Phase 1/2 (and Security Hub). "
            "If false, see missing_permissions/warnings."
        ),
    )
    missing_permissions: list[str] = Field(
        default_factory=list,
        description="List of IAM actions that appear to be missing from the ReadRole policy (best-effort).",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal probe warnings (e.g., service disabled, no buckets found).",
    )
    required_permissions: list[str] = Field(
        default_factory=list,
        description="Required IAM actions for real-time authoritative mode safety checks.",
    )
    authoritative_mode_allowed: bool = Field(
        ...,
        description="True only when required permissions are present for authoritative control-plane mode.",
    )
    authoritative_mode_block_reasons: list[str] = Field(
        default_factory=list,
        description="Reasons authoritative mode should remain blocked for this account.",
    )


class RegionServiceReadiness(BaseModel):
    """Per-region service readiness for onboarding checks."""

    region: str = Field(..., description="AWS region")
    security_hub_enabled: bool = Field(..., description="Whether Security Hub is enabled in this region")
    aws_config_enabled: bool = Field(..., description="Whether AWS Config recording is enabled in this region")
    access_analyzer_enabled: bool = Field(..., description="Whether IAM Access Analyzer appears enabled in this region")
    inspector_enabled: bool = Field(..., description="Whether Amazon Inspector appears enabled in this region")
    security_hub_error: str | None = Field(None, description="Security Hub error detail when unavailable")
    aws_config_error: str | None = Field(None, description="AWS Config error detail when unavailable")
    access_analyzer_error: str | None = Field(None, description="Access Analyzer error detail when unavailable")
    inspector_error: str | None = Field(None, description="Inspector error detail when unavailable")


class AccountServiceReadinessResponse(BaseModel):
    """Aggregated service readiness across the account's configured regions."""

    account_id: str = Field(..., description="AWS account ID (12 digits)")
    overall_ready: bool = Field(..., description="True only when Security Hub and AWS Config are enabled in every region")
    all_security_hub_enabled: bool = Field(..., description="True when Security Hub is enabled in all configured regions")
    all_aws_config_enabled: bool = Field(..., description="True when AWS Config is enabled in all configured regions")
    all_access_analyzer_enabled: bool = Field(..., description="True when Access Analyzer appears enabled in all configured regions")
    all_inspector_enabled: bool = Field(..., description="True when Inspector appears enabled in all configured regions")
    missing_security_hub_regions: list[str] = Field(default_factory=list)
    missing_aws_config_regions: list[str] = Field(default_factory=list)
    missing_access_analyzer_regions: list[str] = Field(default_factory=list)
    missing_inspector_regions: list[str] = Field(default_factory=list)
    regions: list[RegionServiceReadiness] = Field(default_factory=list)


class OnboardingFastPathResponse(BaseModel):
    """Response for onboarding fast-path evaluation and queue trigger."""

    account_id: str = Field(..., description="AWS account ID (12 digits)")
    fast_path_triggered: bool = Field(
        ...,
        description="True when first-value ingest was queued immediately.",
    )
    triggered_at: datetime = Field(..., description="UTC timestamp when fast-path evaluation ran")
    ingest_jobs_queued: int = Field(default=0, description="Number of ingest jobs queued (one per region)")
    ingest_regions: list[str] = Field(default_factory=list, description="Regions used for fast-path ingest queueing")
    ingest_message_ids: list[str] = Field(default_factory=list, description="SQS message IDs for ingest jobs")
    compute_actions_queued: bool = Field(
        default=False,
        description="Whether a compute_actions job was queued for this account",
    )
    compute_actions_message_id: str | None = Field(
        default=None,
        description="SQS message ID for compute_actions when queued",
    )
    missing_security_hub_regions: list[str] = Field(default_factory=list)
    missing_aws_config_regions: list[str] = Field(default_factory=list)
    missing_inspector_regions: list[str] = Field(default_factory=list)
    missing_control_plane_regions: list[str] = Field(default_factory=list)
    missing_access_analyzer_regions: list[str] = Field(default_factory=list)
    message: str = Field(..., description="Human-readable status and next action guidance")


class RegionControlPlaneReadiness(BaseModel):
    """Per-region control-plane forwarding status (Phase 1 validation)."""

    region: str = Field(..., description="AWS region")
    last_event_time: datetime | None = Field(None, description="Event time (from CloudTrail) last seen for this region")
    last_intake_time: datetime | None = Field(None, description="When the SaaS intake last received an event for this region")
    is_recent: bool = Field(..., description="True if last_intake_time is within stale_after_minutes")
    age_minutes: float | None = Field(None, description="Minutes since last_intake_time; null if never seen")


class AccountControlPlaneReadinessResponse(BaseModel):
    """Control-plane forwarding readiness across the account's configured regions."""

    account_id: str = Field(..., description="AWS account ID (12 digits)")
    stale_after_minutes: int = Field(..., description="Window used for is_recent checks")
    overall_ready: bool = Field(..., description="True only when every configured region has recent events")
    missing_regions: list[str] = Field(default_factory=list, description="Regions with no recent events (never seen or stale)")
    regions: list[RegionControlPlaneReadiness] = Field(default_factory=list)


class ReadRoleUpdateRequest(BaseModel):
    """Request body for triggering an in-place CloudFormation update of the ReadRole stack."""

    stack_name: str = Field(
        default="SecurityAutopilotReadRole",
        description="Existing CloudFormation stack name for the ReadRole deployment.",
    )
    include_write_role: bool = Field(
        default=False,
        description="Whether IncludeWriteRole parameter should be true during update.",
    )


class ReadRoleUpdateResponse(BaseModel):
    """Response for ReadRole update operation."""

    account_id: str
    stack_name: str
    template_url: str
    template_version: str | None = None
    status: Literal["update_started", "already_up_to_date"]
    stack_id: str | None = None
    message: str


class ReadRoleUpdateStatusResponse(BaseModel):
    """Response for ReadRole update availability check."""

    account_id: str
    stack_name: str
    current_template_url: str | None = None
    current_template_version: str | None = None
    latest_template_url: str
    latest_template_version: str | None = None
    update_available: bool
    message: str


# Ingest trigger (POST /api/aws/accounts/{account_id}/ingest)
_REGION_PATTERN = re.compile(r"^[a-z]{2}-[a-z]+-\d+$")
_TEMPLATE_VERSION_PATTERN = re.compile(r"/(v?\d+\.\d+\.\d+)\.ya?ml$")
_AUTHORITATIVE_MODE_REQUIRED_PERMISSIONS: tuple[str, ...] = (
    "securityhub:GetFindings",
    "ec2:DescribeSecurityGroups",
    "s3:ListAllMyBuckets",
    "s3:GetBucketPublicAccessBlock",
    "s3:GetBucketPolicyStatus",
    "s3:GetBucketPolicy",
    "s3:GetBucketLocation",
    "s3:GetEncryptionConfiguration",
    "s3:GetBucketLogging",
    "s3:GetLifecycleConfiguration",
)


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


def _extract_template_version(template_url: str) -> str | None:
    """Best-effort semantic version extraction from template URL."""
    match = _TEMPLATE_VERSION_PATTERN.search((template_url or "").strip())
    if not match:
        return None
    return match.group(1)


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
    
    # Not authenticated: tenant_id fallback allowed only in local/dev.
    if not settings.is_local:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Local mode compatibility: allow tenant_id from request
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


def _enqueue_compute_actions_job(tenant_id: uuid.UUID, account_id: str) -> str:
    """Send one compute_actions job scoped to an account."""
    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    now = datetime.now(timezone.utc).isoformat()
    payload = build_compute_actions_job_payload(tenant_id, now, account_id=account_id)
    response = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    return str(response["MessageId"])


def _normalize_db_timestamp(value: datetime | None) -> datetime | None:
    """Ensure DB datetimes are timezone-aware for age comparisons."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def _missing_control_plane_regions(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    account_id: str,
    expected_regions: list[str],
    stale_after_minutes: int = 30,
) -> list[str]:
    """Return account regions with stale or missing control-plane intake status."""
    stmt = (
        select(ControlPlaneEventIngestStatus)
        .where(
            ControlPlaneEventIngestStatus.tenant_id == tenant_id,
            ControlPlaneEventIngestStatus.account_id == account_id,
            ControlPlaneEventIngestStatus.region.in_(expected_regions),
        )
    )
    rows = {row.region: row for row in (await db.execute(stmt)).scalars().all()}
    now = datetime.now(timezone.utc)
    missing: list[str] = []
    for region in expected_regions:
        row = rows.get(region)
        last_intake = _normalize_db_timestamp(getattr(row, "last_intake_time", None)) if row else None
        if not last_intake:
            missing.append(region)
            continue
        age_minutes = (now - last_intake).total_seconds() / 60.0
        if age_minutes > float(stale_after_minutes):
            missing.append(region)
    return missing


def _resolve_async_ingest_regions(
    account_regions: list[str] | None,
    body: IngestTriggerRequest | None,
) -> list[str]:
    override_regions = body.regions if body and body.regions is not None else None
    try:
        return resolve_ingest_regions(account_regions=account_regions, override_regions=override_regions)
    except IngestRegionResolutionError as exc:
        if exc.code == "override_empty":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Bad request", "detail": "regions override cannot be empty. Omit to use account regions."},
            ) from exc
        if exc.code == "override_not_subset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Bad request", "detail": "regions must be a subset of the account's configured regions."},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Bad request", "detail": "No regions configured for this account. Add regions in account settings."},
        ) from exc


def _resolve_sync_ingest_regions(
    account_regions: list[str] | None,
    body: IngestTriggerRequest | None,
) -> list[str]:
    override_regions = body.regions if body and body.regions is not None else None
    try:
        return resolve_ingest_regions(account_regions=account_regions, override_regions=override_regions)
    except IngestRegionResolutionError as exc:
        if exc.code == "override_empty":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "regions override cannot be empty"},
            ) from exc
        if exc.code == "override_not_subset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "regions must be a subset of account regions"},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "No regions configured for this account"},
        ) from exc


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
    cleanup_resources: Annotated[
        bool,
        Query(
            description=(
                "When true (default), delete Security Autopilot roles/policies in the customer AWS account "
                "before removing this account record."
            )
        ),
    ] = True,
) -> None:
    """
    Remove an AWS account from the tenant. The account record and its association
    are deleted; existing findings for this account_id remain in the database.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant(tenant_uuid, db)
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AWS account {account_id} not found for tenant",
        )
    if cleanup_resources:
        try:
            cleanup_account_resources(account=acc, external_id=tenant.external_id)
        except AwsCleanupError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Failed to clean up AWS resources for this account. "
                    f"{e} "
                    "If you need to remove the SaaS link without teardown, retry with cleanup_resources=false."
                ),
            ) from e
        except ClientError as e:
            error_message = e.response.get("Error", {}).get("Message", str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Failed to clean up AWS resources for this account. "
                    f"{error_message} "
                    "If you need to remove the SaaS link without teardown, retry with cleanup_resources=false."
                ),
            ) from e
    await db.delete(acc)
    await db.commit()


@router.post(
    "/{account_id}/read-role/update",
    response_model=ReadRoleUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update ReadRole CloudFormation stack",
)
async def update_read_role_stack(
    account_id: Annotated[
        str,
        Path(..., description="AWS account ID (12 digits)", pattern=r"^\d{12}$"),
    ],
    request: ReadRoleUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> ReadRoleUpdateResponse:
    """
    Trigger an in-place CloudFormation update for the customer's existing ReadRole stack.

    Uses the connected account ReadRole to call CloudFormation update-stack with the latest
    configured ReadRole template URL and the tenant's ExternalId/SaaSAccountId parameters.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant(tenant_uuid, db)

    if current_user is not None and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can trigger ReadRole updates.",
        )

    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AWS account {account_id} not found for tenant",
        )

    saas_account_id = (settings.SAAS_AWS_ACCOUNT_ID or "").strip()
    if not saas_account_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SAAS_AWS_ACCOUNT_ID is not configured.",
        )

    configured_template_url = (settings.CLOUDFORMATION_READ_ROLE_TEMPLATE_URL or "").strip()
    if not configured_template_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CLOUDFORMATION_READ_ROLE_TEMPLATE_URL is not configured.",
        )

    latest_template_url = get_latest_template_version(configured_template_url) or configured_template_url
    template_version = _extract_template_version(latest_template_url)
    stack_name = (request.stack_name or "").strip() or "SecurityAutopilotReadRole"
    include_write_role_value = "true" if request.include_write_role else "false"

    try:
        session = assume_role(role_arn=acc.role_read_arn, external_id=tenant.external_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to assume ReadRole for account {account_id}: {exc}",
        ) from exc

    cf_region = (
        (settings.CLOUDFORMATION_DEFAULT_REGION or "").strip()
        or (acc.regions[0] if acc.regions else "")
        or settings.AWS_REGION
    )
    cf = session.client("cloudformation", region_name=cf_region)

    try:
        response = cf.update_stack(
            StackName=stack_name,
            TemplateURL=latest_template_url,
            Parameters=[
                {"ParameterKey": "SaaSAccountId", "ParameterValue": saas_account_id},
                {"ParameterKey": "ExternalId", "ParameterValue": tenant.external_id},
                {"ParameterKey": "IncludeWriteRole", "ParameterValue": include_write_role_value},
            ],
            Capabilities=["CAPABILITY_NAMED_IAM"],
        )
        stack_id = response.get("StackId")
        return ReadRoleUpdateResponse(
            account_id=account_id,
            stack_name=stack_name,
            template_url=latest_template_url,
            template_version=template_version,
            status="update_started",
            stack_id=stack_id,
            message="ReadRole stack update started successfully.",
        )
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = str(error.get("Code", "")).strip()
        message = str(error.get("Message", "")).strip() or str(exc)
        if code == "ValidationError" and "No updates are to be performed" in message:
            return ReadRoleUpdateResponse(
                account_id=account_id,
                stack_name=stack_name,
                template_url=latest_template_url,
                template_version=template_version,
                status="already_up_to_date",
                stack_id=None,
                message="ReadRole stack is already up to date.",
            )
        if code in {"AccessDenied", "AccessDeniedException"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "ReadRole does not have CloudFormation update permissions. "
                    "Use the Launch Stack link to apply the template update in AWS Console."
                ),
            ) from exc
        if code == "ValidationError" and "does not exist" in message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"CloudFormation stack '{stack_name}' was not found in region '{cf_region}'. "
                    "Use the correct stack name or deploy the ReadRole stack first."
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update ReadRole stack: {message}",
        ) from exc


@router.get(
    "/{account_id}/read-role/update-status",
    response_model=ReadRoleUpdateStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Check ReadRole template update status",
)
async def get_read_role_update_status(
    account_id: Annotated[
        str,
        Path(..., description="AWS account ID (12 digits)", pattern=r"^\d{12}$"),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    stack_name: Annotated[str, Query(description="ReadRole stack name")] = "SecurityAutopilotReadRole",
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> ReadRoleUpdateStatusResponse:
    """Compare currently deployed ReadRole template version against latest available template."""
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant(tenant_uuid, db)

    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AWS account {account_id} not found for tenant",
        )

    configured_template_url = (settings.CLOUDFORMATION_READ_ROLE_TEMPLATE_URL or "").strip()
    if not configured_template_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CLOUDFORMATION_READ_ROLE_TEMPLATE_URL is not configured.",
        )
    latest_template_url = get_latest_template_version(configured_template_url) or configured_template_url
    latest_template_version = _extract_template_version(latest_template_url)
    resolved_stack_name = (stack_name or "").strip() or "SecurityAutopilotReadRole"

    try:
        session = assume_role(role_arn=acc.role_read_arn, external_id=tenant.external_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to assume ReadRole for account {account_id}: {exc}",
        ) from exc

    cf_region = (
        (settings.CLOUDFORMATION_DEFAULT_REGION or "").strip()
        or (acc.regions[0] if acc.regions else "")
        or settings.AWS_REGION
    )
    cf = session.client("cloudformation", region_name=cf_region)

    try:
        stacks = cf.describe_stacks(StackName=resolved_stack_name).get("Stacks", [])
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = str(error.get("Code", "")).strip()
        message = str(error.get("Message", "")).strip() or str(exc)
        if code in {"AccessDenied", "AccessDeniedException"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "ReadRole does not have CloudFormation read permissions to check template version. "
                    "Grant cloudformation:DescribeStacks or update manually in AWS Console."
                ),
            ) from exc
        if code == "ValidationError" and "does not exist" in message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CloudFormation stack '{resolved_stack_name}' was not found in region '{cf_region}'.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to check ReadRole stack status: {message}",
        ) from exc

    if not stacks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CloudFormation stack '{resolved_stack_name}' was not found in region '{cf_region}'.",
        )

    current_template_url = stacks[0].get("TemplateURL")
    current_template_version = _extract_template_version(current_template_url or "")
    update_available = (current_template_url or "").strip() != latest_template_url.strip()
    message = (
        "ReadRole update is available."
        if update_available
        else "ReadRole stack is already on the latest template version."
    )

    return ReadRoleUpdateStatusResponse(
        account_id=account_id,
        stack_name=resolved_stack_name,
        current_template_url=current_template_url,
        current_template_version=current_template_version,
        latest_template_url=latest_template_url,
        latest_template_version=latest_template_version,
        update_available=update_available,
        message=message,
    )


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

    try:
        validate_registration_role_accounts(
            account_id=request.account_id,
            role_read_arn=request.role_read_arn,
            role_write_arn=request.role_write_arn,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

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
        "role_write_arn": request.role_write_arn,
        "external_id": tenant.external_id,  # Must match tenant.external_id
        "regions": request.regions,
        "status": AwsAccountStatus.pending,
    }

    try:
        # Validate ReadRole: assume and verify account_id
        logger.info(f"Validating ReadRole for account {request.account_id}")
        assume_and_verify_role_account(
            role_arn=request.role_read_arn,
            external_id=tenant.external_id,
            account_id=request.account_id,
            role_label="ReadRole",
            assume_role_fn=assume_role,
        )

        # Validate WriteRole only when provided (optional at onboarding).
        if request.role_write_arn:
            logger.info(f"Validating WriteRole for account {request.account_id}")
            assume_and_verify_role_account(
                role_arn=request.role_write_arn,
                external_id=tenant.external_id,
                account_id=request.account_id,
                role_label="WriteRole",
                assume_role_fn=assume_role,
            )

        account_data["status"] = AwsAccountStatus.validated
        account_data["last_validated_at"] = datetime.now(timezone.utc)
        if request.role_write_arn:
            logger.info(
                f"Successfully validated account {request.account_id} (ReadRole + WriteRole) for tenant {tenant_uuid}"
            )
        else:
            logger.info(
                f"Successfully validated account {request.account_id} (ReadRole only, no WriteRole) for tenant {tenant_uuid}"
            )

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
    missing_permissions: list[str] = []
    warnings: list[str] = []

    try:
        logger.info(f"Validating account {account_id} for tenant {tenant_uuid}")
        probe_result = run_validation_probes(
            account_id=account_id,
            role_read_arn=acc.role_read_arn,
            tenant_external_id=tenant.external_id,
            configured_regions=acc.regions,
            default_region=settings.AWS_REGION or "eu-north-1",
            assume_role_fn=assume_role,
        )
        permissions_ok = probe_result.permissions_ok
        missing_permissions = probe_result.missing_permissions
        warnings = probe_result.warnings
        authoritative_mode_block_reasons: list[str] = []
        if missing_permissions:
            authoritative_mode_block_reasons.append(
                "Missing required ReadRole permissions for authoritative control-plane mode."
            )

        acc.status = AwsAccountStatus.validated
        acc.last_validated_at = now
        await db.commit()
        await db.refresh(acc)
        return ValidationResponse(
            status="validated",
            account_id=acc.account_id,
            last_validated_at=acc.last_validated_at,
            permissions_ok=permissions_ok,
            missing_permissions=missing_permissions,
            warnings=warnings,
            required_permissions=list(_AUTHORITATIVE_MODE_REQUIRED_PERMISSIONS),
            authoritative_mode_allowed=len(authoritative_mode_block_reasons) == 0,
            authoritative_mode_block_reasons=authoritative_mode_block_reasons,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
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
            missing_permissions=[],
            warnings=[],
            required_permissions=list(_AUTHORITATIVE_MODE_REQUIRED_PERMISSIONS),
            authoritative_mode_allowed=False,
            authoritative_mode_block_reasons=["ReadRole validation failed; authoritative mode is blocked."],
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
    "/{account_id}/service-readiness",
    response_model=AccountServiceReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Check Security Hub + AWS Config readiness",
    description="Checks whether Security Hub and AWS Config are enabled in each configured account region.",
)
async def check_account_service_readiness(
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
) -> AccountServiceReadinessResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant(tenant_uuid, db)
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AWS account {account_id} not found for tenant",
        )

    try:
        summary = await collect_service_readiness(
            db=db,
            tenant_id=tenant_uuid,
            account_id=account_id,
            role_read_arn=acc.role_read_arn,
            tenant_external_id=tenant.external_id,
            regions=acc.regions,
            default_region=settings.AWS_REGION or "eu-north-1",
            assume_role_fn=assume_role,
        )
        return AccountServiceReadinessResponse(
            account_id=account_id,
            overall_ready=summary.all_security_hub_enabled and summary.all_aws_config_enabled,
            all_security_hub_enabled=summary.all_security_hub_enabled,
            all_aws_config_enabled=summary.all_aws_config_enabled,
            all_access_analyzer_enabled=summary.all_access_analyzer_enabled,
            all_inspector_enabled=summary.all_inspector_enabled,
            missing_security_hub_regions=summary.missing_security_hub_regions,
            missing_aws_config_regions=summary.missing_aws_config_regions,
            missing_access_analyzer_regions=summary.missing_access_analyzer_regions,
            missing_inspector_regions=summary.missing_inspector_regions,
            regions=[
                RegionServiceReadiness(
                    region=item.region,
                    security_hub_enabled=item.security_hub_enabled,
                    aws_config_enabled=item.aws_config_enabled,
                    access_analyzer_enabled=item.access_analyzer_enabled,
                    inspector_enabled=item.inspector_enabled,
                    security_hub_error=item.security_hub_error,
                    aws_config_error=item.aws_config_error,
                    access_analyzer_error=item.access_analyzer_error,
                    inspector_error=item.inspector_error,
                )
                for item in summary.regions
            ],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except HTTPException:
        raise
    except ClientError as e:
        error_message = e.response.get("Error", {}).get("Message", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to check service readiness: {error_message}",
        )
    except Exception as e:
        logger.exception("Unexpected readiness check error for account %s: %s", account_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while checking Security Hub and AWS Config readiness",
        )


@router.post(
    "/{account_id}/onboarding-fast-path",
    response_model=OnboardingFastPathResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger onboarding first-value fast path",
    description=(
        "Evaluates readiness and, when safe, queues first ingest + action computation early. "
        "Required security gates still block onboarding completion."
    ),
    responses={
        404: {"description": "Tenant or account not found"},
        409: {"description": "Account not validated"},
        503: {"description": "Ingest queue unavailable"},
    },
)
async def trigger_onboarding_fast_path(
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
) -> OnboardingFastPathResponse:
    if not settings.has_ingest_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingest queue URL not configured. Set SQS_INGEST_QUEUE_URL.",
        )

    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant(tenant_uuid, db)
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AWS account {account_id} not found for tenant",
        )
    if acc.status != AwsAccountStatus.validated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Validate the AWS account connection before starting fast path.",
        )

    try:
        summary = await collect_service_readiness(
            db=db,
            tenant_id=tenant_uuid,
            account_id=account_id,
            role_read_arn=acc.role_read_arn,
            tenant_external_id=tenant.external_id,
            regions=acc.regions,
            default_region=settings.AWS_REGION or "eu-north-1",
            assume_role_fn=assume_role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ClientError as exc:
        error_message = exc.response.get("Error", {}).get("Message", str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to evaluate fast-path readiness: {error_message}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected onboarding fast-path readiness error for account %s: %s", account_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while evaluating fast-path readiness",
        ) from exc
    expected_regions = [region for region in (acc.regions or []) if region] or [settings.AWS_REGION or "eu-north-1"]
    missing_control_plane_regions = await _missing_control_plane_regions(
        db,
        tenant_uuid,
        account_id,
        expected_regions,
        stale_after_minutes=30,
    )

    safe_to_trigger = len(summary.missing_security_hub_regions) == 0 and len(summary.missing_aws_config_regions) == 0
    triggered_at = datetime.now(timezone.utc)
    ingest_message_ids: list[str] = []
    compute_actions_queued = False
    compute_actions_message_id: str | None = None

    if safe_to_trigger:
        try:
            ingest_message_ids = _enqueue_ingest_jobs(tenant_uuid, account_id, expected_regions)
        except ClientError as exc:
            logger.exception("SQS send_message failed for onboarding fast-path ingest: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not enqueue fast-path ingest jobs. Please try again later.",
            ) from exc

        try:
            compute_actions_message_id = _enqueue_compute_actions_job(tenant_uuid, account_id)
            compute_actions_queued = True
        except ClientError as exc:
            logger.warning("SQS send_message failed for onboarding fast-path compute_actions: %s", exc)

    pending_required_gates: list[str] = []
    if summary.missing_inspector_regions:
        pending_required_gates.append("Inspector")
    if summary.missing_security_hub_regions:
        pending_required_gates.append("Security Hub")
    if summary.missing_aws_config_regions:
        pending_required_gates.append("AWS Config")
    if missing_control_plane_regions:
        pending_required_gates.append("Control-plane forwarder")

    if safe_to_trigger:
        message = "First-value fast path started: initial ingest queued."
        if pending_required_gates:
            message += f" Required onboarding gates still pending: {', '.join(pending_required_gates)}."
    else:
        message = "Fast path deferred until Security Hub and AWS Config are enabled in all monitored regions."
        if pending_required_gates:
            message += f" Pending required gates: {', '.join(pending_required_gates)}."

    return OnboardingFastPathResponse(
        account_id=account_id,
        fast_path_triggered=safe_to_trigger,
        triggered_at=triggered_at,
        ingest_jobs_queued=len(ingest_message_ids),
        ingest_regions=expected_regions if safe_to_trigger else [],
        ingest_message_ids=ingest_message_ids,
        compute_actions_queued=compute_actions_queued,
        compute_actions_message_id=compute_actions_message_id,
        missing_security_hub_regions=summary.missing_security_hub_regions,
        missing_aws_config_regions=summary.missing_aws_config_regions,
        missing_inspector_regions=summary.missing_inspector_regions,
        missing_control_plane_regions=missing_control_plane_regions,
        missing_access_analyzer_regions=summary.missing_access_analyzer_regions,
        message=message,
    )


@router.get(
    "/{account_id}/control-plane-readiness",
    response_model=AccountControlPlaneReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Check control-plane event forwarding readiness",
    description=(
        "Checks whether the SaaS has recently received allowlisted control-plane events for each "
        "configured region of the account. Intended for Phase 1 validation."
    ),
)
async def check_account_control_plane_readiness(
    account_id: Annotated[
        str,
        Path(..., description="AWS account ID (12 digits)", pattern=r"^\d{12}$"),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    stale_after_minutes: Annotated[
        int,
        Query(description="Region is considered ready if last_intake_time is within this many minutes.", ge=1, le=1440),
    ] = 30,
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> AccountControlPlaneReadinessResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AWS account {account_id} not found for tenant",
        )

    expected_regions = acc.regions or [settings.AWS_REGION]
    stmt = (
        select(ControlPlaneEventIngestStatus)
        .where(
            ControlPlaneEventIngestStatus.tenant_id == tenant_uuid,
            ControlPlaneEventIngestStatus.account_id == account_id,
            ControlPlaneEventIngestStatus.region.in_(expected_regions),
        )
    )
    result = await db.execute(stmt)
    rows = {row.region: row for row in result.scalars().all()}

    now = datetime.now(timezone.utc)
    missing: list[str] = []
    region_items: list[RegionControlPlaneReadiness] = []

    for region in expected_regions:
        row = rows.get(region)
        last_event = getattr(row, "last_event_time", None) if row else None
        last_intake = getattr(row, "last_intake_time", None) if row else None
        if not last_intake:
            missing.append(region)
            region_items.append(
                RegionControlPlaneReadiness(
                    region=region,
                    last_event_time=last_event,
                    last_intake_time=last_intake,
                    is_recent=False,
                    age_minutes=None,
                )
            )
            continue

        age = (now - last_intake).total_seconds() / 60.0
        is_recent = age <= float(stale_after_minutes)
        if not is_recent:
            missing.append(region)
        region_items.append(
            RegionControlPlaneReadiness(
                region=region,
                last_event_time=last_event,
                last_intake_time=last_intake,
                is_recent=is_recent,
                age_minutes=round(age, 2),
            )
        )

    return AccountControlPlaneReadinessResponse(
        account_id=account_id,
        stale_after_minutes=stale_after_minutes,
        overall_ready=len(missing) == 0,
        missing_regions=missing,
        regions=region_items,
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
    regions = _resolve_async_ingest_regions(acc.regions, body)
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
    regions = _resolve_async_ingest_regions(acc.regions, body)
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
    regions = _resolve_async_ingest_regions(acc.regions, body)
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
    regions = _resolve_sync_ingest_regions(acc.regions, body)
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
