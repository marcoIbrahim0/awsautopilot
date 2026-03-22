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
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.aws_account import AwsAccount
from backend.models.finding import Finding
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
from backend.services.aws import (
    API_ASSUME_ROLE_SOURCE_IDENTITY,
    assume_role,
    build_assume_role_tags,
)
from backend.services.aws_config_probe import CONFIG_COMPLIANCE_SUMMARY_PERMISSION
from backend.services.cloudformation_templates import (
    build_cloudformation_parameter_list,
    build_role_template_parameter_values,
    generate_presigned_template_url,
    get_latest_template_version,
)
from backend.services.control_plane_intake import is_supported_control_plane_event
from backend.utils.sqs import (
    build_ingest_control_plane_events_job_payload,
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


def _validate_regions_list(v: list[str]) -> list[str]:
    """Validate regions list: 1-5 items, valid region names."""
    if not v:
        raise ValueError("regions list cannot be empty. Provide at least one AWS region (e.g., ['us-east-1'])")
    if len(v) > 5:
        raise ValueError("At most 5 regions allowed. Provide 1 to 5 AWS regions.")
    region_pattern = r"^[a-z]{2}-[a-z]+-\d+$"
    for region in v:
        if not re.match(region_pattern, region):
            raise ValueError(f"Invalid region format: {region}. Expected format: us-east-1, eu-west-1, etc.")
    return v


def _assume_role_failure_detail(error_message: str) -> str:
    return (
        f"Failed to assume role: {error_message}. Ensure (1) the backend runs with credentials "
        "from the SaaS account (SAAS_AWS_ACCOUNT_ID in backend/.env for local runs, or as process "
        "environment in deployed runtime), (2) that principal has sts:AssumeRole permission on the "
        "role, (3) the role trust policy allows your configured SaaS execution role "
        "(or the temporary SaaS account fallback) and the ExternalId matches."
    )


def _api_assume_role_tags(tenant_id: uuid.UUID) -> list[dict[str, str]]:
    return build_assume_role_tags(service_component="api", tenant_id=tenant_id)


def _read_role_template_parameter_values(external_id: str) -> dict[str, str]:
    return build_role_template_parameter_values(
        external_id=external_id,
        saas_account_id=(settings.SAAS_AWS_ACCOUNT_ID or "").strip(),
        saas_execution_role_arns=settings.saas_execution_role_arns_csv,
    )


def _set_account_status(acc: AwsAccount, new_status: Literal["disabled", "validated"]) -> None:
    if new_status == "disabled":
        acc.status = AwsAccountStatus.disabled
        return
    if new_status == "validated":
        acc.status = AwsAccountStatus.validated
        return
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be 'disabled' or 'validated'")


def _update_requires_revalidation(updates: dict[str, object]) -> bool:
    return any(field in updates for field in ("role_read_arn", "regions"))


def _update_validates_write_role(updates: dict[str, object]) -> bool:
    return False


class AccountRegistrationRequest(BaseModel):
    """Request model for registering an AWS account."""

    account_id: str = Field(..., description="AWS account ID (12 digits)")
    role_read_arn: str = Field(..., description="IAM role ARN for read access (ingestion)")
    role_write_arn: str | None = Field(
        default=None,
        description=(
            "Deprecated out-of-scope field retained for backward compatibility. "
            "WriteRole is not used by the currently supported PR-bundle workflow."
        ),
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
        """Ignore deprecated WriteRole input while the field stays out of scope."""
        return None

    @field_validator("regions")
    @classmethod
    def validate_regions(cls, v: list[str]) -> list[str]:
        return _validate_regions_list(v)

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
        """WriteRole is out of scope; clear any supplied value after validation."""
        self.role_write_arn = None
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
    """Request model for PATCH /aws/accounts/{account_id}."""

    role_read_arn: str | None = Field(
        default=None,
        description="ReadRole ARN to revalidate or replace.",
    )
    role_write_arn: str | None = Field(
        default=None,
        description=(
            "Deprecated out-of-scope field retained for backward compatibility. "
            "Updates to WriteRole do not enable any active remediation path."
        ),
    )
    regions: list[str] | None = Field(
        default=None,
        description="List of AWS regions to monitor.",
    )
    status: Literal["disabled", "validated"] | None = Field(
        default=None,
        description="Set to 'disabled' to stop monitoring, or 'validated' to resume.",
    )

    @field_validator("role_read_arn")
    @classmethod
    def validate_role_read_arn_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_role_arn_format(v, "role_read_arn")

    @field_validator("role_write_arn")
    @classmethod
    def validate_role_write_arn_format(cls, v: str | None) -> str | None:
        return None

    @field_validator("regions")
    @classmethod
    def validate_regions(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        return _validate_regions_list(v)


class ValidationResponse(BaseModel):
    """Response model for account validation."""

    status: str = Field(..., description="validated or error")
    account_id: str = Field(..., description="AWS account ID (12 digits)")
    last_validated_at: datetime | None = Field(None, description="When validation last ran")
    permissions_ok: bool = Field(
        ...,
        description=(
            "True if ReadRole passed baseline permission probes for Phase 1/2 (and Security Hub). "
            "If false, see missing_permissions/warnings/authoritative_mode_block_reasons."
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


class ControlPlaneSyntheticEventResponse(BaseModel):
    """Synthetic control-plane intake trigger result."""

    enqueued: int = Field(..., description="Number of events enqueued")
    dropped: int = Field(..., description="Number of events dropped")
    drop_reasons: dict[str, int] = Field(default_factory=dict, description="Drop reason counters")


class ReadRoleUpdateRequest(BaseModel):
    """Request body for triggering an in-place CloudFormation update of the ReadRole stack."""

    stack_name: str = Field(
        default="SecurityAutopilotReadRole",
        description="Existing CloudFormation stack name for the ReadRole deployment.",
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
    "config:DescribeConfigurationRecorders",
    "config:DescribeDeliveryChannels",
    "config:DescribeConfigRules",
    CONFIG_COMPLIANCE_SUMMARY_PERMISSION,
    "config:GetComplianceDetailsByConfigRule",
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


class IngestProgressResponse(BaseModel):
    """Progress snapshot for an ingest request started by the UI."""

    account_id: str = Field(..., description="AWS account ID (12 digits)")
    source: Literal["security_hub", "access_analyzer", "inspector"] | None = Field(
        default=None,
        description="Optional source filter used for this progress query.",
    )
    started_after: datetime = Field(..., description="Client-provided refresh start timestamp (UTC).")
    elapsed_seconds: int = Field(..., description="Elapsed seconds since started_after.")
    status: Literal["queued", "running", "completed", "no_changes_detected"] = Field(
        ...,
        description="Current ingest progress state for this account/source window.",
    )
    progress: int = Field(..., ge=0, le=100, description="UI progress value (0-100).")
    percent_complete: int = Field(
        ...,
        ge=0,
        le=100,
        description="Backward-compatible alias for progress (0-100).",
    )
    estimated_time_remaining: int | None = Field(
        default=None,
        ge=0,
        description="Estimated seconds remaining until terminal state; null when unknown.",
    )
    updated_findings_count: int = Field(..., description="Number of findings updated since started_after.")
    last_finding_update_at: datetime | None = Field(
        default=None,
        description="Most recent Finding.updated_at in the monitored window.",
    )
    message: str = Field(..., description="Human-readable progress guidance.")


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


def _build_synthetic_control_plane_event(account_id: str, region: str, now: datetime) -> dict[str, object]:
    event_id = f"synthetic-{uuid.uuid4()}"
    event_time = now.isoformat()
    return {
        "id": event_id,
        "time": event_time,
        "account": account_id,
        "region": region,
        "source": "security.autopilot.synthetic",
        "detail-type": "AWS API Call via CloudTrail",
        "detail": {
            "eventName": "AuthorizeSecurityGroupIngress",
            "eventTime": event_time,
            "eventID": f"synthetic-detail-{uuid.uuid4()}",
            "userIdentity": {"accountId": account_id},
            "awsRegion": region,
            "eventCategory": "Management",
        },
    }


def _enqueue_control_plane_event(
    tenant_id: uuid.UUID,
    account_id: str,
    region: str,
    event: dict[str, object],
    event_id: str,
    event_time: str,
    intake_time: str,
) -> None:
    queue_url = (settings.SQS_EVENTS_FAST_LANE_QUEUE_URL or "").strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    payload = build_ingest_control_plane_events_job_payload(
        tenant_id=tenant_id,
        account_id=account_id,
        region=region,
        event=event,
        event_id=event_id,
        event_time=event_time,
        intake_time=intake_time,
        created_at=intake_time,
    )
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))


async def _upsert_control_plane_status(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    account_id: str,
    region: str,
    event_time: datetime,
    intake_time: datetime,
) -> None:
    upsert = (
        insert(ControlPlaneEventIngestStatus)
        .values(
            tenant_id=tenant_id,
            account_id=account_id,
            region=region,
            last_event_time=event_time,
            last_intake_time=intake_time,
        )
        .on_conflict_do_update(
            index_elements=["tenant_id", "account_id", "region"],
            set_={
                "last_event_time": event_time,
                "last_intake_time": intake_time,
                "updated_at": func.now(),
            },
        )
    )
    await db.execute(upsert)


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
    # Deprecated/out-of-scope field retained for backward compatibility.
    role_write_arn: str | None
    regions: list[str]
    status: str
    last_validated_at: datetime | None
    last_synced_at: datetime | None = None
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
    account_ids = [acc.account_id for acc in accounts]
    last_synced_at_by_account: dict[str, datetime | None] = {}
    if account_ids:
        freshness_result = await db.execute(
            select(Finding.account_id, func.max(Finding.updated_at))
            .where(
                Finding.tenant_id == tenant.id,
                Finding.account_id.in_(account_ids),
            )
            .group_by(Finding.account_id)
        )
        last_synced_at_by_account = {
            str(account_id): last_synced_at
            for account_id, last_synced_at in freshness_result.all()
        }

    # Convert to response
    return [
        AccountListItem(
            id=str(acc.id),
            account_id=acc.account_id,
            role_read_arn=acc.role_read_arn,
            role_write_arn=None,
            regions=acc.regions or [],
            status=acc.status.value if hasattr(acc.status, "value") else str(acc.status),
            last_validated_at=acc.last_validated_at,
            last_synced_at=last_synced_at_by_account.get(acc.account_id),
            created_at=acc.created_at,
            updated_at=acc.updated_at,
        )
        for acc in accounts
    ]


@router.patch(
    "/{account_id}",
    response_model=AccountListItem,
    status_code=status.HTTP_200_OK,
    summary="Update AWS account",
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
    Update an AWS account.

    - **role_read_arn**: Revalidate or replace the stored ReadRole ARN.
    - **regions**: Replace the monitored AWS region list.
    - **role_write_arn**: Deprecated/out-of-scope. Retained only for backward compatibility.
    - **status**: Set to `disabled` to stop monitoring (no ingestion/remediation); set to `validated`
      to resume. Ingestion endpoints require status=validated.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant(tenant_uuid, db)
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AWS account {account_id} not found for tenant",
        )

    updates = request.model_dump(exclude_unset=True)
    if not updates:
        return AccountListItem(
            id=str(acc.id),
            account_id=acc.account_id,
            role_read_arn=acc.role_read_arn,
            role_write_arn=None,
            regions=acc.regions or [],
            status=acc.status.value if hasattr(acc.status, "value") else str(acc.status),
            last_validated_at=acc.last_validated_at,
            last_synced_at=None,
            created_at=acc.created_at,
            updated_at=acc.updated_at,
        )

    if "role_read_arn" in updates and updates["role_read_arn"] is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role_read_arn cannot be null")
    if "regions" in updates and updates["regions"] is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="regions cannot be null")

    next_role_read_arn = updates["role_read_arn"] if "role_read_arn" in updates else acc.role_read_arn
    next_role_write_arn = None if "role_write_arn" in updates else acc.role_write_arn
    next_regions = list(updates["regions"] if "regions" in updates else (acc.regions or []))

    try:
        validate_registration_role_accounts(
            account_id=account_id,
            role_read_arn=next_role_read_arn,
            role_write_arn=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if _update_requires_revalidation(updates):
        try:
            assume_and_verify_role_account(
                role_arn=next_role_read_arn,
                external_id=tenant.external_id,
                account_id=account_id,
                role_label="ReadRole",
                assume_role_fn=assume_role,
                source_identity=API_ASSUME_ROLE_SOURCE_IDENTITY,
                tags=_api_assume_role_tags(tenant_uuid),
            )
            if _update_validates_write_role(updates):
                assume_and_verify_role_account(
                    role_arn=str(next_role_write_arn),
                    external_id=tenant.external_id,
                    account_id=account_id,
                    role_label="WriteRole",
                    assume_role_fn=assume_role,
                    source_identity=API_ASSUME_ROLE_SOURCE_IDENTITY,
                    tags=_api_assume_role_tags(tenant_uuid),
                )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except ClientError as exc:
            error_message = exc.response.get("Error", {}).get("Message", str(exc))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_assume_role_failure_detail(error_message),
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error updating account %s: %s", account_id, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during account update",
            ) from exc

        acc.role_read_arn = next_role_read_arn
        acc.regions = next_regions
        if "role_write_arn" in updates:
            acc.role_write_arn = None
        acc.last_validated_at = datetime.now(timezone.utc)
        if acc.status != AwsAccountStatus.disabled:
            acc.status = AwsAccountStatus.validated
    elif "role_write_arn" in updates:
        acc.role_write_arn = None

    if "status" in updates:
        _set_account_status(acc, updates["status"])

    await db.commit()
    await db.refresh(acc)

    return AccountListItem(
        id=str(acc.id),
        account_id=acc.account_id,
        role_read_arn=acc.role_read_arn,
        role_write_arn=None,
        regions=acc.regions or [],
        status=acc.status.value if hasattr(acc.status, "value") else str(acc.status),
        last_validated_at=acc.last_validated_at,
        last_synced_at=None,
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
                "When true, delete Security Autopilot IAM resources in the customer account before "
                "removing this record. Default false; prefer customer-initiated CloudFormation stack "
                "deletion instead."
            )
        ),
    ] = False,
) -> None:
    """
    Remove an AWS account from the tenant. The account record and its association
    are deleted; existing findings for this account_id remain in the database.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    current_role = getattr(current_user.role, "value", current_user.role)
    if current_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete AWS accounts",
        )

    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant(tenant_uuid, db)
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AWS account {account_id} not found for tenant",
        )
    if cleanup_resources:
        if not settings.ALLOW_RUNTIME_IAM_CLEANUP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Runtime IAM cleanup is not enabled. Ask the customer to delete the "
                    "SecurityAutopilotReadRole CloudFormation stack in their AWS Console, then retry "
                    "with cleanup_resources=false."
                ),
            )
        try:
            cleanup_account_resources(
                account=acc,
                external_id=tenant.external_id,
                _authorized=True,
            )
        except AwsCleanupError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Failed to clean up AWS resources for this account. "
                    f"{e} "
                    "If you only need to remove the SaaS link, retry with cleanup_resources=false."
                ),
            ) from e
        except ClientError as e:
            error_message = e.response.get("Error", {}).get("Message", str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Failed to clean up AWS resources for this account. "
                    f"{error_message} "
                    "If you only need to remove the SaaS link, retry with cleanup_resources=false."
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
            detail=(
                "SAAS_AWS_ACCOUNT_ID is not configured. "
                "Set it in backend/.env for local runs or as a process environment variable in deployed runtime."
            ),
        )

    configured_template_url = (settings.CLOUDFORMATION_READ_ROLE_TEMPLATE_URL or "").strip()
    if not configured_template_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CLOUDFORMATION_READ_ROLE_TEMPLATE_URL is not configured.",
        )

    latest_template_url = get_latest_template_version(configured_template_url) or configured_template_url
    # CloudFormation update_stack requires an S3-domain TemplateURL; generate a pre-signed URL.
    presigned_template_url = generate_presigned_template_url(latest_template_url) or latest_template_url
    template_version = _extract_template_version(latest_template_url)
    stack_name = (request.stack_name or "").strip() or "SecurityAutopilotReadRole"
    parameter_values = _read_role_template_parameter_values(tenant.external_id)

    try:
        session = assume_role(
            role_arn=acc.role_read_arn,
            external_id=tenant.external_id,
            source_identity=API_ASSUME_ROLE_SOURCE_IDENTITY,
            tags=_api_assume_role_tags(tenant_uuid),
        )
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
            TemplateURL=presigned_template_url,
            Parameters=build_cloudformation_parameter_list(parameter_values),
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
        session = assume_role(
            role_arn=acc.role_read_arn,
            external_id=tenant.external_id,
            source_identity=API_ASSUME_ROLE_SOURCE_IDENTITY,
            tags=_api_assume_role_tags(tenant_uuid),
        )
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
    Register a new AWS account.

    This endpoint:
    1. Validates the request (account_id format, ARN format, regions)
    2. Gets the tenant from the database
    3. Creates the aws_accounts record
    4. Tests the STS assume-role connection
    5. Verifies account_id matches via sts.get_caller_identity()
    6. Updates status to "validated" on success

    **Authentication:**
    - If Bearer token is provided, tenant is resolved from the token.
    - Otherwise, tenant_id in request body is required.
    """
    # Register is auth-required. Do not allow tenant_id fallback for unauthenticated callers.
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Resolve tenant from auth context.
    tenant_uuid = resolve_tenant_id(current_user, request.tenant_id)

    # Get tenant and verify it exists
    tenant = await get_tenant(tenant_uuid, db)

    try:
        validate_registration_role_accounts(
            account_id=request.account_id,
            role_read_arn=request.role_read_arn,
            role_write_arn=None,
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
    if existing_account:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Account already connected",
                "detail": f"AWS account {request.account_id} is already connected for this tenant.",
            },
        )

    # Prepare account data
    account_data = {
        "tenant_id": tenant_uuid,
        "account_id": request.account_id,
        "role_read_arn": request.role_read_arn,
        "role_write_arn": None,
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
            source_identity=API_ASSUME_ROLE_SOURCE_IDENTITY,
            tags=_api_assume_role_tags(tenant_uuid),
        )

        account_data["status"] = AwsAccountStatus.validated
        account_data["last_validated_at"] = datetime.now(timezone.utc)
        logger.info(
            "Successfully validated account %s (ReadRole only; WriteRole out of scope) for tenant %s",
            request.account_id,
            tenant_uuid,
        )

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        logger.error(f"Failed to assume role for account {request.account_id}: {error_code} - {error_message}")

        # Set status to error
        account_data["status"] = AwsAccountStatus.error

        # Create new account with error status
        new_account = AwsAccount(**account_data)
        db.add(new_account)
        await db.commit()
        await db.refresh(new_account)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_assume_role_failure_detail(error_message),
        )

    except Exception as e:
        logger.exception(f"Unexpected error during account registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during account registration",
        )

    # Create new account
    new_account = AwsAccount(**account_data)
    db.add(new_account)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Account already connected",
                "detail": f"AWS account {request.account_id} is already connected for this tenant.",
            },
        )
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
            source_identity=API_ASSUME_ROLE_SOURCE_IDENTITY,
            tags=_api_assume_role_tags(tenant_uuid),
        )
        permissions_ok = probe_result.permissions_ok
        missing_permissions = probe_result.missing_permissions
        warnings = probe_result.warnings
        authoritative_mode_block_reasons = list(probe_result.block_reasons)
        authoritative_mode_block_reasons.extend(
            f"Missing required ReadRole permission: {permission}" for permission in missing_permissions
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
            source_identity=API_ASSUME_ROLE_SOURCE_IDENTITY,
            tags=_api_assume_role_tags(tenant_uuid),
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
            source_identity=API_ASSUME_ROLE_SOURCE_IDENTITY,
            tags=_api_assume_role_tags(tenant_uuid),
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
    "/{account_id}/control-plane-synthetic-event",
    response_model=ControlPlaneSyntheticEventResponse,
    status_code=status.HTTP_200_OK,
    summary="Send synthetic allowlisted control-plane event",
    description=(
        "Queues a synthetic allowlisted management event for this account/region to validate "
        "control-plane intake readiness during onboarding."
    ),
)
async def send_control_plane_synthetic_event(
    account_id: Annotated[
        str,
        Path(..., description="AWS account ID (12 digits)", pattern=r"^\d{12}$"),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    region: Annotated[
        Optional[str],
        Query(description="Target monitored region. Defaults to first account region."),
    ] = None,
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> ControlPlaneSyntheticEventResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AWS account {account_id} not found for tenant")

    configured_regions = [r for r in (acc.regions or []) if r]
    fallback_region = settings.AWS_REGION or "eu-north-1"
    target_region = (region or (configured_regions[0] if configured_regions else fallback_region)).strip()
    if configured_regions and target_region not in configured_regions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="region must be one of account configured regions")

    queue_url = (settings.SQS_EVENTS_FAST_LANE_QUEUE_URL or "").strip()
    if not queue_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Events fast-lane queue URL not configured. Set SQS_EVENTS_FAST_LANE_QUEUE_URL.",
        )

    now = datetime.now(timezone.utc)
    event = _build_synthetic_control_plane_event(account_id, target_region, now)
    supported, reason = is_supported_control_plane_event(event)
    if not supported:
        return ControlPlaneSyntheticEventResponse(enqueued=0, dropped=1, drop_reasons={reason or "unsupported": 1})

    event_id = str(event.get("id") or "").strip() or f"synthetic-{uuid.uuid4()}"
    event_time = str(event.get("time") or "").strip() or now.isoformat()
    intake_time = now.isoformat()
    try:
        _enqueue_control_plane_event(tenant_uuid, account_id, target_region, event, event_id, event_time, intake_time)
        await _upsert_control_plane_status(db, tenant_uuid, account_id, target_region, now, now)
        await db.commit()
    except Exception as exc:
        logger.exception("Failed to enqueue synthetic control-plane event: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to enqueue synthetic control-plane event.",
        ) from exc

    return ControlPlaneSyntheticEventResponse(enqueued=1, dropped=0, drop_reasons={})


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


