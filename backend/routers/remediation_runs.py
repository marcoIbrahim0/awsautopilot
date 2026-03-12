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
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal, NoReturn, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_current_user, get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.action import Action
from backend.models.aws_account import AwsAccount
from backend.models.enums import RemediationRunMode, RemediationRunStatus
from backend.models.remediation_run import RemediationRun
from backend.models.remediation_run_execution import RemediationRunExecution
from backend.models.enums import RemediationRunExecutionPhase, RemediationRunExecutionStatus
from backend.services.remediation_metrics import emit_strategy_metric, emit_validation_failure
from backend.services.remediation_risk import evaluate_strategy_impact, has_failing_checks, requires_risk_ack
from backend.services.remediation_runtime_checks import (
    collect_runtime_risk_signals,
    probe_direct_fix_permissions,
)
from backend.services.direct_fix_bridge import get_supported_direct_fix_action_types
from backend.services.direct_fix_approval import (
    DIRECT_FIX_APPROVAL_ARTIFACT_KEY,
    build_direct_fix_approval_metadata,
)
from backend.services.remediation_handoff import RunArtifactMetadata, build_run_artifact_metadata
from backend.services.remediation_strategy import (
    map_exception_strategy_inputs,
    map_legacy_variant_to_strategy,
    strategy_required_for_action_type,
    validate_strategy,
    validate_strategy_inputs,
)
from backend.services.root_credentials_workflow import (
    ROOT_CREDENTIALS_REQUIRED_MESSAGE,
    ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
    build_manual_high_risk_marker,
    is_root_credentials_required_action,
    root_credentials_required_error_detail,
)
from backend.models.user import User
from backend.routers.aws_accounts import get_tenant, resolve_tenant_id
from backend.utils.sqs import (
    build_pr_bundle_execution_job_payload,
    build_remediation_run_job_payload,
    parse_queue_region,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/remediation-runs", tags=["remediation-runs"])

PR_ONLY_ACTION_TYPE = "pr_only"
PR_BUNDLE_UNSUPPORTED_ERROR = "PR bundle unsupported"
PR_BUNDLE_UNSUPPORTED_DETAIL = (
    "This action group is pr_only (unmapped control). Terraform/CloudFormation generation "
    "isn't supported yet. Remediate manually in AWS, then click Recompute actions."
)
EXCEPTION_ONLY_STRATEGY_ERROR = "Exception-only strategy"
EXCEPTION_ONLY_STRATEGY_DETAIL = "Use Exception workflow instead of PR bundle."
ACTIVE_EXECUTION_STATUSES = {
    RemediationRunExecutionStatus.queued,
    RemediationRunExecutionStatus.running,
}
ACTIVE_RUN_DUPLICATE_STATUSES = (
    RemediationRunStatus.pending,
    RemediationRunStatus.running,
    RemediationRunStatus.awaiting_approval,
)
ACTIVE_RUN_DUPLICATE_STATUS_VALUES = {status.value for status in ACTIVE_RUN_DUPLICATE_STATUSES}
RECENT_DUPLICATE_WINDOW_SECONDS = 30
PR_BUNDLE_RATE_LIMIT_WINDOW_MINUTES = 20
PR_BUNDLE_RATE_LIMIT_TOTAL_PER_WINDOW = 6
PR_BUNDLE_RATE_LIMIT_IDENTICAL_PER_WINDOW = 3
RESEND_RATE_LIMIT_WINDOW_MINUTES = 20
RESEND_RATE_LIMIT_MAX_PER_WINDOW = 3
QUEUE_RESEND_ATTEMPTS_ARTIFACT_KEY = "queue_resend_attempts"
EXECUTION_TOTAL_STEPS = 3
EXECUTION_STATUS_PROGRESS = {
    RemediationRunExecutionStatus.queued.value: (0, 10),
    RemediationRunExecutionStatus.running.value: (1, 60),
    RemediationRunExecutionStatus.awaiting_approval.value: (2, 80),
    RemediationRunExecutionStatus.success.value: (3, 100),
    RemediationRunExecutionStatus.failed.value: (3, 100),
    RemediationRunExecutionStatus.cancelled.value: (3, 100),
}


def _as_mode_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, RemediationRunMode):
        return value.value
    return str(value)


def _as_status_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, RemediationRunStatus):
        return value.value
    return str(value)


def _extract_artifacts(run: RemediationRun | None) -> dict[str, Any]:
    if run is None:
        return {}
    if isinstance(run.artifacts, dict):
        return run.artifacts
    return {}


def _normalize_strategy_inputs(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    return value


def _run_matches_request_signature(
    run: RemediationRun,
    *,
    mode: str,
    strategy_id: str | None,
    strategy_inputs: dict[str, Any] | None,
    pr_bundle_variant: str | None,
    repo_target: dict[str, Any] | None,
) -> bool:
    if _as_mode_value(run.mode) != mode:
        return False

    artifacts = _extract_artifacts(run)
    run_strategy_id = artifacts.get("selected_strategy")
    if run_strategy_id != strategy_id:
        return False

    run_strategy_inputs = _normalize_strategy_inputs(artifacts.get("strategy_inputs"))
    request_strategy_inputs = _normalize_strategy_inputs(strategy_inputs)
    if run_strategy_inputs != request_strategy_inputs:
        return False

    run_variant = artifacts.get("pr_bundle_variant")
    if run_variant != pr_bundle_variant:
        return False

    run_repo_target = _normalize_strategy_inputs(artifacts.get("repo_target"))
    request_repo_target = _normalize_strategy_inputs(repo_target)
    if run_repo_target != request_repo_target:
        return False

    return True


def _raise_duplicate_run_conflict(existing_run: RemediationRun, *, reason: str, detail: str) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "Duplicate pending run",
            "detail": detail,
            "reason": reason,
            "existing_run_id": str(existing_run.id),
            "existing_run_status": _as_status_value(existing_run.status),
        },
    )


def _raise_pr_bundle_rate_limit(
    *,
    reason: Literal["pr_bundle_rate_limit_total", "pr_bundle_rate_limit_identical"],
    detail: str,
    limit: int,
    observed: int,
    window_minutes: int,
) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "PR bundle queue rate limit exceeded",
            "reason": reason,
            "detail": detail,
            "limit": limit,
            "observed": observed,
            "window_minutes": window_minutes,
        },
    )


def _root_notice(action_type: str | None) -> tuple[bool, str | None, str | None]:
    required = is_root_credentials_required_action(action_type)
    if not required:
        return False, None, None
    return True, ROOT_CREDENTIALS_REQUIRED_MESSAGE, ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH


def _with_manual_high_risk_marker(
    artifacts: dict[str, Any] | None,
    *,
    approved_by_user_id: uuid.UUID | None,
    strategy_id: str | None,
    action_type: str | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(artifacts or {})
    merged["manual_high_risk"] = build_manual_high_risk_marker(
        approved_by_user_id=approved_by_user_id,
        strategy_id=strategy_id,
        action_type=action_type,
    )
    return merged


def _with_direct_fix_approval(
    artifacts: dict[str, Any] | None,
    *,
    approved_by_user_id: uuid.UUID | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(artifacts or {})
    merged[DIRECT_FIX_APPROVAL_ARTIFACT_KEY] = build_direct_fix_approval_metadata(
        approved_by_user_id=approved_by_user_id,
    )
    return merged


def _run_requires_root_credentials(run: RemediationRun) -> bool:
    action = getattr(run, "action", None)
    if action is not None and is_root_credentials_required_action(getattr(action, "action_type", None)):
        return True
    if not isinstance(run.artifacts, dict):
        return False
    marker = run.artifacts.get("manual_high_risk")
    if not isinstance(marker, dict):
        return False
    if marker.get("requires_root_credentials") is True:
        return True
    return is_root_credentials_required_action(str(marker.get("action_type") or ""))


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
    strategy_id: str | None = Field(
        None,
        description="Selected remediation strategy ID (required when action type uses strategy catalog).",
    )
    strategy_inputs: dict[str, Any] | None = Field(
        None,
        description="Optional inputs for the selected remediation strategy.",
    )
    risk_acknowledged: bool = Field(
        False,
        description="Must be true when dependency checks include warn/unknown statuses.",
    )
    pr_bundle_variant: str | None = Field(
        None,
        description=(
            "Deprecated legacy field. Accepted for backward compatibility and mapped "
            "to strategy_id when possible."
        ),
    )
    repo_target: "RepoTargetRequest | None" = Field(
        default=None,
        description="Optional provider-agnostic repository metadata for PR payload generation.",
    )


class RepoTargetRequest(BaseModel):
    """Optional repository metadata used to build provider-agnostic PR payloads."""

    provider: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional generic VCS provider label (for example generic_git or gitlab).",
    )
    repository: str = Field(..., min_length=1, max_length=255, description="Repository slug or URL label.")
    base_branch: str = Field(..., min_length=1, max_length=255, description="Base/default branch for the PR.")
    head_branch: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Optional proposed branch name; autogenerated when omitted.",
    )
    root_path: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
        description="Optional repo-relative root path where bundle files should land.",
    )


