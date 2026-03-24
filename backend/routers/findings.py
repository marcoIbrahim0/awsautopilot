"""
Findings API endpoints for listing and retrieving Security Hub findings.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from backend.auth import get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.action import Action
from backend.models.action_finding import ActionFinding
from backend.models.action_group_action_state import ActionGroupActionState
from backend.models.action_group_membership import ActionGroupMembership
from backend.models.action_group_run import ActionGroupRun
from backend.models.finding import Finding
from backend.models.enums import RemediationRunMode
from backend.models.remediation_run import RemediationRun
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.services.exception_service import get_exception_state_for_response, get_exception_states_for_entities
from backend.services.action_run_confirmation import derive_pending_confirmation_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/findings", tags=["findings"])
_SG_TARGET_PATTERN = re.compile(r"\bsg-[0-9a-fA-F]{8,17}\b")

def _normalize_shadow_status(status_raw: str | None) -> str:
    s = (status_raw or "").strip().upper()
    if s == "OPEN":
        return "OPEN"
    if s in {"RESOLVED", "SOFT_RESOLVED"}:
        return "RESOLVED"
    if s in {"UNKNOWN", ""}:
        return "UNKNOWN"
    return "UNKNOWN"


def _is_executable_action_target(action_type: str | None, target_id: str | None, resource_id: str | None) -> bool:
    token = str(action_type or "").strip()
    if token != "sg_restrict_public_ports":
        return True
    for candidate in (target_id, resource_id):
        if candidate and _SG_TARGET_PATTERN.search(str(candidate)):
            return True
    return False


# ============================================
# Response Models
# ============================================

class FindingShadowOverlayResponse(BaseModel):
    """Shadow overlay state for a finding (control-plane wiring)."""

    fingerprint: str | None = None
    source: str | None = None
    status_raw: str
    status_normalized: str
    status_reason: str | None = None
    last_observed_event_time: str | None = None
    last_evaluated_at: str | None = None


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
    canonical_status: str
    status: str
    effective_status: str
    display_badge: str
    in_scope: bool = True
    is_shared_resource: bool = False  # A3: future detection logic; defaults False
    title: str
    description: str | None
    resource_id: str | None
    resource_type: str | None
    control_id: str | None
    standard_name: str | None
    first_observed_at: str | None
    last_observed_at: str | None
    resolved_at: str | None
    updated_at: str | None
    created_at: str
    updated_at_db: str
    raw_json: dict | None = None
    shadow: FindingShadowOverlayResponse | None = None
    # Step 6.3: exception state (on-read expiry)
    exception_id: str | None = None
    exception_expires_at: str | None = None
    exception_expired: bool | None = None
    # Finding actionability hints (for "Fix this finding" + "View PR bundle group")
    remediation_action_id: str | None = None
    remediation_action_type: str | None = None
    remediation_action_status: str | None = None
    remediation_action_account_id: str | None = None
    remediation_action_region: str | None = None
    remediation_action_group_id: str | None = None
    remediation_action_group_status_bucket: str | None = None
    remediation_action_group_latest_run_status: str | None = None
    latest_pr_bundle_run_id: str | None = None
    pending_confirmation: bool = False
    pending_confirmation_started_at: str | None = None
    pending_confirmation_deadline_at: str | None = None
    pending_confirmation_message: str | None = None
    pending_confirmation_severity: str | None = None


class FindingsListResponse(BaseModel):
    """Paginated response for findings list."""

    items: list[FindingResponse]
    total: int


class FindingGroupItem(BaseModel):
    """A single group in the grouped findings response."""

    group_key: str
    control_id: str | None = None
    rule_title: str
    resource_type: str | None
    finding_count: int
    severity_distribution: dict[str, int]
    account_ids: list[str]
    regions: list[str]
    remediation_action_id: str | None = None
    remediation_action_type: str | None = None
    remediation_action_status: str | None = None
    remediation_action_group_id: str | None = None
    remediation_action_group_status_bucket: str | None = None
    remediation_action_group_latest_run_status: str | None = None
    pending_confirmation: bool = False
    pending_confirmation_started_at: str | None = None
    pending_confirmation_deadline_at: str | None = None
    pending_confirmation_message: str | None = None
    pending_confirmation_severity: str | None = None


class FindingsGroupedResponse(BaseModel):
    """Paginated response for grouped findings."""

    items: list[FindingGroupItem]
    total: int


# ============================================
# Helper Functions
# ============================================

def finding_to_response(
    finding: Finding,
    include_raw: bool = False,
    exception_state: dict | None = None,
    remediation_hints: dict | None = None,
) -> FindingResponse:
    """Convert a Finding model to a FindingResponse."""
    state = exception_state or {}
    hints = remediation_hints or {}

    shadow: FindingShadowOverlayResponse | None = None
    if getattr(finding, "shadow_status_raw", None):
        shadow_status_raw = str(getattr(finding, "shadow_status_raw") or "")
        shadow_status_normalized = str(getattr(finding, "shadow_status_normalized") or "").strip().upper()
        shadow = FindingShadowOverlayResponse(
            fingerprint=str(getattr(finding, "shadow_fingerprint") or "") or None,
            source=str(getattr(finding, "shadow_source") or "") or None,
            status_raw=shadow_status_raw,
            status_normalized=shadow_status_normalized or _normalize_shadow_status(shadow_status_raw),
            status_reason=str(getattr(finding, "shadow_status_reason") or "") or None,
            last_observed_event_time=(
                finding.shadow_last_observed_event_time.isoformat()
                if getattr(finding, "shadow_last_observed_event_time", None)
                else None
            ),
            last_evaluated_at=(
                finding.shadow_last_evaluated_at.isoformat()
                if getattr(finding, "shadow_last_evaluated_at", None)
                else None
            ),
        )
    effective_status = _effective_status_from_values(
        canonical_status=str(getattr(finding, "status", "") or ""),
        shadow_status_normalized=str(getattr(finding, "shadow_status_normalized", "") or ""),
    )

    return FindingResponse(
        id=str(finding.id),
        finding_id=finding.finding_id,
        tenant_id=str(finding.tenant_id),
        account_id=finding.account_id,
        region=finding.region,
        source=getattr(finding, "source", "security_hub"),
        severity_label=finding.severity_label,
        severity_normalized=finding.severity_normalized,
        canonical_status=finding.status,
        status=effective_status,
        effective_status=effective_status,
        display_badge="resolved" if effective_status == "RESOLVED" else "open",
        in_scope=bool(getattr(finding, "in_scope", True)),
        is_shared_resource=False,  # A3: real detection is a future task
        title=finding.title,
        description=finding.description,
        resource_id=finding.resource_id,
        resource_type=finding.resource_type,
        control_id=finding.control_id,
        standard_name=finding.standard_name,
        first_observed_at=finding.first_observed_at.isoformat() if finding.first_observed_at else None,
        last_observed_at=finding.last_observed_at.isoformat() if finding.last_observed_at else None,
        resolved_at=finding.resolved_at.isoformat() if getattr(finding, "resolved_at", None) else None,
        updated_at=finding.sh_updated_at.isoformat() if finding.sh_updated_at else None,
        created_at=finding.created_at.isoformat() if finding.created_at else "",
        updated_at_db=finding.updated_at.isoformat() if finding.updated_at else "",
        raw_json=finding.raw_json if include_raw else None,
        shadow=shadow,
        exception_id=state.get("exception_id"),
        exception_expires_at=state.get("exception_expires_at"),
        exception_expired=state.get("exception_expired"),
        remediation_action_id=hints.get("remediation_action_id"),
        remediation_action_type=hints.get("remediation_action_type"),
        remediation_action_status=hints.get("remediation_action_status"),
        remediation_action_account_id=hints.get("remediation_action_account_id"),
        remediation_action_region=hints.get("remediation_action_region"),
        remediation_action_group_id=hints.get("remediation_action_group_id"),
        remediation_action_group_status_bucket=hints.get("remediation_action_group_status_bucket"),
        remediation_action_group_latest_run_status=hints.get("remediation_action_group_latest_run_status"),
        latest_pr_bundle_run_id=hints.get("latest_pr_bundle_run_id"),
        pending_confirmation=bool(hints.get("pending_confirmation")),
        pending_confirmation_started_at=hints.get("pending_confirmation_started_at"),
        pending_confirmation_deadline_at=hints.get("pending_confirmation_deadline_at"),
        pending_confirmation_message=hints.get("pending_confirmation_message"),
        pending_confirmation_severity=hints.get("pending_confirmation_severity"),
    )


async def get_remediation_hints_for_findings(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    finding_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict]:
    """
    Resolve action + latest PR-bundle run metadata for each finding.

    Each finding should map to one action via action_findings. If duplicates exist, the
    most recently updated action row encountered first is used.
    """
    if not finding_ids:
        return {}

    action_rows_result = await db.execute(
        select(
            ActionFinding.finding_id,
            Action.id,
            Action.action_type,
            Action.status,
            Action.account_id,
            Action.region,
            ActionGroupMembership.group_id,
            ActionGroupActionState.latest_run_status_bucket,
            ActionGroupActionState.last_confirmed_at,
            ActionGroupRun.status,
            ActionGroupRun.finished_at,
            Action.target_id,
            Action.resource_id,
        )
        .join(Action, Action.id == ActionFinding.action_id)
        .outerjoin(
            ActionGroupMembership,
            (ActionGroupMembership.action_id == Action.id)
            & (ActionGroupMembership.tenant_id == Action.tenant_id),
        )
        .outerjoin(
            ActionGroupActionState,
            (ActionGroupActionState.tenant_id == ActionGroupMembership.tenant_id)
            & (ActionGroupActionState.group_id == ActionGroupMembership.group_id)
            & (ActionGroupActionState.action_id == ActionGroupMembership.action_id),
        )
        .outerjoin(
            ActionGroupRun,
            (ActionGroupRun.id == ActionGroupActionState.latest_run_id)
            & (ActionGroupRun.tenant_id == ActionGroupMembership.tenant_id),
        )
        .where(
            ActionFinding.finding_id.in_(finding_ids),
            Action.tenant_id == tenant_id,
        )
        .order_by(Action.updated_at.desc().nullslast(), Action.created_at.desc().nullslast())
    )
    action_rows = action_rows_result.all()

    hints_by_finding: dict[uuid.UUID, dict] = {}
    action_ids: set[uuid.UUID] = set()

    for row in action_rows:
        finding_uuid = row[0]
        action_uuid = row[1]
        action_type = row[2]
        if not _is_executable_action_target(action_type, row[11], row[12]):
            continue
        if finding_uuid in hints_by_finding:
            continue
        pending_confirmation = derive_pending_confirmation_state(
            status_bucket=row[7],
            latest_run_status=row[9],
            latest_run_finished_at=row[10],
            last_confirmed_at=row[8],
        )
        hints_by_finding[finding_uuid] = {
            "remediation_action_id": str(action_uuid),
            "remediation_action_type": action_type,
            "remediation_action_status": row[3],
            "remediation_action_account_id": row[4],
            "remediation_action_region": row[5],
            "remediation_action_group_id": str(row[6]) if row[6] else None,
            "remediation_action_group_status_bucket": (
                row[7].value if row[7] is not None and hasattr(row[7], "value") else str(row[7]) if row[7] else None
            ),
            "remediation_action_group_latest_run_status": (
                row[9].value if row[9] is not None and hasattr(row[9], "value") else str(row[9]) if row[9] else None
            ),
            "latest_pr_bundle_run_id": None,
            "pending_confirmation": bool(pending_confirmation["pending_confirmation"]),
            "pending_confirmation_started_at": (
                pending_confirmation["pending_confirmation_started_at"].isoformat()
                if pending_confirmation["pending_confirmation_started_at"]
                else None
            ),
            "pending_confirmation_deadline_at": (
                pending_confirmation["pending_confirmation_deadline_at"].isoformat()
                if pending_confirmation["pending_confirmation_deadline_at"]
                else None
            ),
            "pending_confirmation_message": pending_confirmation["pending_confirmation_message"],
            "pending_confirmation_severity": pending_confirmation["pending_confirmation_severity"],
        }
        action_ids.add(action_uuid)

    if not action_ids:
        return hints_by_finding

    run_rows_result = await db.execute(
        select(
            RemediationRun.action_id,
            RemediationRun.id,
        )
        .where(
            RemediationRun.tenant_id == tenant_id,
            RemediationRun.action_id.in_(list(action_ids)),
            RemediationRun.mode == RemediationRunMode.pr_only,
        )
        .order_by(RemediationRun.action_id, RemediationRun.created_at.desc())
    )
    latest_run_by_action: dict[uuid.UUID, str] = {}
    for action_id, run_id in run_rows_result.all():
        if action_id not in latest_run_by_action:
            latest_run_by_action[action_id] = str(run_id)

    for finding_uuid, hints in hints_by_finding.items():
        action_id = hints.get("remediation_action_id")
        if not action_id:
            continue
        try:
            action_uuid = uuid.UUID(action_id)
        except ValueError:
            continue
        hints["latest_pr_bundle_run_id"] = latest_run_by_action.get(action_uuid)

    return hints_by_finding


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
    
    if not settings.is_local:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

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
# Grouped-findings helpers (A2)
# ============================================

_SEVERITY_LABELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]
_ALLOWED_SEVERITY_FILTERS = set(_SEVERITY_LABELS + ["UNTRIAGED"])


def _parse_severity_filter_values(raw_value: str) -> list[str]:
    values = [part.strip().upper() for part in raw_value.split(",") if part.strip()]
    if not values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid severity",
                "detail": "severity must include at least one value.",
            },
        )
    invalid = sorted({value for value in values if value not in _ALLOWED_SEVERITY_FILTERS})
    if invalid:
        allowed = ", ".join(sorted(_ALLOWED_SEVERITY_FILTERS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid severity",
                "detail": f"severity must be one of: {allowed}",
                "invalid_values": invalid,
            },
        )
    return values


def _parse_status_filter_values(raw_value: str) -> list[str]:
    return [part.strip().upper() for part in raw_value.split(",") if part.strip()]


def _effective_status_from_values(canonical_status: str | None, shadow_status_normalized: str | None) -> str:
    """
    Resolve the effective status shown to users and used for findings filters.

    Canonical status remains the source-of-record in `status`. Shadow status is used
    as an overlay for behavior/UX consistency:
    - shadow RESOLVED always presents as RESOLVED
    - shadow OPEN reopens canonically RESOLVED findings
    """
    canonical = str(canonical_status or "").strip().upper()
    shadow = _normalize_shadow_status(shadow_status_normalized)
    if shadow == "RESOLVED":
        return "RESOLVED"
    if shadow == "OPEN" and canonical == "RESOLVED":
        return "NEW"
    return canonical


def _effective_status_sql_expr() -> object:
    shadow_status = func.upper(func.coalesce(Finding.shadow_status_normalized, ""))
    canonical_status = func.upper(func.coalesce(Finding.status, ""))
    return case(
        (shadow_status == "RESOLVED", "RESOLVED"),
        ((shadow_status == "OPEN") & (canonical_status == "RESOLVED"), "NEW"),
        else_=canonical_status,
    )


def _apply_finding_filters(
    query: object,
    account_id: str | None,
    region: str | None,
    severity: str | None,
    source: str | None,
    status_filter: str | None,
) -> object:
    """Apply optional column filters shared by list and grouped endpoints."""
    if account_id:
        query = query.where(Finding.account_id == account_id)
    if region:
        query = query.where(Finding.region == region)
    if severity:
        severities = _parse_severity_filter_values(severity)
        query = query.where(Finding.severity_label.in_(severities))
    if source:
        sources = [s.strip().lower() for s in source.split(",")]
        query = query.where(Finding.source.in_(sources))
    if status_filter:
        statuses = _parse_status_filter_values(status_filter)
        if statuses:
            query = query.where(_effective_status_sql_expr().in_(statuses))
    return query


def _build_severity_distribution(row: object) -> dict[str, int]:
    """Build {CRITICAL: n, HIGH: n, …} from aggregated count columns."""
    return {
        "CRITICAL": int(row.cnt_critical or 0),
        "HIGH": int(row.cnt_high or 0),
        "MEDIUM": int(row.cnt_medium or 0),
        "LOW": int(row.cnt_low or 0),
        "INFORMATIONAL": int(row.cnt_informational or 0),
    }


def _group_hint_key(
    control_id: str | None,
    resource_type: str | None,
    account_id: str | None,
    region: str | None,
) -> tuple[str, str, str, str]:
    return (
        str(control_id or ""),
        str(resource_type or ""),
        str(account_id or ""),
        str(region or ""),
    )


def _build_group_key(
    control_id: str | None,
    resource_type: str | None,
    account_id: str | None,
    region: str | None,
) -> str:
    return "|".join(
        [
            str(control_id or ""),
            str(resource_type or ""),
            str(account_id or ""),
            str(region or ""),
        ]
    )


async def _fetch_action_hints_for_group_rows(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    rows: list[object],
) -> dict[tuple[str, str, str, str], dict]:
    """Return one executable remediation action hint per grouped findings row."""
    if not rows:
        return {}

    finding_to_group: dict[uuid.UUID, tuple[str, str, str, str]] = {}
    for row in rows:
        group_key = _group_hint_key(
            getattr(row, "control_id", None),
            getattr(row, "resource_type", None),
            getattr(row, "account_id", None),
            getattr(row, "region", None),
        )
        for finding_id in getattr(row, "finding_ids", []) or []:
            if finding_id is None:
                continue
            finding_to_group[finding_id] = group_key

    if not finding_to_group:
        return {}

    rows_result = await db.execute(
        select(
            ActionFinding.finding_id,
            Action.id,
            Action.action_type,
            Action.status,
            Action.account_id,
            Action.region,
            ActionGroupMembership.group_id,
            ActionGroupActionState.latest_run_status_bucket,
            ActionGroupActionState.last_confirmed_at,
            ActionGroupRun.status,
            ActionGroupRun.finished_at,
            Action.target_id,
            Action.resource_id,
        )
        .join(Action, Action.id == ActionFinding.action_id)
        .outerjoin(
            ActionGroupMembership,
            (ActionGroupMembership.action_id == Action.id)
            & (ActionGroupMembership.tenant_id == Action.tenant_id),
        )
        .outerjoin(
            ActionGroupActionState,
            (ActionGroupActionState.tenant_id == ActionGroupMembership.tenant_id)
            & (ActionGroupActionState.group_id == ActionGroupMembership.group_id)
            & (ActionGroupActionState.action_id == ActionGroupMembership.action_id),
        )
        .outerjoin(
            ActionGroupRun,
            (ActionGroupRun.id == ActionGroupActionState.latest_run_id)
            & (ActionGroupRun.tenant_id == ActionGroupMembership.tenant_id),
        )
        .where(
            ActionFinding.finding_id.in_(list(finding_to_group.keys())),
            Action.tenant_id == tenant_id,
        )
        .order_by(Action.updated_at.desc().nullslast(), Action.created_at.desc().nullslast())
    )

    hints: dict[tuple[str, str, str, str], dict] = {}
    for row in rows_result.all():
        finding_id = row[0]
        action_id = row[1]
        action_type = row[2]
        action_status = row[3]
        account_id = row[4]
        region = row[5]
        target_id = row[11]
        resource_id = row[12]
        group_key = finding_to_group.get(finding_id)
        if group_key is None:
            continue
        if not _is_executable_action_target(action_type, target_id, resource_id):
            continue
        if group_key in hints:
            continue
        pending_confirmation = derive_pending_confirmation_state(
            status_bucket=row[7],
            latest_run_status=row[9],
            latest_run_finished_at=row[10],
            last_confirmed_at=row[8],
        )
        hints[group_key] = {
            "remediation_action_id": str(action_id),
            "remediation_action_type": action_type,
            "remediation_action_status": action_status,
            "remediation_action_account_id": account_id,
            "remediation_action_region": region,
            "remediation_action_group_id": str(row[6]) if row[6] else None,
            "remediation_action_group_status_bucket": (
                row[7].value if row[7] is not None and hasattr(row[7], "value") else str(row[7]) if row[7] else None
            ),
            "remediation_action_group_latest_run_status": (
                row[9].value if row[9] is not None and hasattr(row[9], "value") else str(row[9]) if row[9] else None
            ),
            "pending_confirmation": bool(pending_confirmation["pending_confirmation"]),
            "pending_confirmation_started_at": (
                pending_confirmation["pending_confirmation_started_at"].isoformat()
                if pending_confirmation["pending_confirmation_started_at"]
                else None
            ),
            "pending_confirmation_deadline_at": (
                pending_confirmation["pending_confirmation_deadline_at"].isoformat()
                if pending_confirmation["pending_confirmation_deadline_at"]
                else None
            ),
            "pending_confirmation_message": pending_confirmation["pending_confirmation_message"],
            "pending_confirmation_severity": pending_confirmation["pending_confirmation_severity"],
        }
    return hints


def _row_to_group_item(row: object, hint: dict) -> FindingGroupItem:
    """Map one SQLAlchemy grouped row + action hint → FindingGroupItem."""
    return FindingGroupItem(
        group_key=_build_group_key(row.control_id, row.resource_type, row.account_id, row.region),
        control_id=row.control_id or None,
        rule_title=row.rule_title or "",
        resource_type=row.resource_type or None,
        finding_count=int(row.finding_count),
        severity_distribution=_build_severity_distribution(row),
        account_ids=sorted(set(a for a in (row.account_ids or []) if a)),
        regions=sorted(set(r for r in (row.regions or []) if r)),
        remediation_action_id=hint.get("remediation_action_id"),
        remediation_action_type=hint.get("remediation_action_type"),
        remediation_action_status=hint.get("remediation_action_status"),
        remediation_action_group_id=hint.get("remediation_action_group_id"),
        remediation_action_group_status_bucket=hint.get("remediation_action_group_status_bucket"),
        remediation_action_group_latest_run_status=hint.get("remediation_action_group_latest_run_status"),
        pending_confirmation=bool(hint.get("pending_confirmation")),
        pending_confirmation_started_at=hint.get("pending_confirmation_started_at"),
        pending_confirmation_deadline_at=hint.get("pending_confirmation_deadline_at"),
        pending_confirmation_message=hint.get("pending_confirmation_message"),
        pending_confirmation_severity=hint.get("pending_confirmation_severity"),
    )


# ============================================
# Endpoints
# ============================================

@router.get("/grouped", response_model=FindingsGroupedResponse)
async def list_findings_grouped(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    account_id: Annotated[str | None, Query(description="Filter by AWS account ID")] = None,
    region: Annotated[str | None, Query(description="Filter by AWS region")] = None,
    control_id: Annotated[str | None, Query(description="Filter by control ID (e.g., S3.1)")] = None,
    resource_id: Annotated[str | None, Query(description="Filter by resource ID")] = None,
    severity: Annotated[str | None, Query(description="Filter by severity (comma-separated)")] = None,
    source: Annotated[str | None, Query(description="Filter by source (comma-separated)")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="Filter by status (comma-separated)")] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Max groups to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Groups to skip")] = 0,
) -> FindingsGroupedResponse:
    """
    List findings grouped by (control_id, resource_type, account_id, region).

    Applies the same tenant isolation, in-scope filter, and column filters as
    GET /findings. Returns one item per unique scoped group,
    sorted by max severity then by finding count descending.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant_by_uuid(db, tenant_uuid)

    base = (
        select(Finding)
        .where(Finding.tenant_id == tenant.id)
    )
    if settings.ONLY_IN_SCOPE_CONTROLS:
        base = base.where(Finding.in_scope.is_(True))
    if control_id:
        base = base.where(Finding.control_id == control_id.strip())
    if resource_id:
        base = base.where(Finding.resource_id == resource_id.strip())
    base = _apply_finding_filters(base, account_id, region, severity, source, status_filter)

    # Total distinct groups for pagination metadata.
    count_subq = (
        select(Finding.control_id, Finding.resource_type, Finding.account_id, Finding.region)
        .where(Finding.tenant_id == tenant.id)
    )
    if settings.ONLY_IN_SCOPE_CONTROLS:
        count_subq = count_subq.where(Finding.in_scope.is_(True))
    if control_id:
        count_subq = count_subq.where(Finding.control_id == control_id.strip())
    if resource_id:
        count_subq = count_subq.where(Finding.resource_id == resource_id.strip())
    count_subq = _apply_finding_filters(count_subq, account_id, region, severity, source, status_filter)
    count_subq = count_subq.group_by(
        Finding.control_id,
        Finding.resource_type,
        Finding.account_id,
        Finding.region,
    ).subquery()
    total_result = await db.execute(select(func.count()).select_from(count_subq))
    total = total_result.scalar() or 0

    grouped_q = _build_grouped_select(base)
    rows_result = await db.execute(grouped_q.limit(limit).offset(offset))
    rows = rows_result.all()

    hints_by_group = await _fetch_action_hints_for_group_rows(db, tenant_uuid, rows)

    items = [
        _row_to_group_item(
            row,
            hints_by_group.get(
                _group_hint_key(row.control_id, row.resource_type, row.account_id, row.region),
                {},
            ),
        )
        for row in rows
    ]
    logger.info(
        "Grouped findings: %d groups for tenant %s (total: %d)",
        len(items), str(tenant_uuid), total,
    )
    return FindingsGroupedResponse(items=items, total=total)