@router.get(
    "/{account_id}/ingest-progress",
    response_model=IngestProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Check ingest progress for notification center tracking",
    description=(
        "Returns a lightweight progress snapshot by checking findings updated after "
        "the provided start timestamp."
    ),
)
async def get_ingest_progress(
    account_id: Annotated[
        str,
        Path(..., description="AWS account ID (12 digits)", pattern=r"^\d{12}$"),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    started_after: Annotated[
        datetime,
        Query(description="UTC timestamp when the refresh request started."),
    ],
    source: Annotated[
        Literal["security_hub", "access_analyzer", "inspector"] | None,
        Query(description="Optional ingest source filter."),
    ] = None,
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> IngestProgressResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    acc = await get_account_for_tenant(tenant_uuid, account_id, db)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Account not found", "detail": "No AWS account found with the given ID for this tenant."},
        )

    if started_after.tzinfo is None:
        started_after = started_after.replace(tzinfo=timezone.utc)

    stmt = (
        select(func.count(Finding.id), func.max(Finding.updated_at))
        .where(
            Finding.tenant_id == tenant_uuid,
            Finding.account_id == account_id,
            Finding.updated_at >= started_after,
        )
    )
    if source:
        stmt = stmt.where(Finding.source == source)

    result = await db.execute(stmt)
    updated_count_raw, last_updated = result.one()
    updated_count = int(updated_count_raw or 0)

    now = datetime.now(timezone.utc)
    elapsed_seconds = max(0, int((now - started_after).total_seconds()))

    if updated_count > 0:
        return IngestProgressResponse(
            account_id=account_id,
            source=source,
            started_after=started_after,
            elapsed_seconds=elapsed_seconds,
            status="completed",
            progress=100,
            percent_complete=100,
            estimated_time_remaining=0,
            updated_findings_count=updated_count,
            last_finding_update_at=last_updated,
            message="Refresh completed. Findings were updated.",
        )

    if elapsed_seconds < 20:
        status_value: Literal["queued", "running", "completed", "no_changes_detected"] = "queued"
        progress_value = min(25, 8 + elapsed_seconds)
        message = "Refresh queued. Waiting for worker pickup."
    elif elapsed_seconds < 120:
        status_value = "running"
        progress_value = min(90, 25 + int((elapsed_seconds - 20) * 0.6))
        message = "Refresh is processing in the background."
    else:
        status_value = "no_changes_detected"
        progress_value = 100
        message = "No finding updates detected for this refresh window yet."
    eta_seconds = 0 if status_value in {"completed", "no_changes_detected"} else max(0, 120 - elapsed_seconds)

    return IngestProgressResponse(
        account_id=account_id,
        source=source,
        started_after=started_after,
        elapsed_seconds=elapsed_seconds,
        status=status_value,
        progress=progress_value,
        percent_complete=progress_value,
        estimated_time_remaining=eta_seconds,
        updated_findings_count=updated_count,
        last_finding_update_at=last_updated,
        message=message,
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
    summary="Run ingestion synchronously (local) with async fallback elsewhere",
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
    Run Security Hub ingestion synchronously in local development, or queue
    asynchronous ingest jobs in non-local environments.
    """
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

    # Sync mode is strictly local-only and only when no queue is configured.
    # If queue wiring exists, prefer async enqueue to avoid importing worker-only deps in API runtime.
    should_run_sync_locally = settings.is_local and not settings.has_ingest_queue
    if should_run_sync_locally:
        now = datetime.now(timezone.utc).isoformat()
        try:
            from backend.workers.jobs.ingest_findings import execute_ingest_job
        except ModuleNotFoundError as exc:
            logger.exception("Local ingest-sync dependencies are unavailable: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "Ingestion service unavailable",
                    "detail": "Local ingest worker dependencies are unavailable. Configure SQS ingest queue or install worker dependencies.",
                },
            ) from exc

        try:
            for r in regions:
                job = build_ingest_job_payload(tenant_uuid, account_id, r, now)
                await asyncio.to_thread(execute_ingest_job, job)
        except Exception as exc:
            logger.exception("Synchronous ingest-sync execution failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"error": "Ingestion service unavailable", "detail": "Could not complete synchronous ingest job."},
            ) from exc

        return IngestSyncResponse(
            account_id=account_id,
            regions=regions,
            message="Ingestion completed. Refresh GET /api/findings to see results.",
        )

    if not settings.has_ingest_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Ingestion service unavailable", "detail": "Ingest queue URL not configured."},
        )
    try:
        _enqueue_ingest_jobs(tenant_uuid, account_id, regions)
    except (ClientError, BotoCoreError) as exc:
        logger.exception("SQS send_message failed for ingest-sync fallback enqueue: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Ingestion service unavailable", "detail": "Could not enqueue ingest jobs."},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected ingest-sync enqueue failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Ingestion service unavailable", "detail": "Could not enqueue ingest jobs."},
        ) from exc
    return IngestSyncResponse(
        account_id=account_id,
        regions=regions,
        message="Synchronous ingest is local-only; asynchronous ingest jobs were queued.",
    )


@router.get("/ping")
async def ping():
    """Health check endpoint."""
    return {"status": "ok"}