class CreateGroupPrBundleRunRequest(BaseModel):
    """Request body for creating one PR-only remediation run for an execution group."""

    action_type: str = Field(..., description="Remediation action type (e.g. s3_bucket_block_public_access)")
    account_id: str = Field(..., description="AWS account ID for the group")
    status: Literal["open", "in_progress", "resolved", "suppressed"] = Field(
        ...,
        description="Action workflow status for the group",
    )
    region: str | None = Field(
        default=None,
        description="AWS region for the group (omit when group region is null/global)",
    )
    region_is_null: bool = Field(
        default=False,
        description="Set true when execution group region is null/global.",
    )
    strategy_id: str | None = Field(
        None,
        description="Selected remediation strategy ID for this group (required when action type uses strategy catalog).",
    )
    strategy_inputs: dict[str, Any] | None = Field(
        None,
        description="Optional inputs for the selected strategy (applies to all actions in group).",
    )
    risk_acknowledged: bool = Field(
        False,
        description="Must be true when dependency checks include warn/unknown statuses.",
    )
    pr_bundle_variant: str | None = Field(
        None,
        description=(
            "Deprecated legacy field. Accepted for backward compatibility and mapped "
            "to strategy_id when possible."
        ),
    )
    repo_target: RepoTargetRequest | None = Field(
        default=None,
        description="Optional provider-agnostic repository metadata for PR payload generation.",
    )


class RemediationRunCreatedResponse(BaseModel):
    """Response for POST (201 Created)."""

    id: str
    action_id: str
    mode: str
    status: str
    created_at: str
    updated_at: str
    manual_high_risk: bool = False
    pre_execution_notice: str | None = None
    runbook_url: str | None = None


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
    approved_by_user_id: str | None = None


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
    status: str | None = None


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
    artifact_metadata: RunArtifactMetadata = Field(default_factory=RunArtifactMetadata)


class RemediationRunExecutionResponse(BaseModel):
    """SaaS-managed execution status/details for a remediation run."""

    id: str
    run_id: str
    phase: str
    status: str
    workspace_manifest: dict[str, Any] | None
    results: dict[str, Any] | None
    logs_ref: str | None
    error_summary: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str
    source: Literal["execution", "run_fallback"] = "execution"
    current_step: str
    progress_percent: int = Field(..., ge=0, le=100)
    completed_steps: int = Field(..., ge=0)
    total_steps: int = Field(..., ge=1)


class StartPrBundleExecutionResponse(BaseModel):
    """Response for starting plan/apply SaaS bundle execution."""

    execution_id: str
    status: str


class ExecutePrBundlePlanRequest(BaseModel):
    """Optional settings for plan-phase SaaS execution."""

    fail_fast: bool | None = Field(
        default=None,
        description="Override default fail-fast behavior for this execution.",
    )


class BulkExecutePrBundleRequest(BaseModel):
    """Request body for bulk SaaS plan execution across many PR-bundle runs."""

    run_ids: list[str] = Field(
        default_factory=list,
        description="Remediation run IDs to queue for plan execution.",
    )
    phase: Literal["plan"] = Field(
        default="plan",
        description="Bulk execution phase. Only 'plan' is supported for this endpoint.",
    )
    max_parallel: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Requested max parallel executions for this batch.",
    )
    fail_fast: bool = Field(
        default=True,
        description="Fail-fast behavior for each queued run execution.",
    )


class BulkApproveApplyRequest(BaseModel):
    """Request body for bulk SaaS apply execution across many PR-bundle runs."""

    run_ids: list[str] = Field(
        default_factory=list,
        description="Remediation run IDs to queue for apply execution.",
    )
    max_parallel: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Requested max parallel executions for this batch.",
    )


class BulkExecutionAcceptedItem(BaseModel):
    run_id: str
    execution_id: str
    phase: Literal["plan", "apply"]
    status: str


class BulkExecutionRejectedItem(BaseModel):
    run_id: str
    reason: Literal[
        "invalid_id",
        "not_found",
        "invalid_mode",
        "missing_bundle",
        "missing_plan",
        "not_awaiting_approval",
        "already_running",
        "capacity_exceeded",
        "root_credentials_required",
        "queue_failed",
    ]
    detail: str


class BulkExecutionResponse(BaseModel):
    accepted: list[BulkExecutionAcceptedItem] = Field(default_factory=list)
    rejected: list[BulkExecutionRejectedItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _assert_tenant_execution_capacity(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    max_concurrent = settings.SAAS_BUNDLE_EXECUTOR_MAX_CONCURRENT_PER_TENANT
    if max_concurrent <= 0:
        return

    count_result = await db.execute(
        select(func.count(RemediationRunExecution.id)).where(
            RemediationRunExecution.tenant_id == tenant_id,
            RemediationRunExecution.status.in_(tuple(ACTIVE_EXECUTION_STATUSES)),
        )
    )
    active_count = int(count_result.scalar() or 0)
    if active_count >= max_concurrent:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Execution capacity reached",
                "detail": (
                    "Too many SaaS executions are currently in progress for this tenant. "
                    "Please retry after one completes."
                ),
            },
        )


async def _tenant_active_execution_count(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    count_result = await db.execute(
        select(func.count(RemediationRunExecution.id)).where(
            RemediationRunExecution.tenant_id == tenant_id,
            RemediationRunExecution.status.in_(tuple(ACTIVE_EXECUTION_STATUSES)),
        )
    )
    return int(count_result.scalar() or 0)


def _build_sqs_client():
    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    return boto3.client("sqs", region_name=queue_region), queue_url


def _enqueue_pr_bundle_execution_message(
    sqs_client,
    queue_url: str,
    execution_id: uuid.UUID,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    phase: Literal["plan", "apply"],
    requested_by_user_id: uuid.UUID,
) -> None:
    payload = build_pr_bundle_execution_job_payload(
        execution_id=execution_id,
        run_id=run_id,
        tenant_id=tenant_id,
        phase=phase,
        created_at=datetime.now(timezone.utc).isoformat(),
        requested_by_user_id=requested_by_user_id,
    )
    sqs_client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))


def _new_batch_key() -> str:
    return str(uuid.uuid4())


def _raise_exception_only_strategy_selected(
    *,
    action_type: str,
    strategy_id: str | None,
    mode: Literal["pr_only", "direct_fix"],
    strategy_inputs: dict[str, Any] | None = None,
) -> NoReturn:
    emit_validation_failure(
        logger,
        reason="exception_only_strategy_selected",
        action_type=action_type,
        strategy_id=strategy_id,
        mode=mode,
    )
    strategy_fragment = f" '{strategy_id}'" if strategy_id else ""
    exception_defaults = map_exception_strategy_inputs(strategy_inputs)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": EXCEPTION_ONLY_STRATEGY_ERROR,
            "detail": f"Selected strategy{strategy_fragment} is exception-only. {EXCEPTION_ONLY_STRATEGY_DETAIL}",
            "exception_flow": exception_defaults,
        },
    )


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
        approved_by_user_id=str(run.approved_by_user_id) if run.approved_by_user_id else None,
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return None


def _run_to_detail_response(run: RemediationRun, action: Action | None = None) -> RemediationRunDetailResponse:
    action_status = _optional_string(getattr(action, "status", None)) if action else None
    action_summary = None
    if action:
        action_summary = ActionSummary(
            id=str(action.id),
            title=action.title,
            account_id=action.account_id,
            region=action.region,
            status=action_status,
        )
    artifact_metadata = build_run_artifact_metadata(
        run_id=run.id,
        mode=run.mode.value,
        status=run.status.value,
        artifacts=run.artifacts,
        outcome=run.outcome,
        logs=run.logs,
        action_status=action_status,
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
        artifact_metadata=artifact_metadata,
    )


def _progress_for_execution_status(status_value: str) -> tuple[int, int]:
    return EXECUTION_STATUS_PROGRESS.get(status_value, (0, 0))


def _step_name_for_execution(*, phase: str, status_value: str) -> str:
    if status_value == RemediationRunExecutionStatus.awaiting_approval.value:
        return "awaiting_approval"
    if status_value == RemediationRunExecutionStatus.success.value:
        return "completed"
    if status_value == RemediationRunExecutionStatus.failed.value:
        return "failed"
    if status_value == RemediationRunExecutionStatus.cancelled.value:
        return "cancelled"
    return f"{phase}_{status_value}"


def _map_run_status_to_execution_status(run_status: RemediationRunStatus) -> str:
    if run_status == RemediationRunStatus.pending:
        return RemediationRunExecutionStatus.queued.value
    return run_status.value


def _execution_to_response(execution: RemediationRunExecution) -> RemediationRunExecutionResponse:
    status_value = execution.status.value
    completed_steps, progress_percent = _progress_for_execution_status(status_value)
    phase_value = execution.phase.value
    return RemediationRunExecutionResponse(
        id=str(execution.id),
        run_id=str(execution.run_id),
        phase=phase_value,
        status=status_value,
        workspace_manifest=execution.workspace_manifest if isinstance(execution.workspace_manifest, dict) else None,
        results=execution.results if isinstance(execution.results, dict) else None,
        logs_ref=execution.logs_ref,
        error_summary=execution.error_summary,
        started_at=execution.started_at.isoformat() if execution.started_at else None,
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
        created_at=execution.created_at.isoformat(),
        updated_at=execution.updated_at.isoformat(),
        source="execution",
        current_step=_step_name_for_execution(phase=phase_value, status_value=status_value),
        progress_percent=progress_percent,
        completed_steps=completed_steps,
        total_steps=EXECUTION_TOTAL_STEPS,
    )