def _build_grouped_select(base_query: object) -> object:
    """Wrap a base Finding query into a GROUP BY aggregate query."""
    subq = base_query.subquery()
    f = subq.c  # alias columns from the subquery
    return (
        select(
            f.control_id,
            f.resource_type,
            f.account_id,
            f.region,
            func.min(f.title).label("rule_title"),
            func.count(f.id).label("finding_count"),
            func.max(f.severity_normalized).label("max_severity_normalized"),
            func.array_agg(f.id).label("finding_ids"),
            func.array_agg(func.distinct(f.account_id)).label("account_ids"),
            func.array_agg(func.distinct(f.region)).label("regions"),
            func.count(case((f.severity_label == "CRITICAL", 1))).label("cnt_critical"),
            func.count(case((f.severity_label == "HIGH", 1))).label("cnt_high"),
            func.count(case((f.severity_label == "MEDIUM", 1))).label("cnt_medium"),
            func.count(case((f.severity_label == "LOW", 1))).label("cnt_low"),
            func.count(case((f.severity_label == "INFORMATIONAL", 1))).label("cnt_informational"),
        )
        .group_by(f.control_id, f.resource_type, f.account_id, f.region)
        .order_by(
            func.max(f.severity_normalized).desc(),
            func.count(f.id).desc(),
        )
    )


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
    control_id: Annotated[str | None, Query(description="Filter by control ID (e.g., S3.1)")] = None,
    resource_type: Annotated[str | None, Query(description="Filter by resource type")] = None,
    resource_id: Annotated[str | None, Query(description="Filter by resource ID")] = None,
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
    query = (
        select(Finding)
        .where(Finding.tenant_id == tenant.id)
        .options(defer(Finding.raw_json))
    )

    if settings.ONLY_IN_SCOPE_CONTROLS:
        query = query.where(Finding.in_scope.is_(True))

    # Apply optional filters
    if account_id:
        query = query.where(Finding.account_id == account_id)
    if region:
        query = query.where(Finding.region == region)
    if control_id:
        query = query.where(Finding.control_id == control_id.strip())
    if resource_type:
        query = query.where(Finding.resource_type == resource_type.strip())
    if resource_id:
        query = query.where(Finding.resource_id == resource_id.strip())
    if severity:
        # Support comma-separated severities (e.g., "CRITICAL,HIGH")
        severities = _parse_severity_filter_values(severity)
        query = query.where(Finding.severity_label.in_(severities))
    if status_filter:
        # Support comma-separated statuses (e.g., "NEW,NOTIFIED")
        statuses = _parse_status_filter_values(status_filter)
        if statuses:
            query = query.where(_effective_status_sql_expr().in_(statuses))
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
    effective_status_expr = _effective_status_sql_expr()
    resolved_first = case((effective_status_expr == "RESOLVED", 0), else_=1)
    query = query.order_by(
        resolved_first.asc(),  # Resolved findings first for explicit visual confirmation.
        Finding.resolved_at.desc().nullslast(),  # Most recently resolved first within resolved.
        Finding.severity_normalized.desc(),  # Most severe first for non-resolved findings.
        Finding.sh_updated_at.desc().nullslast(),  # Most recently updated.
    )
    query = query.limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    findings = result.scalars().all()

    # Convert to response with exception state (Step 6.3)
    finding_ids = [f.id for f in findings]
    remediation_hints = await get_remediation_hints_for_findings(db, tenant_uuid, finding_ids)

    exception_states = await get_exception_states_for_entities(
        db,
        tenant_id=tenant_uuid,
        entity_type="finding",
        entity_ids=finding_ids,
    )
    items = [
        finding_to_response(
            finding,
            include_raw=False,
            exception_state=exception_states.get(finding.id),
            remediation_hints=remediation_hints.get(finding.id),
        )
        for finding in findings
    ]

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
    remediation_hints = await get_remediation_hints_for_findings(db, tenant_uuid, [finding.id])
    logger.info(f"Retrieved finding {finding_id} for tenant {tenant_id}")

    return finding_to_response(
        finding,
        include_raw=include_raw,
        exception_state=exception_state,
        remediation_hints=remediation_hints.get(finding.id),
    )
