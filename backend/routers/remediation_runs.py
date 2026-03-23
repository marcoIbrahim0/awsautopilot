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
from backend.services.direct_fix_bridge import DIRECT_FIX_OUT_OF_SCOPE_MESSAGE
from backend.services.direct_fix_approval import (
    DIRECT_FIX_APPROVAL_ARTIFACT_KEY,
    build_direct_fix_approval_metadata,
)
from backend.services.grouped_remediation_runs import (
    GroupedActionScope,
    GroupedRemediationRunValidationError,
    build_grouped_run_persistence_plan,
    normalize_grouped_request_from_remediation_runs,
)
from backend.services.remediation_handoff import RunArtifactMetadata, build_run_artifact_metadata
from backend.services.remediation_run_resolution import (
    RemediationRunResolutionError,
    apply_resolution_artifacts,
    build_single_run_resolution,
    resolve_create_profile_selection,
)
from backend.services.remediation_profile_selection import resolve_runtime_probe_inputs
from backend.services.remediation_run_queue_contract import (
    grouped_run_signatures_match,
    normalize_grouped_run_artifact_signature,
    normalize_grouped_run_request_signature,
    normalize_single_run_artifact_signature,
    normalize_single_run_request_signature,
    reconstruct_resend_queue_inputs,
)
from backend.services.remediation_run_resolution_view import build_run_detail_resolution
from backend.services.remediation_settings import normalize_remediation_settings
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
from backend.services.root_key_resolution_adapter import (
    build_root_key_execution_authority_error,
    is_root_key_action_type,
    is_root_key_strategy_id,
)
from backend.models.user import User
from backend.routers.aws_accounts import get_tenant, resolve_tenant_id
from backend.utils.sqs import (
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1,
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
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
STALE_PENDING_PR_BUNDLE_RUN_MINUTES = 10
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
SAAS_BUNDLE_EXECUTION_ARCHIVED_ERROR = "SaaS bundle execution archived"
SAAS_BUNDLE_EXECUTION_ARCHIVED_REASON = "saas_bundle_execution_archived"
SAAS_BUNDLE_EXECUTION_ARCHIVED_DETAIL = (
    "PR bundles remain supported. Download the bundle, review the generated artifacts, "
    "and run it with your own credentials or pipeline outside the SaaS. "
    "Optional grouped reporting callbacks remain supported for customer-run bundles."
)


def _raise_saas_bundle_execution_archived() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "error": SAAS_BUNDLE_EXECUTION_ARCHIVED_ERROR,
            "reason": SAAS_BUNDLE_EXECUTION_ARCHIVED_REASON,
            "detail": SAAS_BUNDLE_EXECUTION_ARCHIVED_DETAIL,
        },
    )


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


def _tenant_default_required_input_keys(
    strategy_id: str | None,
    tenant_settings: dict[str, Any] | None,
) -> set[str]:
    settings = normalize_remediation_settings(tenant_settings)
    if (
        strategy_id == "config_enable_centralized_delivery"
        and settings.get("config", {}).get("default_bucket_name")
    ):
        return {"delivery_bucket"}
    return set()


def _run_matches_request_signature(
    run: RemediationRun,
    *,
    mode: str,
    strategy_id: str | None,
    profile_id: str | None,
    strategy_inputs: dict[str, Any] | None,
    pr_bundle_variant: str | None,
    repo_target: dict[str, Any] | None,
) -> bool:
    run_mode = _as_mode_value(run.mode)
    if run_mode != mode:
        return False
    run_signature = normalize_single_run_artifact_signature(
        mode=run_mode or mode,
        artifacts=_extract_artifacts(run),
    )
    request_signature = normalize_single_run_request_signature(
        mode=mode,
        strategy_id=strategy_id,
        profile_id=profile_id,
        strategy_inputs=strategy_inputs,
        pr_bundle_variant=pr_bundle_variant,
        repo_target=repo_target,
    )
    return run_signature == request_signature


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


def _grouped_representative_candidate_ids(
    *,
    preferred_action_id: str,
    action_ids: tuple[str, ...],
) -> tuple[str, ...]:
    return (preferred_action_id, *tuple(action_id for action_id in action_ids if action_id != preferred_action_id))