def _run_to_execution_fallback(run: RemediationRun) -> RemediationRunExecutionResponse:
    status_value = _map_run_status_to_execution_status(run.status)
    completed_steps, progress_percent = _progress_for_execution_status(status_value)
    phase_value = RemediationRunExecutionPhase.apply.value
    results: dict[str, Any] | None = None
    if run.outcome:
        results = {"run_outcome": run.outcome}
    return RemediationRunExecutionResponse(
        id=str(run.id),
        run_id=str(run.id),
        phase=phase_value,
        status=status_value,
        workspace_manifest=None,
        results=results,
        logs_ref=None,
        error_summary=None,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
        source="run_fallback",
        current_step=_step_name_for_execution(phase=phase_value, status_value=status_value),
        progress_percent=progress_percent,
        completed_steps=completed_steps,
        total_steps=EXECUTION_TOTAL_STEPS,
    )


def _parse_group_action_ids_from_artifacts(artifacts: dict | None) -> list[str]:
    """Extract group action_ids from run.artifacts.group_bundle.action_ids if present."""
    if not isinstance(artifacts, dict):
        return []
    group_bundle = artifacts.get("group_bundle")
    if not isinstance(group_bundle, dict):
        return []
    raw_ids = group_bundle.get("action_ids")
    if not isinstance(raw_ids, list):
        return []
    action_ids: list[str] = []
    for raw_id in raw_ids:
        if not isinstance(raw_id, str):
            continue
        raw_id = raw_id.strip()
        if not raw_id:
            continue
        action_ids.append(raw_id)
    return action_ids


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _recent_resend_attempts(artifacts: dict[str, Any] | None, *, cutoff: datetime) -> list[str]:
    if not isinstance(artifacts, dict):
        return []
    raw_attempts = artifacts.get(QUEUE_RESEND_ATTEMPTS_ARTIFACT_KEY)
    if not isinstance(raw_attempts, list):
        return []
    kept: list[tuple[datetime, str]] = []
    for raw in raw_attempts:
        parsed = _parse_iso_datetime(raw)
        if parsed is None or parsed < cutoff:
            continue
        kept.append((parsed, parsed.isoformat()))
    kept.sort(key=lambda item: item[0])
    return [iso for _, iso in kept]


