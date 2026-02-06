"""
Remediation runs API: create run (enqueue worker), list, get by id (Step 7.2).

Lets the frontend start a remediation run (PR bundle or direct fix), list runs,
and fetch a single run with logs and artifacts.
"""
from __future__ import annotations

import io
import json
import logging
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_current_user, get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.action import Action
from backend.models.aws_account import AwsAccount
from backend.models.enums import RemediationRunMode, RemediationRunStatus
from backend.models.remediation_run import RemediationRun
from backend.models.user import User
from backend.routers.aws_accounts import get_tenant, resolve_tenant_id
from backend.utils.sqs import build_remediation_run_job_payload, parse_queue_region

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/remediation-runs", tags=["remediation-runs"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CreateRemediationRunRequest(BaseModel):
    """Request body for creating a remediation run."""

    action_id: str = Field(..., description="UUID of the action to remediate")
    mode: Literal["pr_only", "direct_fix"] = Field(
        ...,
        description="Whether to generate a PR bundle only or apply a direct fix",
    )


class RemediationRunCreatedResponse(BaseModel):
    """Response for POST (201 Created)."""

    id: str
    action_id: str
    mode: str
    status: str
    created_at: str
    updated_at: str


class RemediationRunListItem(BaseModel):
    """Single run in list response."""

    id: str
    action_id: str
    mode: str
    status: str
    outcome: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str
    artifacts_summary: str | None = None


class RemediationRunsListResponse(BaseModel):
    """Paginated list of remediation runs."""

    items: list[RemediationRunListItem]
    total: int


class ActionSummary(BaseModel):
    """Action summary for run detail."""

    id: str
    title: str
    account_id: str
    region: str | None


class RemediationRunDetailResponse(BaseModel):
    """Full run with action summary and logs/artifacts."""

    id: str
    action_id: str
    mode: str
    status: str
    outcome: str | None
    logs: str | None
    artifacts: dict[str, Any] | None
    approved_by_user_id: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str
    action: ActionSummary | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _artifacts_summary(artifacts: dict | None) -> str | None:
    """Derive a short summary from artifacts (e.g. 'PR bundle: 2 files')."""
    if not artifacts or not isinstance(artifacts, dict):
        return None
    pr_bundle = artifacts.get("pr_bundle")
    if not isinstance(pr_bundle, dict):
        return None
    files = pr_bundle.get("files")
    if isinstance(files, list):
        n = len(files)
        return f"PR bundle: {n} file{'s' if n != 1 else ''}"
    return "PR bundle"


def _run_to_list_item(run: RemediationRun) -> RemediationRunListItem:
    return RemediationRunListItem(
        id=str(run.id),
        action_id=str(run.action_id),
        mode=run.mode.value,
        status=run.status.value,
        outcome=run.outcome,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        created_at=run.created_at.isoformat(),
        artifacts_summary=_artifacts_summary(run.artifacts),
    )


def _run_to_detail_response(run: RemediationRun, action: Action | None = None) -> RemediationRunDetailResponse:
    action_summary = None
    if action:
        action_summary = ActionSummary(
            id=str(action.id),
            title=action.title,
            account_id=action.account_id,
            region=action.region,
        )
    return RemediationRunDetailResponse(
        id=str(run.id),
        action_id=str(run.action_id),
        mode=run.mode.value,
        status=run.status.value,
        outcome=run.outcome,
        logs=run.logs,
        artifacts=run.artifacts,
        approved_by_user_id=str(run.approved_by_user_id) if run.approved_by_user_id else None,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
        action=action_summary,
    )