def _is_stale_pending_pr_bundle_run(run: RemediationRun, *, now: datetime) -> bool:
    if _as_mode_value(run.mode) != RemediationRunMode.pr_only.value:
        return False
    if run.status != RemediationRunStatus.pending:
        return False
    created_at = getattr(run, "created_at", None)
    if not isinstance(created_at, datetime):
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age = now - created_at.astimezone(timezone.utc)
    return age >= timedelta(minutes=STALE_PENDING_PR_BUNDLE_RUN_MINUTES)


def _filter_active_group_duplicate_runs(active_runs: list[RemediationRun], *, now: datetime) -> list[RemediationRun]:
    return [run for run in active_runs if not _is_stale_pending_pr_bundle_run(run, now=now)]


def _select_grouped_representative_action_id(
    *,
    preferred_action_id: str,
    action_ids: tuple[str, ...],
    active_runs: list[RemediationRun],
) -> str | None:
    action_id_set = set(action_ids)
    occupied = {str(run.action_id) for run in active_runs if str(run.action_id) in action_id_set}
    for action_id in _grouped_representative_candidate_ids(
        preferred_action_id=preferred_action_id,
        action_ids=action_ids,
    ):
        if action_id not in occupied:
            return action_id
    return None


def _raise_grouped_active_run_conflict(
    *,
    active_runs: list[RemediationRun],
    action_ids: tuple[str, ...],
) -> NoReturn:
    action_id_set = set(action_ids)
    conflicting_runs = [run for run in active_runs if str(run.action_id) in action_id_set]
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "Active grouped run conflict",
            "detail": (
                "Every action in this execution group already anchors an active remediation run. "
                "Wait for an existing run to complete before creating another differentiated grouped request."
            ),
            "reason": "grouped_active_run_conflict",
            "conflicting_action_ids": sorted({str(run.action_id) for run in conflicting_runs}),
            "existing_run_ids": [str(run.id) for run in conflicting_runs],
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


def _raise_root_key_execution_authority(strategy_id: str | None) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=build_root_key_execution_authority_error(strategy_id=strategy_id),
    )


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