# ---------------------------------------------------------------------------
# POST /remediation-runs - Create run and enqueue worker (requires auth)
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=RemediationRunCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create remediation run",
    description=(
        "Create a remediation run (PR bundle or direct fix) and enqueue worker job. "
        "For pr_only runs, optional pr_bundle_variant selects alternative bundle templates "
        "(e.g. cloudfront_oac_private_s3 for S3.2). Requires authentication."
    ),
    responses={
        400: {"description": "Invalid action_id or mode"},
        401: {"description": "Not authenticated"},
        404: {"description": "Action not found"},
        409: {"description": "Duplicate pending run for same action"},
        429: {"description": "PR bundle queue rate limit exceeded"},
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
        select(Action).where(Action.id == action_uuid, Action.tenant_id == tenant_uuid).with_for_update()
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Action not found", "detail": f"No action found with ID {body.action_id}"},
        )
    if body.mode == "pr_only" and action.action_type == PR_ONLY_ACTION_TYPE:
        emit_validation_failure(
            logger,
            reason="pr_only_bundle_disabled",
            action_type=action.action_type,
            mode=body.mode,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": PR_BUNDLE_UNSUPPORTED_ERROR,
                "detail": PR_BUNDLE_UNSUPPORTED_DETAIL,
            },
        )

    if body.mode == "direct_fix" and body.pr_bundle_variant:
        emit_validation_failure(
            logger,
            reason="variant_not_allowed_for_direct_fix",
            action_type=action.action_type,
            mode=body.mode,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid pr_bundle_variant",
                "detail": "pr_bundle_variant is only supported when mode is 'pr_only'.",
            },
        )

    account: AwsAccount | None = None
    acc_result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_uuid,
            AwsAccount.account_id == action.account_id,
        )
    )
    account = acc_result.scalar_one_or_none()

    selected_strategy_id = (body.strategy_id or "").strip() or None
    normalized_variant = (body.pr_bundle_variant or "").strip() or None
    legacy_variant_mapped_from: str | None = None

    if normalized_variant:
        mapped_strategy = map_legacy_variant_to_strategy(action.action_type, normalized_variant)
        if mapped_strategy is None:
            emit_validation_failure(
                logger,
                reason="invalid_legacy_variant",
                action_type=action.action_type,
                mode=body.mode,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid pr_bundle_variant",
                    "detail": (
                        f"Unsupported legacy pr_bundle_variant '{normalized_variant}' "
                        f"for action_type '{action.action_type}'."
                    ),
                },
            )
        if selected_strategy_id and selected_strategy_id != mapped_strategy:
            emit_validation_failure(
                logger,
                reason="strategy_conflict",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Strategy conflict",
                    "detail": (
                        f"strategy_id '{selected_strategy_id}' conflicts with legacy "
                        f"pr_bundle_variant mapping '{mapped_strategy}'."
                    ),
                },
            )
        selected_strategy_id = mapped_strategy
        legacy_variant_mapped_from = normalized_variant

    selected_strategy: dict[str, Any] | None = None
    selected_strategy_inputs: dict[str, Any] | None = None
    risk_snapshot: dict[str, Any] | None = None
    repo_target_payload = body.repo_target.model_dump(exclude_none=True) if body.repo_target else None

    strategy_required = strategy_required_for_action_type(action.action_type)
    if strategy_required or selected_strategy_id:
        if not selected_strategy_id:
            emit_validation_failure(
                logger,
                reason="missing_strategy_id",
                action_type=action.action_type,
                mode=body.mode,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Missing strategy_id",
                    "detail": (
                        f"strategy_id is required for action_type '{action.action_type}'. "
                        "Fetch options via GET /api/actions/{id}/remediation-options."
                    ),
                },
            )
        try:
            selected_strategy = validate_strategy(action.action_type, selected_strategy_id, body.mode)
            selected_strategy_inputs = validate_strategy_inputs(selected_strategy, body.strategy_inputs)
        except ValueError as exc:
            err_text = str(exc).lower()
            reason = "strategy_mode_mismatch" if "requires mode" in err_text else "invalid_strategy_selection"
            emit_validation_failure(
                logger,
                reason=reason,
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid strategy selection", "detail": str(exc)},
            ) from exc

        if selected_strategy.get("exception_only"):
            _raise_exception_only_strategy_selected(
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
                strategy_inputs=selected_strategy_inputs,
            )

        risk_snapshot = evaluate_strategy_impact(
            action,
            selected_strategy,
            strategy_inputs=selected_strategy_inputs,
            account=account,
            runtime_signals=collect_runtime_risk_signals(
                action=action,
                strategy=selected_strategy,
                strategy_inputs=selected_strategy_inputs,
                account=account,
            ),
        )
        if has_failing_checks(risk_snapshot["checks"]):
            emit_strategy_metric(
                logger,
                "dependency_check_fail_count",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            emit_validation_failure(
                logger,
                reason="dependency_check_failed",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Dependency check failed",
                    "detail": "One or more dependency checks blocked this remediation strategy.",
                    "risk_snapshot": risk_snapshot,
                },
            )
        if requires_risk_ack(risk_snapshot["checks"]):
            emit_strategy_metric(
                logger,
                "risk_ack_required_count",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            if not body.risk_acknowledged:
                emit_strategy_metric(
                    logger,
                    "risk_ack_missing_rejection_count",
                    action_type=action.action_type,
                    strategy_id=selected_strategy_id,
                    mode=body.mode,
                )
                emit_validation_failure(
                    logger,
                    reason="risk_ack_missing",
                    action_type=action.action_type,
                    strategy_id=selected_strategy_id,
                    mode=body.mode,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Risk acknowledgement required",
                        "detail": (
                            "This remediation strategy has warning/unknown dependency checks. "
                            "Set risk_acknowledged=true after review."
                        ),
                        "risk_snapshot": risk_snapshot,
                    },
                )
    if body.mode == "direct_fix":
        supported_direct_fix_action_types = get_supported_direct_fix_action_types()
        if not supported_direct_fix_action_types:
            emit_validation_failure(
                logger,
                reason="direct_fix_runtime_unavailable",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "Direct-fix runtime unavailable",
                    "detail": (
                        "This API deployment does not include direct-fix runtime modules. "
                        "Use PR bundle mode or deploy worker-enabled runtime."
                    ),
                },
            )
        if action.action_type not in supported_direct_fix_action_types:
            emit_validation_failure(
                logger,
                reason="direct_fix_unsupported",
                action_type=action.action_type,
                mode=body.mode,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Action not fixable",
                    "detail": (
                        f"Action type '{action.action_type}' does not support direct fix. "
                        f"Supported: {', '.join(sorted(supported_direct_fix_action_types))}. "
                        "Use PR bundle instead."
                    ),
                },
            )
        if not account:
            emit_validation_failure(
                logger,
                reason="direct_fix_account_missing",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "AWS account not found",
                    "detail": f"No AWS account found for action's account_id {action.account_id}. Connect the account first.",
                },
            )
        if not account.role_write_arn:
            emit_validation_failure(
                logger,
                reason="direct_fix_writerole_missing",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
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
        probe_ok, probe_detail = probe_direct_fix_permissions(action=action, account=account)
        if probe_ok is False:
            emit_validation_failure(
                logger,
                reason="direct_fix_permission_probe_failed",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Direct-fix permission probe failed",
                    "detail": probe_detail or "WriteRole cannot perform required pre-check API calls.",
                    "check_id": "direct_fix_permission_probe_failed",
                },
            )
        if probe_ok is None and probe_detail:
            logger.warning(
                "Direct-fix permission probe unavailable action_id=%s action_type=%s detail=%s",
                action.id,
                action.action_type,
                probe_detail,
            )

    now_utc = datetime.now(timezone.utc)
    recent_cutoff = now_utc - timedelta(seconds=RECENT_DUPLICATE_WINDOW_SECONDS)
    pr_bundle_window_cutoff = now_utc - timedelta(minutes=PR_BUNDLE_RATE_LIMIT_WINDOW_MINUTES)
    duplicate_scan_cutoff = pr_bundle_window_cutoff if body.mode == "pr_only" else recent_cutoff
    duplicate_candidate_result = await db.execute(
        select(RemediationRun)
        .where(
            RemediationRun.tenant_id == tenant_uuid,
            RemediationRun.action_id == action_uuid,
            (
                RemediationRun.status.in_(ACTIVE_RUN_DUPLICATE_STATUSES)
                | (RemediationRun.created_at >= duplicate_scan_cutoff)
            ),
        )
        .order_by(
            case(
                (RemediationRun.status.in_(ACTIVE_RUN_DUPLICATE_STATUSES), 0),
                else_=1,
            ),
            RemediationRun.created_at.desc(),
        )
    )
    duplicate_candidates = duplicate_candidate_result.scalars().all()
    active_duplicate = next(
        (
            candidate
            for candidate in duplicate_candidates
            if _as_status_value(candidate.status) in ACTIVE_RUN_DUPLICATE_STATUS_VALUES
        ),
        None,
    )
    if active_duplicate is not None:
        emit_validation_failure(
            logger,
            reason="duplicate_active_run",
            action_type=action.action_type,
            strategy_id=selected_strategy_id,
            mode=body.mode,
        )
        _raise_duplicate_run_conflict(
            active_duplicate,
            reason="duplicate_active_run",
            detail=(
                "An active remediation run already exists for this action. "
                "Wait for it to complete or use the existing run."
            ),
        )

    if body.mode == "pr_only":
        window_runs = [
            candidate
            for candidate in duplicate_candidates
            if _as_mode_value(candidate.mode) == RemediationRunMode.pr_only.value
            and candidate.created_at is not None
            and candidate.created_at >= pr_bundle_window_cutoff
        ]
        total_count = len(window_runs)
        if total_count >= PR_BUNDLE_RATE_LIMIT_TOTAL_PER_WINDOW:
            emit_validation_failure(
                logger,
                reason="pr_bundle_rate_limit_total",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            _raise_pr_bundle_rate_limit(
                reason="pr_bundle_rate_limit_total",
                detail=(
                    "Too many PR bundles were queued for this action recently. "
                    "Try again after the rate-limit window resets."
                ),
                limit=PR_BUNDLE_RATE_LIMIT_TOTAL_PER_WINDOW,
                observed=total_count,
                window_minutes=PR_BUNDLE_RATE_LIMIT_WINDOW_MINUTES,
            )

        identical_count = sum(
            1
            for candidate in window_runs
            if _run_matches_request_signature(
                candidate,
                mode=body.mode,
                strategy_id=selected_strategy_id,
                strategy_inputs=selected_strategy_inputs,
                pr_bundle_variant=normalized_variant,
                repo_target=repo_target_payload,
            )
        )
        if identical_count >= PR_BUNDLE_RATE_LIMIT_IDENTICAL_PER_WINDOW:
            emit_validation_failure(
                logger,
                reason="pr_bundle_rate_limit_identical",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            _raise_pr_bundle_rate_limit(
                reason="pr_bundle_rate_limit_identical",
                detail=(
                    "This PR bundle configuration hit the queue submission limit for this action. "
                    "Try a different configuration or wait for the window to reset."
                ),
                limit=PR_BUNDLE_RATE_LIMIT_IDENTICAL_PER_WINDOW,
                observed=identical_count,
                window_minutes=PR_BUNDLE_RATE_LIMIT_WINDOW_MINUTES,
            )
    else:
        recent_identical = next(
            (
                candidate
                for candidate in duplicate_candidates
                if candidate.created_at is not None
                and candidate.created_at >= recent_cutoff
                and _run_matches_request_signature(
                    candidate,
                    mode=body.mode,
                    strategy_id=selected_strategy_id,
                    strategy_inputs=selected_strategy_inputs,
                    pr_bundle_variant=normalized_variant,
                    repo_target=repo_target_payload,
                )
            ),
            None,
        )
        if recent_identical is not None:
            emit_validation_failure(
                logger,
                reason="duplicate_recent_request",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            _raise_duplicate_run_conflict(
                recent_identical,
                reason="duplicate_recent_request",
                detail=(
                    "An identical remediation run was created recently for this action. "
                    "Use the existing run instead of creating a duplicate."
                ),
            )

    artifacts: dict[str, Any] = {}
    if selected_strategy_id:
        artifacts["selected_strategy"] = selected_strategy_id
    if selected_strategy_inputs:
        artifacts["strategy_inputs"] = selected_strategy_inputs
    if risk_snapshot:
        artifacts["risk_snapshot"] = risk_snapshot
    if body.risk_acknowledged:
        artifacts["risk_acknowledged"] = True
    if normalized_variant:
        artifacts["pr_bundle_variant"] = normalized_variant
    if legacy_variant_mapped_from:
        artifacts["legacy_variant_mapped_from"] = legacy_variant_mapped_from
    if repo_target_payload:
        artifacts["repo_target"] = repo_target_payload
    if body.mode == "direct_fix":
        artifacts = _with_direct_fix_approval(
            artifacts,
            approved_by_user_id=current_user.id,
        )
    root_required, pre_execution_notice, runbook_url = _root_notice(action.action_type)
    if root_required:
        artifacts = _with_manual_high_risk_marker(
            artifacts,
            approved_by_user_id=current_user.id,
            strategy_id=selected_strategy_id,
            action_type=action.action_type,
        )

    run = RemediationRun(
        tenant_id=tenant_uuid,
        action_id=action_uuid,
        mode=RemediationRunMode(body.mode),
        status=RemediationRunStatus.pending,
        approved_by_user_id=current_user.id,
        artifacts=artifacts or None,
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        race_duplicate_result = await db.execute(
            select(RemediationRun)
            .where(
                RemediationRun.tenant_id == tenant_uuid,
                RemediationRun.action_id == action_uuid,
                RemediationRun.status.in_(ACTIVE_RUN_DUPLICATE_STATUSES),
            )
            .order_by(RemediationRun.created_at.desc())
            .limit(1)
        )
        race_duplicate = race_duplicate_result.scalar_one_or_none()
        if race_duplicate is not None:
            emit_validation_failure(
                logger,
                reason="duplicate_active_run_race",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            _raise_duplicate_run_conflict(
                race_duplicate,
                reason="duplicate_active_run_race",
                detail=(
                    "An active remediation run already exists for this action. "
                    "Wait for it to complete or use the existing run."
                ),
            )
        raise
    await db.refresh(run)

    now = datetime.now(timezone.utc).isoformat()
    payload = build_remediation_run_job_payload(
        run.id,
        tenant_uuid,
        action_uuid,
        body.mode,
        now,
        pr_bundle_variant=normalized_variant,
        strategy_id=selected_strategy_id,
        strategy_inputs=selected_strategy_inputs,
        risk_acknowledged=body.risk_acknowledged,
        repo_target=repo_target_payload,
    )
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

    if selected_strategy_id:
        emit_strategy_metric(
            logger,
            "strategy_selected_count",
            action_type=action.action_type,
            strategy_id=selected_strategy_id,
            mode=body.mode,
        )

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
        manual_high_risk=root_required,
        pre_execution_notice=pre_execution_notice,
        runbook_url=runbook_url,
    )


@router.post(
    "/group-pr-bundle",
    response_model=RemediationRunCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create one PR bundle run for an execution group",
    description=(
        "Create a single PR-only remediation run for a specific execution group "
        "(action_type + account_id + region + status). The resulting run produces one combined bundle."
    ),
    responses={
        400: {"description": "Invalid group filters"},
        401: {"description": "Not authenticated"},
        404: {"description": "No actions found for group"},
        409: {"description": "Duplicate pending group run"},
        503: {"description": "Queue unavailable or SQS send failed"},
    },
)
async def create_group_pr_bundle_run(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: CreateGroupPrBundleRunRequest = Body(...),
) -> RemediationRunCreatedResponse:
    """Create one PR-only run that includes all actions in the selected execution group."""
    tenant_uuid = current_user.tenant_id

    if not settings.SQS_INGEST_QUEUE_URL or not settings.SQS_INGEST_QUEUE_URL.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Remediation queue unavailable",
                "detail": "Queue URL not configured. Set SQS_INGEST_QUEUE_URL.",
            },
        )

    action_type = (body.action_type or "").strip()
    account_id = (body.account_id or "").strip()
    status_value = (body.status or "").strip().lower()
    region_value = (body.region or "").strip() if body.region is not None else None

    if not action_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid action_type", "detail": "action_type is required."},
        )
    if action_type == PR_ONLY_ACTION_TYPE:
        emit_validation_failure(
            logger,
            reason="pr_only_bundle_disabled",
            action_type=action_type,
            mode="pr_only",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": PR_BUNDLE_UNSUPPORTED_ERROR,
                "detail": PR_BUNDLE_UNSUPPORTED_DETAIL,
            },
        )
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid account_id", "detail": "account_id is required."},
        )
    if body.region_is_null and region_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid region filter",
                "detail": "region and region_is_null cannot both be set.",
            },
        )
    if not body.region_is_null and not region_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid region filter",
                "detail": "Provide region, or set region_is_null=true for global groups.",
            },
        )
    selected_strategy_id = (body.strategy_id or "").strip() or None
    normalized_variant = (body.pr_bundle_variant or "").strip() or None
    legacy_variant_mapped_from: str | None = None
    if normalized_variant:
        mapped_strategy = map_legacy_variant_to_strategy(action_type, normalized_variant)
        if mapped_strategy is None:
            emit_validation_failure(
                logger,
                reason="invalid_legacy_variant",
                action_type=action_type,
                mode="pr_only",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid pr_bundle_variant",
                    "detail": (
                        f"Unsupported legacy pr_bundle_variant '{normalized_variant}' "
                        f"for action_type '{action_type}'."
                    ),
                },
            )
        if selected_strategy_id and selected_strategy_id != mapped_strategy:
            emit_validation_failure(
                logger,
                reason="strategy_conflict",
                action_type=action_type,
                strategy_id=selected_strategy_id,
                mode="pr_only",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Strategy conflict",
                    "detail": (
                        f"strategy_id '{selected_strategy_id}' conflicts with legacy "
                        f"pr_bundle_variant mapping '{mapped_strategy}'."
                    ),
                },
            )
        selected_strategy_id = mapped_strategy
        legacy_variant_mapped_from = normalized_variant

    query = (
        select(Action)
        .where(
            Action.tenant_id == tenant_uuid,
            Action.action_type == action_type,
            Action.account_id == account_id,
            Action.status == status_value,
        )
        .order_by(Action.priority.desc(), Action.updated_at.desc(), Action.created_at.desc())
    )
    if body.region_is_null:
        query = query.where(Action.region.is_(None))
        normalized_region: str | None = None
    else:
        query = query.where(Action.region == region_value)
        normalized_region = region_value

    result = await db.execute(query)
    actions = result.scalars().unique().all()
    if not actions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "No actions found for group",
                "detail": "No actions match the provided execution-group filters.",
            },
        )

    representative = actions[0]
    account_result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_uuid,
            AwsAccount.account_id == account_id,
        )
    )
    account = account_result.scalar_one_or_none()

    selected_strategy: dict[str, Any] | None = None
    selected_strategy_inputs: dict[str, Any] | None = None
    risk_snapshot: dict[str, Any] | None = None
    repo_target_payload = body.repo_target.model_dump(exclude_none=True) if body.repo_target else None

    strategy_required = strategy_required_for_action_type(action_type)
    if strategy_required or selected_strategy_id:
        if not selected_strategy_id:
            emit_validation_failure(
                logger,
                reason="missing_strategy_id",
                action_type=action_type,
                mode="pr_only",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Missing strategy_id",
                    "detail": (
                        f"strategy_id is required for action_type '{action_type}'. "
                        "Fetch options via GET /api/actions/{id}/remediation-options."
                    ),
                },
            )
        try:
            selected_strategy = validate_strategy(action_type, selected_strategy_id, "pr_only")
            selected_strategy_inputs = validate_strategy_inputs(selected_strategy, body.strategy_inputs)
        except ValueError as exc:
            err_text = str(exc).lower()
            reason = "strategy_mode_mismatch" if "requires mode" in err_text else "invalid_strategy_selection"
            emit_validation_failure(
                logger,
                reason=reason,
                action_type=action_type,
                strategy_id=selected_strategy_id,
                mode="pr_only",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid strategy selection", "detail": str(exc)},
            ) from exc

        if selected_strategy.get("exception_only"):
            _raise_exception_only_strategy_selected(
                action_type=action_type,
                strategy_id=selected_strategy_id,
                mode="pr_only",
                strategy_inputs=selected_strategy_inputs,
            )

        risk_snapshot = evaluate_strategy_impact(
            representative,
            selected_strategy,
            strategy_inputs=selected_strategy_inputs,
            account=account,
            runtime_signals=collect_runtime_risk_signals(
                action=representative,
                strategy=selected_strategy,
                strategy_inputs=selected_strategy_inputs,
                account=account,
            ),
        )
        if has_failing_checks(risk_snapshot["checks"]):
            emit_strategy_metric(
                logger,
                "dependency_check_fail_count",
                action_type=action_type,
                strategy_id=selected_strategy_id,
                mode="pr_only",
            )
            emit_validation_failure(
                logger,
                reason="dependency_check_failed",
                action_type=action_type,
                strategy_id=selected_strategy_id,
                mode="pr_only",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Dependency check failed",
                    "detail": "One or more dependency checks blocked this remediation strategy.",
                    "risk_snapshot": risk_snapshot,
                },
            )
        if requires_risk_ack(risk_snapshot["checks"]):
            emit_strategy_metric(
                logger,
                "risk_ack_required_count",
                action_type=action_type,
                strategy_id=selected_strategy_id,
                mode="pr_only",
            )
            if not body.risk_acknowledged:
                emit_strategy_metric(
                    logger,
                    "risk_ack_missing_rejection_count",
                    action_type=action_type,
                    strategy_id=selected_strategy_id,
                    mode="pr_only",
                )
                emit_validation_failure(
                    logger,
                    reason="risk_ack_missing",
                    action_type=action_type,
                    strategy_id=selected_strategy_id,
                    mode="pr_only",
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Risk acknowledgement required",
                        "detail": (
                            "This remediation strategy has warning/unknown dependency checks. "
                            "Set risk_acknowledged=true after review."
                        ),
                        "risk_snapshot": risk_snapshot,
                    },
                )
    group_key = f"{action_type}|{account_id}|{normalized_region or 'global'}|{status_value}"
    pending_result = await db.execute(
        select(RemediationRun).where(
            RemediationRun.tenant_id == tenant_uuid,
            RemediationRun.mode == RemediationRunMode.pr_only,
            RemediationRun.status == RemediationRunStatus.pending,
        )
    )
    pending_runs = pending_result.scalars().unique().all()
    for pending in pending_runs:
        if not isinstance(pending.artifacts, dict):
            continue
        group_bundle = pending.artifacts.get("group_bundle")
        if not isinstance(group_bundle, dict):
            continue
        existing_group_key = group_bundle.get("group_key")
        existing_repo_target = _normalize_strategy_inputs(pending.artifacts.get("repo_target"))
        if (
            isinstance(existing_group_key, str)
            and existing_group_key == group_key
            and existing_repo_target == repo_target_payload
        ):
            emit_validation_failure(
                logger,
                reason="duplicate_pending_group_run",
                action_type=action_type,
                strategy_id=selected_strategy_id,
                mode="pr_only",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Duplicate pending run",
                    "detail": "A pending group PR bundle run already exists for this execution group.",
                },
            )

    action_ids = [str(action.id) for action in actions]

    artifacts: dict[str, Any] = {
        "group_bundle": {
            "group_key": group_key,
            "action_type": action_type,
            "account_id": account_id,
            "region": normalized_region,
            "status": status_value,
            "action_count": len(action_ids),
            "action_ids": action_ids,
        }
    }
    if selected_strategy_id:
        artifacts["selected_strategy"] = selected_strategy_id
    if selected_strategy_inputs:
        artifacts["strategy_inputs"] = selected_strategy_inputs
    if risk_snapshot:
        artifacts["risk_snapshot"] = risk_snapshot
    if body.risk_acknowledged:
        artifacts["risk_acknowledged"] = True
    if normalized_variant:
        artifacts["pr_bundle_variant"] = normalized_variant
    if legacy_variant_mapped_from:
        artifacts["legacy_variant_mapped_from"] = legacy_variant_mapped_from
    if repo_target_payload:
        artifacts["repo_target"] = repo_target_payload
    root_required, pre_execution_notice, runbook_url = _root_notice(action_type)
    if root_required:
        artifacts = _with_manual_high_risk_marker(
            artifacts,
            approved_by_user_id=current_user.id,
            strategy_id=selected_strategy_id,
            action_type=action_type,
        )

    run = RemediationRun(
        tenant_id=tenant_uuid,
        action_id=representative.id,
        mode=RemediationRunMode.pr_only,
        status=RemediationRunStatus.pending,
        approved_by_user_id=current_user.id,
        artifacts=artifacts,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    now = datetime.now(timezone.utc).isoformat()
    payload = build_remediation_run_job_payload(
        run.id,
        tenant_uuid,
        representative.id,
        run.mode.value,
        now,
        pr_bundle_variant=normalized_variant,
        strategy_id=selected_strategy_id,
        strategy_inputs=selected_strategy_inputs,
        risk_acknowledged=body.risk_acknowledged,
        group_action_ids=action_ids,
        repo_target=repo_target_payload,
    )
    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)

    try:
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    except ClientError as e:
        logger.exception("SQS send_message failed for group remediation run: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Remediation queue unavailable",
                "detail": "Could not enqueue job. Please try again later.",
            },
        ) from e

    if selected_strategy_id:
        emit_strategy_metric(
            logger,
            "strategy_selected_count",
            action_type=action_type,
            strategy_id=selected_strategy_id,
            mode="pr_only",
        )

    logger.info(
        "Created group remediation run %s (%d actions) key=%s by user %s (tenant %s)",
        run.id,
        len(action_ids),
        group_key,
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
        manual_high_risk=root_required,
        pre_execution_notice=pre_execution_notice,
        runbook_url=runbook_url,
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
    control_id: Annotated[
        Optional[str],
        Query(description="Filter by action control ID (e.g., S3.1)"),
    ] = None,
    resource_id: Annotated[
        Optional[str],
        Query(description="Filter by action resource ID"),
    ] = None,
    approved_by_user_id: Annotated[
        Optional[str],
        Query(description="Filter by approver user UUID"),
    ] = None,
    status_filter: Annotated[
        Optional[str],
        Query(alias="status", description="Filter by status (pending, running, awaiting_approval, success, failed, cancelled)"),
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
    if control_id is not None or resource_id is not None:
        query = query.join(Action, RemediationRun.action_id == Action.id)

    if action_id is not None:
        try:
            action_uuid = uuid.UUID(action_id)
            query = query.where(RemediationRun.action_id == action_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid action_id", "detail": "action_id must be a valid UUID"},
            )
    if approved_by_user_id is not None:
        try:
            approved_by_uuid = uuid.UUID(approved_by_user_id)
            query = query.where(RemediationRun.approved_by_user_id == approved_by_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid approved_by_user_id",
                    "detail": "approved_by_user_id must be a valid UUID",
                },
            )
    if status_filter is not None:
        allowed = ("pending", "running", "awaiting_approval", "success", "failed", "cancelled")
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
    if control_id is not None:
        query = query.where(Action.control_id == control_id.strip())
    if resource_id is not None:
        query = query.where(Action.resource_id == resource_id.strip())

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

    if run.status not in (RemediationRunStatus.pending, RemediationRunStatus.running, RemediationRunStatus.awaiting_approval):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Run not cancellable",
                "detail": f"Run is {run.status}; only pending, running, or awaiting_approval runs can be cancelled.",
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


@router.post(
    "/bulk-execute-pr-bundle",
    response_model=BulkExecutionResponse,
    summary="Run plan for multiple PR bundles on SaaS",
    description="Queues plan executions for multiple PR-only runs and returns accepted/rejected results.",
)
async def bulk_execute_pr_bundle_plan(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: BulkExecutePrBundleRequest = Body(default_factory=BulkExecutePrBundleRequest),
) -> BulkExecutionResponse:
    if not settings.SAAS_BUNDLE_EXECUTOR_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "SaaS bundle executor disabled",
                "detail": "Enable SAAS_BUNDLE_EXECUTOR_ENABLED to run PR bundles on SaaS.",
            },
        )
    if not settings.SQS_INGEST_QUEUE_URL or not settings.SQS_INGEST_QUEUE_URL.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Queue not configured",
                "detail": "Queue URL not configured. Set SQS_INGEST_QUEUE_URL.",
            },
        )
    if not body.run_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Missing run_ids", "detail": "Provide at least one run ID."},
        )

    tenant_uuid = current_user.tenant_id
    max_concurrent = settings.SAAS_BUNDLE_EXECUTOR_MAX_CONCURRENT_PER_TENANT
    active_count = await _tenant_active_execution_count(db, tenant_uuid)
    batch_key = _new_batch_key()

    parsed_ids: list[uuid.UUID] = []
    response = BulkExecutionResponse()
    seen: set[str] = set()
    for raw_id in body.run_ids:
        value = (raw_id or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        try:
            parsed_ids.append(uuid.UUID(value))
        except ValueError:
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value or "<empty>",
                    reason="invalid_id",
                    detail="run_id must be a valid UUID",
                )
            )

    if parsed_ids:
        runs_result = await db.execute(
            select(RemediationRun)
            .where(RemediationRun.tenant_id == tenant_uuid, RemediationRun.id.in_(parsed_ids))
            .options(selectinload(RemediationRun.action))
        )
        runs = {run.id: run for run in runs_result.scalars().all()}
    else:
        runs = {}

    queued: list[tuple[RemediationRunExecution, RemediationRun]] = []
    for raw_id in body.run_ids:
        value = (raw_id or "").strip()
        try:
            run_uuid = uuid.UUID(value)
        except ValueError:
            continue
        run = runs.get(run_uuid)
        if run is None:
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="not_found",
                    detail="Remediation run not found.",
                )
            )
            continue
        if run.mode != RemediationRunMode.pr_only:
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="invalid_mode",
                    detail="Only pr_only runs are supported.",
                )
            )
            continue
        if _run_requires_root_credentials(run):
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="root_credentials_required",
                    detail=(
                        "Root credentials required. This remediation cannot run in SaaS executor mode. "
                        f"Follow runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}."
                    ),
                )
            )
            continue
        if not isinstance(run.artifacts, dict) or not isinstance(run.artifacts.get("pr_bundle"), dict):
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="missing_bundle",
                    detail="Run has no pr_bundle artifacts.",
                )
            )
            continue
        active_result = await db.execute(
            select(RemediationRunExecution)
            .where(
                RemediationRunExecution.run_id == run.id,
                RemediationRunExecution.tenant_id == tenant_uuid,
                RemediationRunExecution.status.in_(tuple(ACTIVE_EXECUTION_STATUSES)),
            )
            .order_by(RemediationRunExecution.created_at.desc())
        )
        active = active_result.scalars().first()
        if active:
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="already_running",
                    detail="Run already has an active queued/running execution.",
                )
            )
            continue
        if max_concurrent > 0 and active_count >= max_concurrent:
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="capacity_exceeded",
                    detail="Tenant execution capacity reached.",
                )
            )
            continue
        execution = RemediationRunExecution(
            run_id=run.id,
            tenant_id=tenant_uuid,
            phase=RemediationRunExecutionPhase.plan,
            status=RemediationRunExecutionStatus.queued,
            workspace_manifest={
                "fail_fast": bool(body.fail_fast),
                "max_parallel": int(body.max_parallel),
                "batch_key": batch_key,
            },
        )
        db.add(execution)
        run.status = RemediationRunStatus.running
        run.outcome = "SaaS plan execution queued."
        await db.flush()
        active_count += 1
        queued.append((execution, run))

    await db.commit()
    sqs, queue_url = _build_sqs_client()
    enqueue_failures: list[tuple[RemediationRunExecution, str]] = []
    for execution, run in queued:
        try:
            _enqueue_pr_bundle_execution_message(
                sqs_client=sqs,
                queue_url=queue_url,
                execution_id=execution.id,
                run_id=run.id,
                tenant_id=tenant_uuid,
                phase="plan",
                requested_by_user_id=current_user.id,
            )
            response.accepted.append(
                BulkExecutionAcceptedItem(
                    run_id=str(run.id),
                    execution_id=str(execution.id),
                    phase="plan",
                    status=execution.status.value,
                )
            )
        except ClientError as exc:
            logger.exception("SQS send_message failed for bulk execute-pr-bundle: %s", exc)
            enqueue_failures.append((execution, str(exc)))
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=str(run.id),
                    reason="queue_failed",
                    detail="Could not enqueue execution job.",
                )
            )

    if enqueue_failures:
        for execution, err in enqueue_failures:
            update_result = await db.execute(
                select(RemediationRunExecution)
                .where(RemediationRunExecution.id == execution.id, RemediationRunExecution.tenant_id == tenant_uuid)
                .options(selectinload(RemediationRunExecution.run))
            )
            current_execution = update_result.scalar_one_or_none()
            if current_execution is None:
                continue
            current_execution.status = RemediationRunExecutionStatus.failed
            current_execution.error_summary = f"queue_failed: {err}"[:500]
            current_execution.completed_at = datetime.now(timezone.utc)
            if current_execution.run:
                current_execution.run.status = RemediationRunStatus.failed
                current_execution.run.outcome = "SaaS plan enqueue failed."
        await db.commit()

    return response