# ---------------------------------------------------------------------------
# POST /remediation-runs - Create run and enqueue worker (requires auth)
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=RemediationRunCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create remediation run",
    description="Create a remediation run (PR bundle or direct fix) and enqueue worker job. Requires authentication.",
    responses={
        400: {"description": "Invalid action_id or mode"},
        401: {"description": "Not authenticated"},
        404: {"description": "Action not found"},
        409: {"description": "Duplicate pending run for same action"},
        503: {"description": "Queue unavailable or SQS send failed"},
    },
)
async def create_remediation_run(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: CreateRemediationRunRequest = Body(...),
) -> RemediationRunCreatedResponse:
    """
    Create a remediation run and enqueue the worker.

    **Approval (Step 8.4):** For direct_fix, the authenticated user creating the run
    is the approver. approved_by_user_id is set to current_user.id. No separate
    approval step—creating the run implies approval. For pr_only, approved_by_user_id
    is also set for consistency. Once a run completes (success/failed), the audit
    record (approved_by_user_id, created_at) is immutable.
    """
    tenant_uuid = current_user.tenant_id

    if not settings.SQS_INGEST_QUEUE_URL or not settings.SQS_INGEST_QUEUE_URL.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Remediation queue unavailable",
                "detail": "Queue URL not configured. Set SQS_INGEST_QUEUE_URL.",
            },
        )

    try:
        action_uuid = uuid.UUID(body.action_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid action_id", "detail": "action_id must be a valid UUID"},
        )

    result = await db.execute(
        select(Action).where(Action.id == action_uuid, Action.tenant_id == tenant_uuid)
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Action not found", "detail": f"No action found with ID {body.action_id}"},
        )

    # Step 8.4: For direct_fix, validate action is fixable and account has WriteRole
    if body.mode == "direct_fix":
        from worker.services.direct_fix import SUPPORTED_ACTION_TYPES

        if action.action_type not in SUPPORTED_ACTION_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Action not fixable",
                    "detail": (
                        f"Action type '{action.action_type}' does not support direct fix. "
                        f"Supported: {', '.join(sorted(SUPPORTED_ACTION_TYPES))}. Use PR bundle instead."
                    ),
                },
            )
        acc_result = await db.execute(
            select(AwsAccount).where(
                AwsAccount.tenant_id == tenant_uuid,
                AwsAccount.account_id == action.account_id,
            )
        )
        account = acc_result.scalar_one_or_none()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "AWS account not found",
                    "detail": f"No AWS account found for action's account_id {action.account_id}. Connect the account first.",
                },
            )
        if not account.role_write_arn:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "WriteRole not configured",
                    "detail": (
                        "Direct fix requires WriteRole. Add WriteRole ARN in account settings "
                        "or use 'Generate PR bundle' (pr_only) instead."
                    ),
                },
            )

    from backend.models.enums import RemediationRunMode, RemediationRunStatus

    existing = await db.execute(
        select(RemediationRun).where(
            RemediationRun.tenant_id == tenant_uuid,
            RemediationRun.action_id == action_uuid,
            RemediationRun.status == RemediationRunStatus.pending,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Duplicate pending run",
                "detail": "A pending remediation run already exists for this action. Wait for it to complete or use the existing run.",
            },
        )

    run = RemediationRun(
        tenant_id=tenant_uuid,
        action_id=action_uuid,
        mode=RemediationRunMode(body.mode),
        status=RemediationRunStatus.pending,
        approved_by_user_id=current_user.id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    now = datetime.now(timezone.utc).isoformat()
    payload = build_remediation_run_job_payload(run.id, tenant_uuid, action_uuid, body.mode, now)
    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)

    try:
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    except ClientError as e:
        logger.exception("SQS send_message failed for remediation_run: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Remediation queue unavailable",
                "detail": "Could not enqueue job. Please try again later.",
            },
        ) from e

    logger.info(
        "Created remediation run %s for action %s (mode=%s) by user %s (tenant %s)",
        run.id,
        body.action_id,
        body.mode,
        current_user.id,
        tenant_uuid,
    )

    return RemediationRunCreatedResponse(
        id=str(run.id),
        action_id=str(run.action_id),
        mode=run.mode.value,
        status=run.status.value,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /remediation-runs - List runs with filters and pagination
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=RemediationRunsListResponse,
    summary="List remediation runs",
    description="List remediation runs with optional filters (action_id, status, mode) and pagination.",
)
async def list_remediation_runs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    action_id: Annotated[
        Optional[str],
        Query(description="Filter by action UUID"),
    ] = None,
    status_filter: Annotated[
        Optional[str],
        Query(alias="status", description="Filter by status (pending, running, success, failed, cancelled)"),
    ] = None,
    mode: Annotated[
        Optional[str],
        Query(description="Filter by mode (pr_only, direct_fix)"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Max items per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
) -> RemediationRunsListResponse:
    """
    List remediation runs scoped to the tenant.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    query = select(RemediationRun).where(RemediationRun.tenant_id == tenant_uuid)

    if action_id is not None:
        try:
            action_uuid = uuid.UUID(action_id)
            query = query.where(RemediationRun.action_id == action_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid action_id", "detail": "action_id must be a valid UUID"},
            )
    if status_filter is not None:
        allowed = ("pending", "running", "success", "failed", "cancelled")
        raw = status_filter.strip().lower()
        if raw not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid status", "detail": f"status must be one of: {', '.join(allowed)}"},
            )
        query = query.where(RemediationRun.status == RemediationRunStatus(raw))
    if mode is not None:
        if mode not in ("pr_only", "direct_fix"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid mode", "detail": "mode must be 'pr_only' or 'direct_fix'"},
            )
        query = query.where(RemediationRun.mode == RemediationRunMode(mode))

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(RemediationRun.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    runs = result.scalars().unique().all()

    items = [_run_to_list_item(r) for r in runs]
    logger.info("Listed %d remediation runs for tenant %s (total=%d)", len(items), tenant_uuid, total)
    return RemediationRunsListResponse(items=items, total=total)


# ---------------------------------------------------------------------------
# PATCH /remediation-runs/{id} - Cancel a pending or running run
# ---------------------------------------------------------------------------

class PatchRemediationRunRequest(BaseModel):
    """Request body for PATCH (cancel only)."""

    status: Literal["cancelled"] = Field(..., description="Set status to cancelled (only allowed for pending/running)")


@router.patch(
    "/{run_id}",
    response_model=RemediationRunDetailResponse,
    summary="Cancel remediation run",
    description="Cancel a pending or running remediation run. Allows starting a new run for the same action.",
    responses={
        400: {"description": "Invalid run_id or run not cancellable"},
        404: {"description": "Remediation run not found"},
    },
)
async def patch_remediation_run(
    run_id: Annotated[str, Path(description="Remediation run UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: PatchRemediationRunRequest,
) -> RemediationRunDetailResponse:
    """Cancel a pending or running run so a new run can be started. Requires authentication."""
    tenant_uuid = current_user.tenant_id
    await get_tenant(tenant_uuid, db)

    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid run_id", "detail": "run_id must be a valid UUID"},
        )

    result = await db.execute(
        select(RemediationRun)
        .where(RemediationRun.id == run_uuid, RemediationRun.tenant_id == tenant_uuid)
        .options(selectinload(RemediationRun.action))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Remediation run not found", "detail": f"No run found with ID {run_id}"},
        )

    if run.status not in (RemediationRunStatus.pending, RemediationRunStatus.running):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Run not cancellable",
                "detail": f"Run is {run.status}; only pending or running runs can be cancelled.",
            },
        )

    run.status = RemediationRunStatus.cancelled
    run.completed_at = datetime.now(timezone.utc)
    run.outcome = "Cancelled by user"
    run.logs = (run.logs or "").strip()
    if run.logs:
        run.logs += "\nCancelled by user."
    else:
        run.logs = "Cancelled by user."
    await db.commit()
    await db.refresh(run)

    action = run.action if run.action else None
    return _run_to_detail_response(run, action)


# ---------------------------------------------------------------------------
# GET /remediation-runs/{id} - Get single run with action summary
# ---------------------------------------------------------------------------

@router.get(
    "/{run_id}",
    response_model=RemediationRunDetailResponse,
    summary="Get remediation run",
    description="Get a single remediation run by ID with full logs and artifacts. Tenant-scoped.",
    responses={
        400: {"description": "Invalid run_id"},
        404: {"description": "Remediation run not found"},
    },
)
async def get_remediation_run(
    run_id: Annotated[str, Path(description="Remediation run UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> RemediationRunDetailResponse:
    """
    Get a single remediation run by ID with logs, artifacts, and action summary.
    Tenant-scoped; 404 if not found.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid run_id", "detail": "run_id must be a valid UUID"},
        )

    result = await db.execute(
        select(RemediationRun)
        .where(RemediationRun.id == run_uuid, RemediationRun.tenant_id == tenant_uuid)
        .options(selectinload(RemediationRun.action))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Remediation run not found", "detail": f"No run found with ID {run_id}"},
        )

    action = run.action if run.action else None
    return _run_to_detail_response(run, action)