def _run_targets_root_key_authority(run: RemediationRun) -> bool:
    if _run_requires_root_credentials(run):
        return True
    artifacts = _extract_artifacts(run)
    if is_root_key_strategy_id(_optional_string(artifacts.get("selected_strategy"))):
        return True
    resolution = artifacts.get("resolution")
    if isinstance(resolution, dict) and is_root_key_strategy_id(_optional_string(resolution.get("strategy_id"))):
        return True
    group_bundle = artifacts.get("group_bundle")
    if not isinstance(group_bundle, dict):
        return False
    for entry in group_bundle.get("action_resolutions") or []:
        if isinstance(entry, dict) and is_root_key_strategy_id(_optional_string(entry.get("strategy_id"))):
            return True
    return False


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CreateRemediationRunRequest(BaseModel):
    """Request body for creating a remediation run."""

    action_id: str = Field(..., description="UUID of the action to remediate")
    mode: str = Field(
        ...,
        description=(
            "Execution mode. The only supported value is `pr_only`. "
            "Deprecated `direct_fix` requests are rejected."
        ),
    )
    strategy_id: str | None = Field(
        None,
        description="Selected remediation strategy ID (required when action type uses strategy catalog).",
    )
    profile_id: str | None = Field(
        None,
        description="Optional remediation profile ID nested beneath the selected strategy family.",
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


class GroupedActionOverrideRequest(BaseModel):
    """Optional per-action grouped override for Wave 3 grouped resolution."""

    action_id: str = Field(..., description="UUID of the grouped action to override.")
    strategy_id: str | None = Field(
        None,
        description="Optional strategy override for this grouped action.",
    )
    profile_id: str | None = Field(
        None,
        description="Optional remediation profile override for this grouped action.",
    )
    strategy_inputs: dict[str, Any] | None = Field(
        None,
        description="Optional strategy_inputs override for this grouped action.",
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
    action_overrides: list[GroupedActionOverrideRequest] = Field(
        default_factory=list,
        description="Optional per-action grouped overrides nested beneath the top-level group defaults.",
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


class RemediationRunResolutionResponse(BaseModel):
    """Normalized remediation resolution view for run detail."""

    strategy_id: str
    profile_id: str
    support_tier: Literal[
        "deterministic_bundle",
        "review_required_bundle",
        "manual_guidance_only",
    ]
    resolved_inputs: dict[str, Any] = Field(default_factory=dict)
    missing_inputs: list[str] = Field(default_factory=list)
    missing_defaults: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    rejected_profiles: list[dict[str, Any]] = Field(default_factory=list)
    finding_coverage: dict[str, Any] = Field(default_factory=dict)
    preservation_summary: dict[str, Any] = Field(default_factory=dict)
    decision_rationale: str = ""
    decision_version: str


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
    resolution: RemediationRunResolutionResponse | None = None
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
        "no_executable_bundle",
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


def _pr_bundle_files_from_run(run: RemediationRun) -> list[dict[str, Any]]:
    artifacts = run.artifacts if isinstance(run.artifacts, dict) else {}
    pr_bundle = artifacts.get("pr_bundle")
    if not isinstance(pr_bundle, dict):
        return []
    raw_files = pr_bundle.get("files")
    if not isinstance(raw_files, list):
        return []
    return [item for item in raw_files if isinstance(item, dict)]


def _bundle_manifest_from_files(files: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in files:
        path = str(item.get("path") or "").strip()
        if path != "bundle_manifest.json":
            continue
        content = item.get("content")
        if not isinstance(content, str):
            return None
        try:
            payload = json.loads(content)
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None
    return None


def _bundle_has_prefix(files: list[dict[str, Any]], prefix: str) -> bool:
    normalized = prefix.rstrip("/")
    return any(
        (path := str(item.get("path") or "").strip()) == normalized or path.startswith(f"{normalized}/")
        for item in files
    )


def _bundle_executable_folder_count(files: list[dict[str, Any]], execution_root: str) -> int:
    prefix = f"{execution_root.strip().rstrip('/')}/"
    folders: set[str] = set()
    for item in files:
        path = str(item.get("path") or "").strip()
        if not path.startswith(prefix) or not path.endswith(".tf"):
            continue
        relative = path[len(prefix):]
        folder = relative.split("/", 1)[0].strip()
        if folder:
            folders.add(folder)
    return len(folders)


def _mixed_tier_bundle_summary(run: RemediationRun) -> dict[str, Any] | None:
    files = _pr_bundle_files_from_run(run)
    if not files:
        return None
    manifest = _bundle_manifest_from_files(files)
    if isinstance(manifest, dict):
        layout_version = manifest.get("layout_version")
        execution_root = manifest.get("execution_root")
        if isinstance(layout_version, str) and layout_version.strip() and isinstance(execution_root, str) and execution_root.strip():
            root = execution_root.strip()
            return {
                "target_kind": "mixed_tier_grouped",
                "detected_by": "bundle_manifest",
                "layout_version": layout_version.strip(),
                "execution_root": root,
                "executable_folder_count": _bundle_executable_folder_count(files, root),
            }
    heuristic_root = "executable/actions"
    if _bundle_has_prefix(files, heuristic_root):
        return {
            "target_kind": "mixed_tier_grouped",
            "detected_by": "executable_actions_heuristic",
            "layout_version": None,
            "execution_root": heuristic_root,
            "executable_folder_count": _bundle_executable_folder_count(files, heuristic_root),
        }
    return None


def _assert_bundle_has_executable_targets(run: RemediationRun) -> dict[str, Any] | None:
    summary = _mixed_tier_bundle_summary(run)
    if summary and int(summary.get("executable_folder_count") or 0) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "No executable bundle actions",
                "reason": "no_executable_bundle",
                "detail": (
                    "This mixed-tier grouped bundle has no executable Terraform folders. "
                    "Review the review_required/manual_guidance artifacts instead of starting SaaS execution."
                ),
                "layout_version": summary.get("layout_version"),
                "execution_root": summary.get("execution_root"),
            },
        )
    return summary


def _execution_manifest_seed(
    *,
    fail_fast: bool | None = None,
    max_parallel: int | None = None,
    batch_key: str | None = None,
    bundle_summary: dict[str, Any] | None = None,
    base_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = dict(base_manifest or {})
    if fail_fast is not None:
        manifest["fail_fast"] = bool(fail_fast)
    if max_parallel is not None:
        manifest["max_parallel"] = int(max_parallel)
    if batch_key is not None:
        manifest["batch_key"] = batch_key
    if isinstance(bundle_summary, dict):
        manifest["target_kind"] = str(bundle_summary.get("target_kind") or "mixed_tier_grouped")
        manifest["detected_by"] = str(bundle_summary.get("detected_by") or "")
        execution_root = bundle_summary.get("execution_root")
        if isinstance(execution_root, str) and execution_root:
            manifest["execution_root"] = execution_root
        layout_version = bundle_summary.get("layout_version")
        if isinstance(layout_version, str) and layout_version:
            manifest["layout_version"] = layout_version
        manifest["executable_folder_count"] = int(bundle_summary.get("executable_folder_count") or 0)
    return manifest


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


def _raise_grouped_validation_error(
    exc: GroupedRemediationRunValidationError,
    *,
    action_type: str,
    strategy_id: str | None,
) -> NoReturn:
    emit_validation_failure(
        logger,
        reason=exc.code,
        action_type=action_type,
        strategy_id=strategy_id,
        mode="pr_only",
    )
    if exc.code == "exception_only_strategy":
        detail = {
            "error": EXCEPTION_ONLY_STRATEGY_ERROR,
            "detail": str(exc),
            "exception_flow": exc.details.get("exception_flow") if isinstance(exc.details, dict) else {},
        }
    elif exc.code == "dependency_check_failed":
        detail = {
            "error": "Dependency check failed",
            "detail": "One or more dependency checks blocked this remediation strategy.",
        }
        risk_snapshot = exc.details.get("risk_snapshot") if isinstance(exc.details, dict) else None
        if isinstance(risk_snapshot, dict):
            detail["risk_snapshot"] = risk_snapshot
    elif exc.code == "risk_ack_required":
        detail = {
            "error": "Risk acknowledgement required",
            "detail": (
                "This remediation strategy has warning/unknown dependency checks. "
                "Set risk_acknowledged=true after review."
            ),
        }
        risk_snapshot = exc.details.get("risk_snapshot") if isinstance(exc.details, dict) else None
        if isinstance(risk_snapshot, dict):
            detail["risk_snapshot"] = risk_snapshot
    elif exc.code == "duplicate_action_override":
        detail = {"error": "Duplicate action_overrides entry", "detail": str(exc)}
    elif exc.code == "override_action_not_in_group":
        detail = {"error": "Invalid action_overrides[].action_id", "detail": str(exc)}
    elif exc.code == "invalid_override_strategy":
        detail = {"error": "Invalid strategy selection", "detail": str(exc)}
    elif exc.code == "invalid_override_profile":
        detail = {"error": "Invalid profile_id", "detail": str(exc)}
    elif exc.code == "missing_grouped_strategy_id":
        detail = {"error": "Missing strategy_id", "detail": str(exc)}
    elif exc.code == "strategy_conflict":
        detail = {"error": "Strategy conflict", "detail": str(exc)}
    elif exc.code == "invalid_pr_bundle_variant":
        detail = {"error": "Invalid pr_bundle_variant", "detail": str(exc)}
    else:
        detail = {"error": "Invalid grouped remediation request", "detail": str(exc), "reason": exc.code}
        if exc.details:
            detail["validation_details"] = dict(exc.details)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


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
    resolution = build_run_detail_resolution(
        mode=run.mode.value,
        artifacts=run.artifacts,
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
        resolution=resolution,
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
        "Create a PR-bundle remediation run and enqueue the worker job. "
        "Deprecated direct-fix requests are rejected fail-closed. "
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

    Direct-fix and customer WriteRole are intentionally out of scope for now.
    This route currently supports PR-bundle creation only.
    """
    tenant_uuid = current_user.tenant_id
    tenant = await get_tenant(tenant_uuid, db)

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
    body.mode = body.mode.strip()
    if body.mode == "direct_fix":
        emit_validation_failure(
            logger,
            reason="direct_fix_out_of_scope",
            action_type=action.action_type,
            mode=body.mode,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Direct-fix out of scope",
                "detail": DIRECT_FIX_OUT_OF_SCOPE_MESSAGE,
            },
        )
    if body.mode != "pr_only":
        emit_validation_failure(
            logger,
            reason="unsupported_mode",
            action_type=action.action_type,
            mode=body.mode,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Unsupported remediation mode",
                "detail": "Only `pr_only` is supported for remediation runs.",
            },
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
    requested_profile_id = (body.profile_id or "").strip() or None
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
    if body.mode == "pr_only" and requested_profile_id and not selected_strategy_id:
        emit_validation_failure(
            logger,
            reason="profile_requires_strategy_id",
            action_type=action.action_type,
            mode=body.mode,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Missing strategy_id",
                "detail": "profile_id requires a selected strategy_id for validation.",
            },
        )

    selected_strategy: dict[str, Any] | None = None
    selected_strategy_inputs: dict[str, Any] | None = None
    selected_profile_id: str | None = None
    risk_snapshot: dict[str, Any] | None = None
    profile_selection = None
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
            selected_strategy_inputs = validate_strategy_inputs(
                selected_strategy,
                body.strategy_inputs,
                allow_missing_required_keys=_tenant_default_required_input_keys(
                    selected_strategy["strategy_id"],
                    getattr(tenant, "remediation_settings", None),
                ),
            )
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
        if body.mode == "pr_only" and is_root_key_action_type(action.action_type):
            emit_validation_failure(
                logger,
                reason="root_key_execution_authority",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            _raise_root_key_execution_authority(selected_strategy_id)
        try:
            probe_inputs = resolve_runtime_probe_inputs(
                action_type=action.action_type,
                strategy=selected_strategy,
                requested_profile_id=requested_profile_id,
                explicit_inputs=selected_strategy_inputs,
                tenant_settings=getattr(tenant, "remediation_settings", None),
                action=action,
            )
        except ValueError as exc:
            emit_validation_failure(
                logger,
                reason="invalid_profile_selection",
                action_type=action.action_type,
                strategy_id=selected_strategy_id,
                mode=body.mode,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid profile_id", "detail": str(exc)},
            ) from exc
        runtime_signals = collect_runtime_risk_signals(
            action=action,
            strategy=selected_strategy,
            strategy_inputs=probe_inputs,
            account=account,
        )
        if body.mode == "pr_only":
            try:
                profile_selection = resolve_create_profile_selection(
                    action_type=action.action_type,
                    strategy=selected_strategy,
                    requested_profile_id=requested_profile_id,
                    explicit_inputs=selected_strategy_inputs,
                    tenant_settings=getattr(tenant, "remediation_settings", None),
                    runtime_signals=runtime_signals,
                    action=action,
                )
            except RemediationRunResolutionError as exc:
                emit_validation_failure(
                    logger,
                    reason="invalid_profile_selection",
                    action_type=action.action_type,
                    strategy_id=selected_strategy_id,
                    mode=body.mode,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Invalid profile_id", "detail": str(exc)},
                ) from exc
            selected_profile_id = profile_selection.profile.profile_id
            selected_strategy_inputs = profile_selection.persisted_strategy_inputs

        risk_snapshot = evaluate_strategy_impact(
            action,
            selected_strategy,
            strategy_inputs=selected_strategy_inputs,
            account=account,
            runtime_signals=runtime_signals,
        )
        non_executable_resolution = (
            body.mode == "pr_only"
            and profile_selection is not None
            and profile_selection.support_tier != "deterministic_bundle"
        )
        if has_failing_checks(risk_snapshot["checks"]) and not non_executable_resolution:
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
                profile_id=selected_profile_id,
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
                    profile_id=selected_profile_id,
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

    canonical_resolution: dict[str, Any] | None = None
    artifacts: dict[str, Any] = {}
    if risk_snapshot:
        artifacts["risk_snapshot"] = risk_snapshot
    if body.risk_acknowledged:
        artifacts["risk_acknowledged"] = True
    if legacy_variant_mapped_from:
        artifacts["legacy_variant_mapped_from"] = legacy_variant_mapped_from
    if repo_target_payload:
        artifacts["repo_target"] = repo_target_payload
    if body.mode == "pr_only" and selected_strategy and profile_selection is not None:
        canonical_resolution = build_single_run_resolution(
            strategy=selected_strategy,
            profile_selection=profile_selection,
            risk_snapshot=risk_snapshot,
            risk_acknowledged=body.risk_acknowledged,
            requested_profile_id=requested_profile_id,
        )
        artifacts = apply_resolution_artifacts(
            artifacts,
            resolution=canonical_resolution,
            strategy_id=selected_strategy_id,
            strategy_inputs=selected_strategy_inputs,
            pr_bundle_variant=normalized_variant,
        )
    else:
        if selected_strategy_id:
            artifacts["selected_strategy"] = selected_strategy_id
        if selected_strategy_inputs:
            artifacts["strategy_inputs"] = selected_strategy_inputs
        if normalized_variant:
            artifacts["pr_bundle_variant"] = normalized_variant
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
        resolution=canonical_resolution,
        schema_version=(
            REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
            if canonical_resolution is not None
            else REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1
        ),
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
    tenant = await get_tenant(tenant_uuid, db)

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
    try:
        normalized_request = normalize_grouped_request_from_remediation_runs(body)
    except GroupedRemediationRunValidationError as exc:
        _raise_grouped_validation_error(
            exc,
            action_type=action_type,
            strategy_id=(body.strategy_id or "").strip() or None,
        )
    if is_root_key_action_type(action_type):
        emit_validation_failure(
            logger,
            reason="root_key_execution_authority",
            action_type=action_type,
            strategy_id=normalized_request.strategy_id,
            mode="pr_only",
        )
        _raise_root_key_execution_authority(normalized_request.strategy_id)

    strategy_required = strategy_required_for_action_type(action_type)
    has_top_level_group_strategy = bool(normalized_request.strategy_id or normalized_request.pr_bundle_variant)
    if (strategy_required or normalized_request.action_overrides) and not has_top_level_group_strategy:
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

    group_key = f"{action_type}|{account_id}|{normalized_region or 'global'}|{status_value}"
    account_result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_uuid,
            AwsAccount.account_id == account_id,
        )
    )
    account = account_result.scalar_one_or_none()

    try:
        plan = build_grouped_run_persistence_plan(
            request=normalized_request,
            scope=GroupedActionScope(
                action_type=action_type,
                account_id=account_id,
                region=normalized_region,
                status=status_value,
                group_key=group_key,
            ),
            actions=actions,
            group_bundle_seed={"group_key": group_key},
            account=account,
            tenant_settings=getattr(tenant, "remediation_settings", None),
        )
    except GroupedRemediationRunValidationError as exc:
        _raise_grouped_validation_error(
            exc,
            action_type=action_type,
            strategy_id=normalized_request.strategy_id,
        )

    active_run_result = await db.execute(
        select(RemediationRun).where(
            RemediationRun.tenant_id == tenant_uuid,
            RemediationRun.status.in_(ACTIVE_RUN_DUPLICATE_STATUSES),
        )
    )
    active_runs = _filter_active_group_duplicate_runs(
        active_run_result.scalars().unique().all(),
        now=datetime.now(timezone.utc),
    )
    for pending in active_runs:
        if _as_mode_value(pending.mode) != RemediationRunMode.pr_only.value:
            continue
        if not isinstance(pending.artifacts, dict):
            continue
        existing_signature = normalize_grouped_run_artifact_signature(pending.artifacts)
        request_signature = normalize_grouped_run_request_signature(
            group_key=group_key,
            strategy_id=plan.request.strategy_id,
            strategy_inputs=plan.request.strategy_inputs,
            pr_bundle_variant=plan.request.pr_bundle_variant,
            repo_target=plan.request.repo_target,
            action_resolutions=plan.action_resolutions,
        )
        if grouped_run_signatures_match(existing_signature, request_signature):
            emit_validation_failure(
                logger,
                reason="duplicate_pending_group_run",
                action_type=action_type,
                strategy_id=plan.request.strategy_id,
                mode="pr_only",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Duplicate pending run",
                    "detail": "A pending group PR bundle run already exists for this execution group.",
                },
            )

    representative_action_id = _select_grouped_representative_action_id(
        preferred_action_id=plan.representative_action_id,
        action_ids=plan.action_ids,
        active_runs=active_runs,
    )
    if representative_action_id is None:
        emit_validation_failure(
            logger,
            reason="grouped_active_run_conflict",
            action_type=action_type,
            strategy_id=plan.request.strategy_id,
            mode="pr_only",
        )
        _raise_grouped_active_run_conflict(active_runs=active_runs, action_ids=plan.action_ids)

    representative_by_id = {str(action.id): action for action in actions}
    representative = representative_by_id.get(representative_action_id, actions[0])
    artifacts: dict[str, Any] = dict(plan.artifacts)
    if plan.request.pr_bundle_variant:
        artifacts["legacy_variant_mapped_from"] = plan.request.pr_bundle_variant
    root_required, pre_execution_notice, runbook_url = _root_notice(action_type)
    if root_required:
        artifacts = _with_manual_high_risk_marker(
            artifacts,
            approved_by_user_id=current_user.id,
            strategy_id=plan.request.strategy_id,
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
    queue_fields = plan.queue_payload_fields_for_schema(REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2)
    payload = build_remediation_run_job_payload(
        run.id,
        tenant_uuid,
        representative.id,
        run.mode.value,
        now,
        pr_bundle_variant=queue_fields.get("pr_bundle_variant"),
        strategy_id=queue_fields.get("strategy_id"),
        strategy_inputs=queue_fields.get("strategy_inputs"),
        risk_acknowledged=bool(queue_fields.get("risk_acknowledged")),
        group_action_ids=queue_fields.get("group_action_ids"),
        repo_target=queue_fields.get("repo_target"),
        action_resolutions=queue_fields.get("action_resolutions"),
        schema_version=REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
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

    if plan.request.strategy_id:
        emit_strategy_metric(
            logger,
            "strategy_selected_count",
            action_type=action_type,
            strategy_id=plan.request.strategy_id,
            mode="pr_only",
        )

    logger.info(
        "Created group remediation run %s (%d actions) key=%s by user %s (tenant %s)",
        run.id,
        len(plan.action_ids),
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
        Query(description="Filter by mode (`pr_only`; `direct_fix` only for historical runs)"),
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
                detail={
                    "error": "Invalid mode",
                    "detail": "mode must be 'pr_only' or 'direct_fix' (historical runs only).",
                },
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
    summary="Archived SaaS PR bundle plan endpoint",
    description=(
        "This public SaaS-managed PR bundle execution path is archived. "
        "Download and run PR bundles in customer-owned workflows instead."
    ),
    responses={410: {"description": "SaaS-managed PR bundle execution is archived"}},
)
async def bulk_execute_pr_bundle_plan(
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    _ = current_user
    _raise_saas_bundle_execution_archived()


@router.post(
    "/bulk-approve-apply",
    summary="Archived SaaS PR bundle apply endpoint",
    description=(
        "This public SaaS-managed PR bundle execution path is archived. "
        "Download and run PR bundles in customer-owned workflows instead."
    ),
    responses={410: {"description": "SaaS-managed PR bundle execution is archived"}},
)
async def bulk_approve_apply_pr_bundle(
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    _ = current_user
    _raise_saas_bundle_execution_archived()


@router.post(
    "/{run_id}/execute-pr-bundle",
    summary="Archived SaaS PR bundle plan endpoint",
    description=(
        "This public SaaS-managed PR bundle execution path is archived. "
        "Download and run PR bundles in customer-owned workflows instead."
    ),
    responses={410: {"description": "SaaS-managed PR bundle execution is archived"}},
)
async def execute_pr_bundle_plan(
    run_id: Annotated[str, Path(description="Remediation run UUID")],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    _ = run_id, current_user
    _raise_saas_bundle_execution_archived()


@router.post(
    "/{run_id}/approve-apply",
    summary="Archived SaaS PR bundle apply endpoint",
    description=(
        "This public SaaS-managed PR bundle execution path is archived. "
        "Download and run PR bundles in customer-owned workflows instead."
    ),
    responses={410: {"description": "SaaS-managed PR bundle execution is archived"}},
)
async def approve_apply_pr_bundle(
    run_id: Annotated[str, Path(description="Remediation run UUID")],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    _ = run_id, current_user
    _raise_saas_bundle_execution_archived()


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
    if _run_targets_root_key_authority(run):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_root_key_execution_authority_error(
                strategy_id=_optional_string(_extract_artifacts(run).get("selected_strategy")),
            ),
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
    queue_inputs = reconstruct_resend_queue_inputs(
        artifacts=run.artifacts if isinstance(run.artifacts, dict) else None,
        mode=run.mode.value,
    )
    schema_version = int(queue_inputs.get("schema_version") or REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1)
    payload = build_remediation_run_job_payload(
        run.id,
        run.tenant_id,
        run.action_id,
        run.mode.value,
        now,
        pr_bundle_variant=queue_inputs.get("pr_bundle_variant"),
        strategy_id=queue_inputs.get("strategy_id"),
        strategy_inputs=queue_inputs.get("strategy_inputs"),
        risk_acknowledged=bool(queue_inputs.get("risk_acknowledged")),
        group_action_ids=queue_inputs.get("group_action_ids"),
        repo_target=queue_inputs.get("repo_target"),
        resolution=queue_inputs.get("resolution") if schema_version == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2 else None,
        action_resolutions=(
            queue_inputs.get("action_resolutions")
            if schema_version == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
            else None
        ),
        schema_version=schema_version,
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