@router.post(
    "/bulk-approve-apply",
    response_model=BulkExecutionResponse,
    summary="Approve and run apply for multiple PR bundles on SaaS",
    description="Queues apply executions for multiple PR-only runs after plan approval stage.",
)
async def bulk_approve_apply_pr_bundle(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: BulkApproveApplyRequest = Body(default_factory=BulkApproveApplyRequest),
) -> BulkExecutionResponse:
    if not settings.SAAS_BUNDLE_EXECUTOR_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "SaaS bundle executor disabled",
                "detail": "Enable SAAS_BUNDLE_EXECUTOR_ENABLED to run PR bundles on SaaS.",
            },
        )
    if not settings.SQS_INGEST_QUEUE_URL or not settings.SQS_INGEST_QUEUE_URL.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Queue not configured",
                "detail": "Queue URL not configured. Set SQS_INGEST_QUEUE_URL.",
            },
        )
    if not body.run_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Missing run_ids", "detail": "Provide at least one run ID."},
        )

    tenant_uuid = current_user.tenant_id
    max_concurrent = settings.SAAS_BUNDLE_EXECUTOR_MAX_CONCURRENT_PER_TENANT
    active_count = await _tenant_active_execution_count(db, tenant_uuid)
    batch_key = _new_batch_key()

    parsed_ids: list[uuid.UUID] = []
    response = BulkExecutionResponse()
    seen: set[str] = set()
    for raw_id in body.run_ids:
        value = (raw_id or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        try:
            parsed_ids.append(uuid.UUID(value))
        except ValueError:
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value or "<empty>",
                    reason="invalid_id",
                    detail="run_id must be a valid UUID",
                )
            )

    if parsed_ids:
        runs_result = await db.execute(
            select(RemediationRun)
            .where(RemediationRun.tenant_id == tenant_uuid, RemediationRun.id.in_(parsed_ids))
            .options(selectinload(RemediationRun.action))
        )
        runs = {run.id: run for run in runs_result.scalars().all()}
    else:
        runs = {}

    queued: list[tuple[RemediationRunExecution, RemediationRun]] = []
    for raw_id in body.run_ids:
        value = (raw_id or "").strip()
        try:
            run_uuid = uuid.UUID(value)
        except ValueError:
            continue
        run = runs.get(run_uuid)
        if run is None:
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="not_found",
                    detail="Remediation run not found.",
                )
            )
            continue
        if run.mode != RemediationRunMode.pr_only:
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="invalid_mode",
                    detail="Only pr_only runs are supported.",
                )
            )
            continue
        if _run_requires_root_credentials(run):
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="root_credentials_required",
                    detail=(
                        "Root credentials required. This remediation cannot run in SaaS executor mode. "
                        f"Follow runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}."
                    ),
                )
            )
            continue

        latest_result = await db.execute(
            select(RemediationRunExecution)
            .where(
                RemediationRunExecution.run_id == run.id,
                RemediationRunExecution.tenant_id == tenant_uuid,
            )
            .order_by(RemediationRunExecution.created_at.desc())
        )
        latest = latest_result.scalars().first()
        if latest is None or latest.phase != RemediationRunExecutionPhase.plan:
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="missing_plan",
                    detail="Run plan phase first before apply.",
                )
            )
            continue
        if latest.status != RemediationRunExecutionStatus.awaiting_approval:
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="not_awaiting_approval",
                    detail=f"Current plan status is {latest.status.value}; cannot approve apply.",
                )
            )
            continue
        active_apply_result = await db.execute(
            select(RemediationRunExecution)
            .where(
                RemediationRunExecution.run_id == run.id,
                RemediationRunExecution.tenant_id == tenant_uuid,
                RemediationRunExecution.phase == RemediationRunExecutionPhase.apply,
                RemediationRunExecution.status.in_(tuple(ACTIVE_EXECUTION_STATUSES)),
            )
            .order_by(RemediationRunExecution.created_at.desc())
        )
        active_apply = active_apply_result.scalars().first()
        if active_apply:
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="already_running",
                    detail="Run already has an active apply execution.",
                )
            )
            continue
        if max_concurrent > 0 and active_count >= max_concurrent:
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=value,
                    reason="capacity_exceeded",
                    detail="Tenant execution capacity reached.",
                )
            )
            continue

        execution = RemediationRunExecution(
            run_id=run.id,
            tenant_id=tenant_uuid,
            phase=RemediationRunExecutionPhase.apply,
            status=RemediationRunExecutionStatus.queued,
            workspace_manifest={
                **(latest.workspace_manifest if isinstance(latest.workspace_manifest, dict) else {}),
                "max_parallel": int(body.max_parallel),
                "batch_key": batch_key,
            },
        )
        db.add(execution)
        run.status = RemediationRunStatus.running
        run.outcome = "SaaS apply execution queued."
        await db.flush()
        active_count += 1
        queued.append((execution, run))

    await db.commit()
    sqs, queue_url = _build_sqs_client()
    enqueue_failures: list[tuple[RemediationRunExecution, str]] = []
    for execution, run in queued:
        try:
            _enqueue_pr_bundle_execution_message(
                sqs_client=sqs,
                queue_url=queue_url,
                execution_id=execution.id,
                run_id=run.id,
                tenant_id=tenant_uuid,
                phase="apply",
                requested_by_user_id=current_user.id,
            )
            response.accepted.append(
                BulkExecutionAcceptedItem(
                    run_id=str(run.id),
                    execution_id=str(execution.id),
                    phase="apply",
                    status=execution.status.value,
                )
            )
        except ClientError as exc:
            logger.exception("SQS send_message failed for bulk approve-apply: %s", exc)
            enqueue_failures.append((execution, str(exc)))
            response.rejected.append(
                BulkExecutionRejectedItem(
                    run_id=str(run.id),
                    reason="queue_failed",
                    detail="Could not enqueue execution job.",
                )
            )

    if enqueue_failures:
        for execution, err in enqueue_failures:
            update_result = await db.execute(
                select(RemediationRunExecution)
                .where(RemediationRunExecution.id == execution.id, RemediationRunExecution.tenant_id == tenant_uuid)
                .options(selectinload(RemediationRunExecution.run))
            )
            current_execution = update_result.scalar_one_or_none()
            if current_execution is None:
                continue
            current_execution.status = RemediationRunExecutionStatus.failed
            current_execution.error_summary = f"queue_failed: {err}"[:500]
            current_execution.completed_at = datetime.now(timezone.utc)
            if current_execution.run:
                current_execution.run.status = RemediationRunStatus.failed
                current_execution.run.outcome = "SaaS apply enqueue failed."
        await db.commit()

    return response