# ---------------------------------------------------------------------------
# POST /remediation-runs/{run_id}/resend — re-enqueue pending run (unstick stale)
# ---------------------------------------------------------------------------

class ResendRemediationRunResponse(BaseModel):
    """Response for POST resend (200 OK)."""

    message: str = Field(..., description="Confirmation that the job was re-sent to the queue.")


@router.post(
    "/{run_id}/resend",
    response_model=ResendRemediationRunResponse,
    summary="Resend pending run to queue",
    description="Re-sends the remediation run job to SQS. Only allowed when run status is pending (e.g. run stuck because message was lost or worker was not running).",
    responses={
        400: {"description": "Run is not pending"},
        404: {"description": "Remediation run not found"},
        503: {"description": "Queue unavailable"},
    },
)
async def resend_remediation_run(
    run_id: Annotated[str, Path(description="Remediation run UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> ResendRemediationRunResponse:
    """
    Re-enqueue a pending remediation run. Use when a run has been pending too long
    (e.g. worker was not running or message was lost). Worker will process idempotently.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    if not settings.SQS_INGEST_QUEUE_URL or not settings.SQS_INGEST_QUEUE_URL.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Queue not configured",
                "detail": "SQS_INGEST_QUEUE_URL is not set. Cannot resend.",
            },
        )

    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid run_id", "detail": "run_id must be a valid UUID"},
        )

    result = await db.execute(
        select(RemediationRun).where(
            RemediationRun.id == run_uuid,
            RemediationRun.tenant_id == tenant_uuid,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Remediation run not found", "detail": f"No run found with ID {run_id}"},
        )

    if run.status != RemediationRunStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Run is not pending",
                "detail": f"Only pending runs can be re-sent. Current status: {run.status.value}.",
            },
        )

    now = datetime.now(timezone.utc).isoformat()
    payload = build_remediation_run_job_payload(run.id, run.tenant_id, run.action_id, run.mode.value, now)
    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)

    try:
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    except ClientError as e:
        logger.exception("SQS send_message failed for remediation_run resend: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Remediation queue unavailable",
                "detail": "Could not re-send job. Please try again later.",
            },
        ) from e

    logger.info(
        "Re-sent remediation run to queue run_id=%s action_id=%s tenant_id=%s",
        run.id,
        run.action_id,
        run.tenant_id,
    )
    return ResendRemediationRunResponse(message="Job re-sent to queue.")


# ---------------------------------------------------------------------------
# PR bundle download (Step 9.6) — optional server-side zip
# ---------------------------------------------------------------------------


@router.get(
    "/{run_id}/pr-bundle.zip",
    summary="Download PR bundle as ZIP",
    description="Returns a zip of all files in run.artifacts.pr_bundle.files. Tenant-scoped; 404 if run not found or no PR bundle.",
    responses={
        404: {"description": "Remediation run not found or no PR bundle files"},
    },
)
async def get_remediation_run_pr_bundle_zip(
    run_id: Annotated[str, Path(description="Remediation run UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> StreamingResponse:
    """
    Download PR bundle as a single zip file (pr-bundle-{run_id}.zip).
    Files are at root of the zip (e.g. s3_block_public_access.tf, providers.tf).
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid run_id", "detail": "run_id must be a valid UUID"},
        )

    result = await db.execute(
        select(RemediationRun).where(
            RemediationRun.id == run_uuid,
            RemediationRun.tenant_id == tenant_uuid,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Remediation run not found", "detail": f"No run found with ID {run_id}"},
        )

    artifacts = run.artifacts if isinstance(run.artifacts, dict) else None
    pr_bundle = artifacts.get("pr_bundle") if artifacts else None
    if not isinstance(pr_bundle, dict):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "No PR bundle", "detail": "This run has no PR bundle artifacts."},
        )
    files = pr_bundle.get("files")
    if not isinstance(files, list) or not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "No PR bundle files", "detail": "PR bundle has no files to download."},
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in files:
            if not isinstance(item, dict):
                continue
            path = item.get("path") or "file"
            content = item.get("content")
            if content is None:
                content = ""
            elif not isinstance(content, str):
                content = str(content)
            zf.writestr(path, content)

    buffer.seek(0)
    filename = f"pr-bundle-{run_id}.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