@router.post(
    "/{run_id}/execute-pr-bundle",
    response_model=StartPrBundleExecutionResponse,
    summary="Run PR bundle plan on SaaS",
    description="Creates a plan-phase execution and enqueues worker job for SaaS-managed Terraform plan.",
    responses={
        400: {"description": "Invalid run state or missing bundle files"},
        401: {"description": "Not authenticated"},
        429: {"description": "Too many in-flight executions for tenant"},
        404: {"description": "Remediation run not found"},
        503: {"description": "Feature disabled or queue unavailable"},
    },
)
async def execute_pr_bundle_plan(
    run_id: Annotated[str, Path(description="Remediation run UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: ExecutePrBundlePlanRequest = Body(default_factory=ExecutePrBundlePlanRequest),
) -> StartPrBundleExecutionResponse:
    if not settings.SAAS_BUNDLE_EXECUTOR_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "SaaS bundle executor disabled",
                "detail": "Enable SAAS_BUNDLE_EXECUTOR_ENABLED to run PR bundles on SaaS.",
            },
        )
    if not settings.SQS_INGEST_QUEUE_URL or not settings.SQS_INGEST_QUEUE_URL.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Queue not configured",
                "detail": "Queue URL not configured. Set SQS_INGEST_QUEUE_URL.",
            },
        )
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid run_id", "detail": "run_id must be a valid UUID"},
        )

    tenant_uuid = current_user.tenant_id
    run_result = await db.execute(
        select(RemediationRun)
        .where(RemediationRun.id == run_uuid, RemediationRun.tenant_id == tenant_uuid)
        .options(selectinload(RemediationRun.action))
        .with_for_update()
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Remediation run not found", "detail": f"No run found with ID {run_id}"},
        )
    if run.mode != RemediationRunMode.pr_only:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid mode", "detail": "SaaS bundle execution is only supported for pr_only runs."},
        )
    if _run_requires_root_credentials(run):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=root_credentials_required_error_detail(),
        )
    if not isinstance(run.artifacts, dict) or not isinstance(run.artifacts.get("pr_bundle"), dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Missing PR bundle", "detail": "Run has no pr_bundle artifacts to execute."},
        )

    active_result = await db.execute(
        select(RemediationRunExecution)
        .where(
            RemediationRunExecution.run_id == run.id,
            RemediationRunExecution.tenant_id == tenant_uuid,
            RemediationRunExecution.status.in_(tuple(ACTIVE_EXECUTION_STATUSES)),
        )
        .order_by(RemediationRunExecution.created_at.desc())
    )
    active = active_result.scalars().first()
    if active:
        return StartPrBundleExecutionResponse(execution_id=str(active.id), status=active.status.value)

    await _assert_tenant_execution_capacity(db, tenant_uuid)
    fail_fast = settings.SAAS_BUNDLE_EXECUTOR_FAIL_FAST if body.fail_fast is None else body.fail_fast
    execution = RemediationRunExecution(
        run_id=run.id,
        tenant_id=tenant_uuid,
        phase=RemediationRunExecutionPhase.plan,
        status=RemediationRunExecutionStatus.queued,
        workspace_manifest={"fail_fast": bool(fail_fast)},
    )
    db.add(execution)
    run.status = RemediationRunStatus.running
    run.outcome = "SaaS plan execution queued."
    await db.commit()
    await db.refresh(execution)

    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    payload = build_pr_bundle_execution_job_payload(
        execution_id=execution.id,
        run_id=run.id,
        tenant_id=tenant_uuid,
        phase="plan",
        created_at=datetime.now(timezone.utc).isoformat(),
        requested_by_user_id=current_user.id,
    )
    try:
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    except ClientError as exc:
        logger.exception("SQS send_message failed for execute_pr_bundle_plan: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Remediation queue unavailable",
                "detail": "Could not enqueue plan job. Please try again later.",
            },
        ) from exc

    return StartPrBundleExecutionResponse(execution_id=str(execution.id), status=execution.status.value)


@router.post(
    "/{run_id}/approve-apply",
    response_model=StartPrBundleExecutionResponse,
    summary="Approve and run PR bundle apply on SaaS",
    description="Creates an apply-phase execution after plan is awaiting approval and enqueues worker job.",
    responses={
        400: {"description": "Run is not awaiting approval"},
        401: {"description": "Not authenticated"},
        429: {"description": "Too many in-flight executions for tenant"},
        404: {"description": "Remediation run not found"},
        503: {"description": "Feature disabled or queue unavailable"},
    },
)
async def approve_apply_pr_bundle(
    run_id: Annotated[str, Path(description="Remediation run UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StartPrBundleExecutionResponse:
    if not settings.SAAS_BUNDLE_EXECUTOR_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "SaaS bundle executor disabled",
                "detail": "Enable SAAS_BUNDLE_EXECUTOR_ENABLED to run PR bundles on SaaS.",
            },
        )
    if not settings.SQS_INGEST_QUEUE_URL or not settings.SQS_INGEST_QUEUE_URL.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Queue not configured",
                "detail": "Queue URL not configured. Set SQS_INGEST_QUEUE_URL.",
            },
        )
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid run_id", "detail": "run_id must be a valid UUID"},
        )

    tenant_uuid = current_user.tenant_id
    run_result = await db.execute(
        select(RemediationRun)
        .where(RemediationRun.id == run_uuid, RemediationRun.tenant_id == tenant_uuid)
        .options(selectinload(RemediationRun.action))
        .with_for_update()
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Remediation run not found", "detail": f"No run found with ID {run_id}"},
        )
    if run.mode != RemediationRunMode.pr_only:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid mode", "detail": "SaaS bundle execution is only supported for pr_only runs."},
        )
    if _run_requires_root_credentials(run):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=root_credentials_required_error_detail(),
        )

    latest_result = await db.execute(
        select(RemediationRunExecution)
        .where(
            RemediationRunExecution.run_id == run.id,
            RemediationRunExecution.tenant_id == tenant_uuid,
        )
        .order_by(RemediationRunExecution.created_at.desc())
    )
    latest = latest_result.scalars().first()
    if latest is None or latest.phase != RemediationRunExecutionPhase.plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Plan required", "detail": "Run plan phase first before approve/apply."},
        )
    if latest.status != RemediationRunExecutionStatus.awaiting_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Run not awaiting approval",
                "detail": f"Current plan status is {latest.status.value}; cannot approve apply.",
            },
        )

    active_apply_result = await db.execute(
        select(RemediationRunExecution)
        .where(
            RemediationRunExecution.run_id == run.id,
            RemediationRunExecution.tenant_id == tenant_uuid,
            RemediationRunExecution.phase == RemediationRunExecutionPhase.apply,
            RemediationRunExecution.status.in_(tuple(ACTIVE_EXECUTION_STATUSES)),
        )
        .order_by(RemediationRunExecution.created_at.desc())
    )
    active_apply = active_apply_result.scalars().first()
    if active_apply:
        return StartPrBundleExecutionResponse(execution_id=str(active_apply.id), status=active_apply.status.value)

    await _assert_tenant_execution_capacity(db, tenant_uuid)
    execution = RemediationRunExecution(
        run_id=run.id,
        tenant_id=tenant_uuid,
        phase=RemediationRunExecutionPhase.apply,
        status=RemediationRunExecutionStatus.queued,
        workspace_manifest=latest.workspace_manifest if isinstance(latest.workspace_manifest, dict) else None,
    )
    db.add(execution)
    run.status = RemediationRunStatus.running
    run.outcome = "SaaS apply execution queued."
    await db.commit()
    await db.refresh(execution)

    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    payload = build_pr_bundle_execution_job_payload(
        execution_id=execution.id,
        run_id=run.id,
        tenant_id=tenant_uuid,
        phase="apply",
        created_at=datetime.now(timezone.utc).isoformat(),
        requested_by_user_id=current_user.id,
    )
    try:
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    except ClientError as exc:
        logger.exception("SQS send_message failed for execute_pr_bundle_apply: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Remediation queue unavailable",
                "detail": "Could not enqueue apply job. Please try again later.",
            },
        ) from exc

    return StartPrBundleExecutionResponse(execution_id=str(execution.id), status=execution.status.value)


@router.get(
    "/{run_id}/execution",
    response_model=RemediationRunExecutionResponse,
    summary="Get latest SaaS bundle execution",
    description=(
        "Returns execution details for a remediation run. "
        "When no SaaS execution row exists yet, returns a run-level fallback progress snapshot."
    ),
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Remediation run not found"},
    },
)
async def get_remediation_run_execution(
    run_id: Annotated[str, Path(description="Remediation run UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RemediationRunExecutionResponse:
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid run_id", "detail": "run_id must be a valid UUID"},
        )
    tenant_uuid = current_user.tenant_id
    run_result = await db.execute(
        select(RemediationRun).where(RemediationRun.id == run_uuid, RemediationRun.tenant_id == tenant_uuid)
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Remediation run not found", "detail": f"No run found with ID {run_id}"},
        )
    exec_result = await db.execute(
        select(RemediationRunExecution)
        .where(RemediationRunExecution.run_id == run_uuid, RemediationRunExecution.tenant_id == tenant_uuid)
        .order_by(RemediationRunExecution.created_at.desc())
    )
    execution = exec_result.scalars().first()
    if execution is None:
        return _run_to_execution_fallback(run)
    return _execution_to_response(execution)


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
        429: {"description": "Resend rate limit exceeded"},
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
        ).with_for_update()
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

    now_dt = datetime.now(timezone.utc)
    resend_cutoff = now_dt - timedelta(minutes=RESEND_RATE_LIMIT_WINDOW_MINUTES)
    recent_resend_attempts = _recent_resend_attempts(
        run.artifacts if isinstance(run.artifacts, dict) else None,
        cutoff=resend_cutoff,
    )
    if len(recent_resend_attempts) >= RESEND_RATE_LIMIT_MAX_PER_WINDOW:
        oldest_attempt = _parse_iso_datetime(recent_resend_attempts[0])
        retry_after_seconds = None
        if oldest_attempt is not None:
            retry_after_seconds = max(
                1,
                int((oldest_attempt + timedelta(minutes=RESEND_RATE_LIMIT_WINDOW_MINUTES) - now_dt).total_seconds()),
            )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Resend rate limit exceeded",
                "detail": (
                    f"No more than {RESEND_RATE_LIMIT_MAX_PER_WINDOW} resend attempts are allowed "
                    f"within {RESEND_RATE_LIMIT_WINDOW_MINUTES} minutes for the same run."
                ),
                "limit": RESEND_RATE_LIMIT_MAX_PER_WINDOW,
                "window_minutes": RESEND_RATE_LIMIT_WINDOW_MINUTES,
                "retry_after_seconds": retry_after_seconds,
            },
        )

    now = now_dt.isoformat()
    variant: str | None = None
    strategy_id: str | None = None
    strategy_inputs: dict[str, Any] | None = None
    risk_acknowledged = False
    group_action_ids: list[str] | None = None
    if isinstance(run.artifacts, dict):
        raw_variant = run.artifacts.get("pr_bundle_variant")
        if isinstance(raw_variant, str) and raw_variant.strip():
            variant = raw_variant.strip()
        raw_strategy = run.artifacts.get("selected_strategy")
        if isinstance(raw_strategy, str) and raw_strategy.strip():
            strategy_id = raw_strategy.strip()
        raw_inputs = run.artifacts.get("strategy_inputs")
        if isinstance(raw_inputs, dict):
            strategy_inputs = raw_inputs
        risk_acknowledged = bool(run.artifacts.get("risk_acknowledged"))
        parsed_group_ids = _parse_group_action_ids_from_artifacts(run.artifacts)
        if parsed_group_ids:
            group_action_ids = parsed_group_ids

    payload = build_remediation_run_job_payload(
        run.id,
        run.tenant_id,
        run.action_id,
        run.mode.value,
        now,
        pr_bundle_variant=variant,
        strategy_id=strategy_id,
        strategy_inputs=strategy_inputs,
        risk_acknowledged=risk_acknowledged,
        group_action_ids=group_action_ids,
    )
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

    updated_artifacts = dict(run.artifacts) if isinstance(run.artifacts, dict) else {}
    recent_resend_attempts.append(now)
    updated_artifacts[QUEUE_RESEND_ATTEMPTS_ARTIFACT_KEY] = recent_resend_attempts
    run.artifacts = updated_artifacts
    await db.commit()

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

    normalized_files: list[tuple[str, str]] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "file")
        content = item.get("content")
        if content is None:
            content_str = ""
        elif isinstance(content, str):
            content_str = content
        else:
            content_str = str(content)
        normalized_files.append((path, content_str))

    zip_epoch = (1980, 1, 1, 0, 0, 0)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, content in sorted(normalized_files, key=lambda item: item[0]):
            info = zipfile.ZipInfo(filename=path, date_time=zip_epoch)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            zf.writestr(info, content.encode("utf-8"))

    buffer.seek(0)
    filename = f"pr-bundle-{run_id}.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
