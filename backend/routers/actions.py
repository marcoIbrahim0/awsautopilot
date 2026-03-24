"""
Actions API: compute trigger (Step 5.4), list/detail/PATCH (Step 5.5), remediation-preview (Step 8.4).
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Integer, String, and_, case, cast, exists, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.action import Action
from backend.models.action_finding import ActionFinding
from backend.models.action_group import ActionGroup
from backend.models.action_group_membership import ActionGroupMembership
from backend.models.action_external_link import ActionExternalLink
from backend.models.action_remediation_sync_state import ActionRemediationSyncState
from backend.models.aws_account import AwsAccount
from backend.models.enums import EntityType
from backend.models.exception import Exception
from backend.models.finding import Finding
from backend.models.remediation_run import RemediationRun
from backend.models.user import User
from backend.routers.aws_accounts import get_account_for_tenant, get_tenant, resolve_tenant_id
from backend.services.action_ownership import (
    UNASSIGNED_OWNER_KEY,
    UNASSIGNED_OWNER_LABEL,
    UNASSIGNED_OWNER_TYPE,
    normalize_owner_lookup_key,
)
from backend.services.action_remediation_sync import apply_canonical_action_status
from backend.services.action_sla import (
    ActionSLAStatus as ComputedActionSLAStatus,
    action_sla_expiring_expr,
    action_sla_overdue_cutoff_expr,
    action_sla_overdue_expr,
    compute_action_sla,
)
from backend.services.exception_service import get_exception_state_for_response, get_exception_states_for_entities
from backend.services.direct_fix_bridge import (
    DIRECT_FIX_OUT_OF_SCOPE_MESSAGE,
)
from backend.services.action_scoring import build_score_factors
from backend.services.action_business_impact import (
    build_business_impact_from_components,
    business_impact_rank,
)
from backend.services.action_execution_guidance import build_action_execution_guidance
from backend.services.action_attack_path_view import build_action_attack_path_view
from backend.services.action_graph_context import build_action_graph_context
from backend.services.attack_paths import (
    attack_path_id_for_graph_context,
    build_attack_path_detail_record,
    build_attack_path_graph_context,
    build_shared_attack_path_records,
)
from backend.services.control_scope import equivalent_control_ids_for_control
from backend.services.attack_path_materialized import (
    get_materialized_attack_path,
    has_materialized_attack_paths,
    list_materialized_attack_paths,
    materialize_attack_paths,
    maybe_schedule_attack_path_refresh,
)
from backend.services.integration_sync import dispatch_sync_tasks, plan_action_sync_tasks
from backend.services.action_recommendation import build_action_recommendation
from backend.services.remediation_handoff import (
    ActionImplementationArtifactLink,
    build_run_artifact_metadata,
    build_action_implementation_artifacts,
)
from backend.services.remediation_profile_read_path import (
    InvalidProfileSelection,
    build_preview_resolution,
    build_strategy_profile_metadata,
)
from backend.services.remediation_profile_selection import resolve_profile_selection, resolve_runtime_probe_inputs
from backend.services.remediation_risk import evaluate_strategy_impact
from backend.services.remediation_runtime_checks import collect_runtime_risk_signals
from backend.services.remediation_settings import normalize_remediation_settings
from backend.services.remediation_strategy import (
    build_remediation_state_simulation,
    get_blast_radius,
    get_estimated_resolution_time,
    get_rollback_command,
    get_strategy,
    get_impact_summary,
    list_mode_options_for_action_type,
    list_strategies_for_action_type,
    supports_immediate_reeval,
    strategy_supports_state_simulation,
    validate_strategy,
)
from backend.services.root_credentials_workflow import (
    ROOT_CREDENTIALS_REQUIRED_MESSAGE,
    ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
    is_root_credentials_required_action,
)
from backend.utils.sqs import (
    build_compute_actions_job_payload,
    build_reconcile_inventory_shard_job_payload,
    parse_queue_region,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actions", tags=["actions"])

_RUNTIME_RISK_OPTION_STRATEGIES = frozenset(
    {
        "s3_bucket_block_public_access_standard",
        "s3_migrate_cloudfront_oac_private",
        "s3_enable_access_logging_guided",
        "s3_enforce_ssl_strict_deny",
        "s3_enforce_ssl_with_principal_exemptions",
        "s3_enable_abort_incomplete_uploads",
        "iam_root_key_delete",
    }
)

_RUNTIME_CONTEXT_OPTION_STRATEGIES = frozenset(
    {
        "s3_enable_sse_kms_guided",
        "config_enable_account_local_delivery",
        "config_enable_centralized_delivery",
        "cloudtrail_enable_guided",
    }
)


# ---------------------------------------------------------------------------
# POST /actions/compute (Step 5.4)
# ---------------------------------------------------------------------------

class ComputeActionsRequest(BaseModel):
    """Optional scope for action computation."""

    account_id: Optional[str] = Field(default=None, description="AWS account ID (12 digits). Omit for tenant-wide.")
    region: Optional[str] = Field(default=None, description="AWS region. Requires account_id if set.")


class ComputeActionsResponse(BaseModel):
    """Response for successful compute trigger (202 Accepted)."""

    message: str = "Action computation job queued"
    tenant_id: str = Field(..., description="Tenant UUID")
    scope: dict = Field(default_factory=dict, description="Scope used: account_id and/or region if provided")


class ReconcileActionsRequest(BaseModel):
    """Scope for action reconciliation enqueue."""

    account_id: str = Field(..., description="AWS account ID (12 digits).")
    region: Optional[str] = Field(
        default=None,
        description="AWS region. If omitted, all configured regions for the account are reconciled.",
    )


class ReconcileActionsResponse(BaseModel):
    """Response for successful reconcile enqueue (202 Accepted)."""

    message: str = "Action reconciliation jobs queued"
    tenant_id: str = Field(..., description="Tenant UUID")
    scope: dict = Field(default_factory=dict, description="Scope used: account_id and/or region if provided")
    enqueued_jobs: int = Field(..., description="Number of reconcile shard jobs enqueued")


# ---------------------------------------------------------------------------
# GET /actions, GET /actions/{id}, PATCH /actions/{id} (Step 5.5)
# ---------------------------------------------------------------------------

class ActionScoreFactorProvenance(BaseModel):
    """One provenance record behind a score-factor shift."""

    source: str
    observed_at: str | None = None
    decay_applied: float
    final_contribution: int
    base_contribution: int | None = None


class ActionScoreFactor(BaseModel):
    """One explainable factor behind an action score."""

    factor_name: str
    weight: int
    contribution: int
    evidence_source: str
    signals: list[str] = Field(default_factory=list)
    explanation: str
    provenance: list[ActionScoreFactorProvenance] = Field(default_factory=list)


class ActionCriticalityDimension(BaseModel):
    """One explicit business-criticality dimension."""

    dimension: str
    label: str
    weight: int
    matched: bool
    contribution: int
    signals: list[str] = Field(default_factory=list)
    explanation: str


class ActionCriticality(BaseModel):
    """Resolved business-criticality state for one action."""

    status: Literal["known", "unknown"]
    score: int
    tier: Literal["critical", "high", "medium", "unknown"]
    weight: int
    dimensions: list[ActionCriticalityDimension] = Field(default_factory=list)
    explanation: str


class ActionBusinessImpactMatrixPosition(BaseModel):
    """Matrix coordinates used for business-impact ranking."""

    row: Literal["critical", "high", "medium", "low"]
    column: Literal["critical", "high", "medium", "unknown"]
    cell: str
    risk_weight: int
    criticality_weight: int
    rank: int
    explanation: str


class ActionBusinessImpact(BaseModel):
    """Transparent risk x criticality payload."""

    technical_risk_score: int
    technical_risk_tier: Literal["critical", "high", "medium", "low"]
    criticality: ActionCriticality
    matrix_position: ActionBusinessImpactMatrixPosition
    summary: str


class ActionSLAStatus(BaseModel):
    """Computed SLA state for one action."""

    risk_tier: Literal["critical", "high", "medium", "low"]
    due_in_hours: int
    expiring_in_hours: int
    due_at: str
    expiring_at: str
    state: Literal["on_track", "expiring", "overdue"]
    is_expiring: bool
    is_overdue: bool
    hours_until_due: int | None = None
    hours_overdue: int | None = None
    escalation_level: Literal["warning", "breach"] | None = None
    escalation_eligible: bool = False
    escalation_reason: str | None = None
    has_active_exception: bool = False


class OwnerQueueCounters(BaseModel):
    """Owner-queue counts for the current filtered scope."""

    open: int = 0
    expiring: int = 0
    overdue: int = 0
    blocked_fixes: int = 0
    expiring_exceptions: int = 0


class ActionListItem(BaseModel):
    """Single action in list response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    action_type: str
    target_id: str
    account_id: str
    region: str | None
    score: int
    score_components: dict[str, Any] | None = None
    score_factors: list[ActionScoreFactor] = Field(default_factory=list)
    business_impact: ActionBusinessImpact
    priority: int
    status: str
    title: str
    control_id: str | None
    resource_id: str | None
    owner_type: str | None = None
    owner_key: str | None = None
    owner_label: str | None = None
    updated_at: str | None
    finding_count: int
    # Step 6.3: exception state (on-read expiry)
    exception_id: str | None = None
    exception_expires_at: str | None = None
    exception_expired: bool | None = None
    sla: ActionSLAStatus | None = None
    # Optional execution-group fields (group_by=batch)
    is_batch: bool = False
    batch_action_count: int | None = None
    batch_finding_count: int | None = None


class ActionsListResponse(BaseModel):
    """Paginated list of actions."""

    items: list[ActionListItem]
    total: int
    owner_queue_counters: OwnerQueueCounters | None = None


class ActionDetailFinding(BaseModel):
    """Finding summary in action detail."""

    id: str
    finding_id: str
    severity_label: str
    title: str
    resource_id: str | None
    account_id: str
    region: str
    updated_at: str | None


class ActionRecommendationMatrixPosition(BaseModel):
    """Matrix location used to derive the recommendation mode."""

    risk_tier: Literal["low", "medium", "high"]
    business_criticality: Literal["low", "medium", "high"]
    cell: str


class ActionRecommendationEvidence(BaseModel):
    """Auditable evidence used to derive the recommendation."""

    score: int
    context_incomplete: bool
    data_sensitivity: float
    internet_exposure: float
    privilege_level: float
    exploit_signals: float
    matched_signals: list[str] = Field(default_factory=list)


class ActionRecommendationResponse(BaseModel):
    """Recommendation mode derived from the risk x criticality matrix."""

    mode: Literal["pr_only", "exception_review"]
    default_mode: Literal["pr_only", "exception_review"]
    advisory: bool
    enforced_by_policy: str | None = None
    rationale: str
    matrix_position: ActionRecommendationMatrixPosition
    evidence: ActionRecommendationEvidence


class ActionDetailResponse(BaseModel):
    """Full action with linked findings."""

    id: str
    tenant_id: str
    action_type: str
    target_id: str
    account_id: str
    region: str | None
    score: int
    score_components: dict[str, Any] | None
    score_factors: list[ActionScoreFactor] = Field(default_factory=list)
    business_impact: ActionBusinessImpact
    context_incomplete: bool = False
    priority: int
    status: str
    title: str
    description: str | None
    what_is_wrong: str
    what_the_fix_does: str
    control_id: str | None
    resource_id: str | None
    resource_type: str | None
    owner_type: str
    owner_key: str
    owner_label: str
    created_at: str | None
    updated_at: str | None
    findings: list[ActionDetailFinding]
    # Step 6.3: exception state (on-read expiry)
    exception_id: str | None = None
    exception_expires_at: str | None = None
    exception_expired: bool | None = None
    sla: ActionSLAStatus | None = None
    recommendation: ActionRecommendationResponse
    execution_guidance: list["ActionExecutionGuidance"] = Field(default_factory=list)
    implementation_artifacts: list[ActionImplementationArtifactLink] = Field(default_factory=list)
    graph_context: "ActionGraphContext"
    attack_path_view: "ActionAttackPathView"
    path_id: str | None = None


class ExecutionGuidanceCheck(BaseModel):
    """One execution-check item for action detail guidance."""

    code: str
    status: Literal["pass", "warn", "unknown", "fail", "info"]
    message: str


class ExecutionGuidanceRollback(BaseModel):
    """Rollback guidance for one action strategy."""

    summary: str
    command: str
    notes: list[str] = Field(default_factory=list)


class ActionExecutionGuidance(BaseModel):
    """Execution guidance entry for one actionable remediation strategy."""

    strategy_id: str
    label: str
    mode: Literal["pr_only"]
    recommended: bool
    blast_radius: Literal["account", "resource", "access_changing"]
    blast_radius_summary: str
    pre_checks: list[ExecutionGuidanceCheck] = Field(default_factory=list)
    expected_outcome: str
    post_checks: list[ExecutionGuidanceCheck] = Field(default_factory=list)
    rollback: ExecutionGuidanceRollback


class ActionGraphLimits(BaseModel):
    """Bounded graph-traversal limits applied to action detail context."""

    max_related_findings: int
    max_related_actions: int
    max_inventory_assets: int
    max_connected_assets: int
    max_identity_nodes: int
    max_blast_radius_neighbors: int


class ActionGraphAsset(BaseModel):
    """One graph-connected asset related to the anchor action."""

    label: str
    resource_id: str | None = None
    resource_type: str | None = None
    resource_key: str | None = None
    relationship: str
    finding_count: int = 0
    action_count: int = 0
    inventory_services: list[str] = Field(default_factory=list)


class ActionGraphIdentityNode(BaseModel):
    """One node in the graph-derived identity path."""

    node_type: Literal["principal", "account", "resource"]
    label: str
    value: str
    source: str


class ActionBlastRadiusNeighbor(BaseModel):
    """One bounded blast-radius neighborhood summary item."""

    scope: Literal["anchor", "account", "related"]
    label: str
    resource_id: str | None = None
    resource_type: str | None = None
    resource_key: str | None = None
    finding_count: int = 0
    open_action_count: int = 0
    inventory_service_count: int = 0
    controls: list[str] = Field(default_factory=list)


class ActionGraphContext(BaseModel):
    """Additive graph-backed action detail context."""

    status: Literal["available", "unavailable"]
    availability_reason: str | None = None
    source: str
    connected_assets: list[ActionGraphAsset] = Field(default_factory=list)
    identity_path: list[ActionGraphIdentityNode] = Field(default_factory=list)
    blast_radius_neighborhood: list[ActionBlastRadiusNeighbor] = Field(default_factory=list)
    truncated_sections: list[str] = Field(default_factory=list)
    limits: ActionGraphLimits


class ActionAttackPathNode(BaseModel):
    """One bounded node in the attack-path story."""

    node_id: str
    kind: Literal["entry_point", "identity", "target_asset", "business_impact", "next_step"]
    label: str
    detail: str | None = None
    badges: list[str] = Field(default_factory=list)


class ActionAttackPathEdge(BaseModel):
    """One directional connection between attack-path nodes."""

    source_node_id: str
    target_node_id: str
    label: str


class ActionAttackPathView(BaseModel):
    """Bounded visual attack story for action detail."""

    status: Literal["available", "partial", "unavailable", "context_incomplete"]
    summary: str
    path_nodes: list[ActionAttackPathNode] = Field(default_factory=list)
    path_edges: list[ActionAttackPathEdge] = Field(default_factory=list)
    entry_points: list[ActionAttackPathNode] = Field(default_factory=list)
    target_assets: list[ActionAttackPathNode] = Field(default_factory=list)
    business_impact_summary: str | None = None
    risk_reasons: list[str] = Field(default_factory=list)
    recommendation_summary: str | None = None
    confidence: float = 0.0
    truncated: bool = False
    availability_reason: str | None = None


class AttackPathSummaryItem(BaseModel):
    """One ranked attack-path summary row."""

    id: str
    status: Literal["available", "partial", "unavailable", "context_incomplete"]
    rank: int
    confidence: float = 0.0
    entry_points: list[ActionAttackPathNode] = Field(default_factory=list)
    target_assets: list[ActionAttackPathNode] = Field(default_factory=list)
    summary: str
    business_impact_summary: str | None = None
    recommended_fix_summary: str | None = None
    owner_labels: list[str] = Field(default_factory=list)
    linked_action_ids: list[str] = Field(default_factory=list)
    rank_factors: list["AttackPathRankFactor"] = Field(default_factory=list)
    freshness: Optional["AttackPathFreshness"] = None
    remediation_summary: Optional["AttackPathRemediationSummary"] = None
    runtime_signals: Optional["AttackPathRuntimeSignals"] = None
    closure_targets: Optional["AttackPathClosureTargets"] = None
    governance_summary: Optional["AttackPathExternalWorkflowSummary"] = None
    access_scope: Optional["AttackPathAccessScope"] = None
    computed_at: str | None = None
    stale_after: str | None = None
    is_stale: bool = False


class AttackPathRankFactor(BaseModel):
    """Explainable factor contributing to attack-path rank."""

    name: str
    label: str
    direction: Literal["positive", "negative"]
    score: float
    weight: float
    weighted_impact: float
    explanation: str


class AttackPathFreshness(BaseModel):
    """Freshness summary for one attack path."""

    score: float
    observed_at: str | None = None


class AttackPathRuntimeSignals(BaseModel):
    """Additive runtime and reachability truth for a shared path."""

    workload_presence: Literal["present", "unknown"]
    publicly_reachable: bool
    sensitive_target_count: int = 0
    identity_hops: int = 0
    confidence: float = 0.0
    summary: str


class AttackPathExposureValidation(BaseModel):
    """Bounded exposure validation summary."""

    status: Literal["verified", "partial", "unverified"]
    summary: str
    observed_at: str | None = None


class AttackPathRepositoryLink(BaseModel):
    """One repo-aware code target tied to the path."""

    provider: str
    repository: str
    base_branch: str | None = None
    root_path: str | None = None
    source_run_id: str | None = None


class AttackPathCodeContext(BaseModel):
    """Code-to-cloud linkage summary for a shared path."""

    owner_label: str
    service_owner_key: str | None = None
    repository_count: int = 0
    implementation_artifact_count: int = 0
    summary: str


class AttackPathClosureTargets(BaseModel):
    """Closure projection for linked actions on a shared path."""

    open_action_ids: list[str] = Field(default_factory=list)
    in_progress_action_ids: list[str] = Field(default_factory=list)
    resolved_action_ids: list[str] = Field(default_factory=list)
    summary: str


class AttackPathExternalWorkflowSummary(BaseModel):
    """External ticket/chat workflow projection for a shared path."""

    provider_count: int = 0
    drifted_count: int = 0
    in_sync_count: int = 0
    linked_items: list[str] = Field(default_factory=list)
    summary: str


class AttackPathExceptionSummary(BaseModel):
    """Exception visibility for linked actions on a shared path."""

    active_count: int = 0
    expiring_count: int = 0
    summary: str


class AttackPathEvidenceExports(BaseModel):
    """Evidence/export readiness summary for a shared path."""

    evidence_item_count: int = 0
    implementation_artifact_count: int = 0
    export_ready: bool = False
    summary: str


class AttackPathAccessScope(BaseModel):
    """Tenant-scoped access and evidence-visibility summary."""

    scope: Literal["tenant_scoped"]
    evidence_visibility: Literal["full"]
    restricted_sections: list[str] = Field(default_factory=list)
    export_allowed: bool = True


class AttackPathOwner(BaseModel):
    """One owner attached to a shared path."""

    key: str | None = None
    label: str


class AttackPathLinkedAction(BaseModel):
    """One linked action attached to a shared path."""

    id: str
    title: str
    priority: int
    status: str
    owner_label: str


class AttackPathBusinessImpact(BaseModel):
    """Shared business-impact summary for a path."""

    summary: str | None = None
    criticality_tier: str | None = None
    criticality_score: int | float | None = None


class AttackPathRecommendedFix(BaseModel):
    """Recommended fix summary for a path."""

    summary: str | None = None
    action_type: str | None = None


class AttackPathEvidenceItem(BaseModel):
    """One evidence item contributing to the path record."""

    type: str
    id: str
    label: str
    updated_at: str | None = None


class AttackPathProvenanceItem(BaseModel):
    """One provenance source contributing to the path record."""

    source: str
    kind: str


class AttackPathDetailResponse(BaseModel):
    """Full bounded detail for a shared attack path."""

    id: str
    status: Literal["available", "partial", "unavailable", "context_incomplete"]
    rank: int
    rank_factors: list[AttackPathRankFactor] = Field(default_factory=list)
    confidence: float = 0.0
    freshness: AttackPathFreshness | None = None
    path_nodes: list[ActionAttackPathNode] = Field(default_factory=list)
    path_edges: list[ActionAttackPathEdge] = Field(default_factory=list)
    entry_points: list[ActionAttackPathNode] = Field(default_factory=list)
    target_assets: list[ActionAttackPathNode] = Field(default_factory=list)
    business_impact: AttackPathBusinessImpact
    risk_reasons: list[str] = Field(default_factory=list)
    owners: list[AttackPathOwner] = Field(default_factory=list)
    recommended_fix: AttackPathRecommendedFix
    linked_actions: list[AttackPathLinkedAction] = Field(default_factory=list)
    evidence: list[AttackPathEvidenceItem] = Field(default_factory=list)
    provenance: list[AttackPathProvenanceItem] = Field(default_factory=list)
    remediation_summary: Optional["AttackPathRemediationSummary"] = None
    runtime_signals: Optional["AttackPathRuntimeSignals"] = None
    exposure_validation: Optional["AttackPathExposureValidation"] = None
    code_context: Optional["AttackPathCodeContext"] = None
    linked_repositories: list["AttackPathRepositoryLink"] = Field(default_factory=list)
    implementation_artifacts: list[ActionImplementationArtifactLink] = Field(default_factory=list)
    closure_targets: Optional["AttackPathClosureTargets"] = None
    external_workflow_summary: Optional["AttackPathExternalWorkflowSummary"] = None
    exception_summary: Optional["AttackPathExceptionSummary"] = None
    evidence_exports: Optional["AttackPathEvidenceExports"] = None
    access_scope: Optional["AttackPathAccessScope"] = None
    computed_at: str | None = None
    stale_after: str | None = None
    is_stale: bool = False
    refresh_status: str | None = None
    truncated: bool = False
    availability_reason: str | None = None


class AttackPathRemediationSummary(BaseModel):
    """Bounded remediation-rollup summary for linked actions on a path."""

    linked_actions_total: int = 0
    open_actions: int = 0
    in_progress_actions: int = 0
    resolved_actions: int = 0
    highest_priority_open: int | None = None
    coverage_summary: str


class AttackPathViewOption(BaseModel):
    """One bounded preset view available on the Attack Paths surface."""

    key: str
    label: str
    description: str


class AttackPathsListResponse(BaseModel):
    """Paginated list of ranked attack paths."""

    items: list[AttackPathSummaryItem] = Field(default_factory=list)
    total: int = 0
    selected_view: str | None = None
    available_views: list[AttackPathViewOption] = Field(default_factory=list)


_ACTION_FIX_SUMMARY_BY_TYPE: dict[str, str] = {
    "s3_block_public_access": "Enables account-level S3 Block Public Access to stop broad public exposure.",
    "enable_security_hub": "Enables Security Hub and default standards to restore security visibility.",
    "enable_guardduty": "Enables GuardDuty detector coverage in the target region.",
    "s3_bucket_block_public_access": "Adds bucket-level public access blocks to prevent public ACL/policy exposure.",
    "s3_bucket_encryption": "Enforces default server-side encryption on the affected S3 bucket.",
    "sg_restrict_public_ports": "Restricts risky inbound security-group rules on unauthorized public ports.",
    "cloudtrail_enabled": "Enables CloudTrail so account activity is logged for audit and detection.",
    "aws_config_enabled": "Enables AWS Config recorder and delivery channel for continuous config tracking.",
    "ssm_block_public_sharing": "Disables public sharing for SSM documents to reduce unauthorized exposure.",
    "ebs_snapshot_block_public_access": "Blocks public sharing of EBS snapshots for this account and region.",
    "ebs_default_encryption": "Enables EBS default encryption for newly created volumes.",
    "s3_bucket_require_ssl": "Adds policy enforcement so bucket access requires TLS/SSL.",
    "iam_root_access_key_absent": "Guides removal of root user access keys and restoration of safer IAM access.",
    "s3_bucket_access_logging": "Configures server access logging to improve traceability of bucket access.",
    "s3_bucket_lifecycle_configuration": "Applies lifecycle rules to enforce retention and cost-control posture.",
    "s3_bucket_encryption_kms": "Enforces SSE-KMS encryption policy for the affected S3 bucket.",
}

_ATTACK_PATH_ACTION_SCAN_HARD_CAP = 20


def _option_recommended(strategy: dict[str, Any], tenant_settings: dict[str, Any] | None) -> bool:
    if strategy.get("action_type") != "aws_config_enabled":
        return bool(strategy["recommended"])
    config_settings = normalize_remediation_settings(tenant_settings).get("config", {})
    delivery_mode = str(config_settings.get("delivery_mode") or "").strip()
    if delivery_mode == "account_local_delivery":
        return strategy["strategy_id"] == "config_enable_account_local_delivery"
    if delivery_mode == "centralized_delivery":
        return strategy["strategy_id"] == "config_enable_centralized_delivery"
    return bool(strategy["recommended"])


def _action_target_label(action: Action) -> str:
    if action.resource_id:
        return action.resource_id
    if action.target_id:
        return action.target_id
    return "the affected resource"


def _build_what_is_wrong(action: Action) -> str:
    description = (action.description or "").strip()
    if description:
        return description
    title = (action.title or "").strip()
    if title:
        return title
    control = (action.control_id or "Unknown control").strip()
    return f"{control} is failing for {_action_target_label(action)}."


def _build_what_the_fix_does(action: Action) -> str:
    known = _ACTION_FIX_SUMMARY_BY_TYPE.get((action.action_type or "").strip())
    if known:
        return known
    control = (action.control_id or "the failing control").strip()
    return f"Applies the configured remediation workflow to address {control} findings."


class PatchActionRequest(BaseModel):
    """Request body for PATCH /actions/{id}."""

    status: Literal["in_progress", "resolved", "suppressed"] = Field(..., description="New workflow status")


def _patch_action_status_sync(
    session,
    *,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    target_status: str,
    actor_user_id: uuid.UUID | None,
) -> None:
    result = session.execute(select(Action).where(Action.id == action_id, Action.tenant_id == tenant_id))
    action = result.scalar_one_or_none()
    if action is None:
        raise ValueError(f"Action not found: {action_id}")
    apply_canonical_action_status(
        session,
        action=action,
        target_status=target_status,
        source="api.actions.patch",
        actor_user_id=actor_user_id,
        detail="Canonical action state updated via PATCH /api/actions/{id}.",
    )


class RemediationPreviewResponse(BaseModel):
    """Response for GET /actions/{id}/remediation-preview (Step 8.4 dry-run)."""

    compliant: bool = Field(..., description="True if already compliant; no fix needed")
    message: str = Field(..., description="Human-readable pre-check result")
    will_apply: bool = Field(..., description="True if not compliant and fix would be applied")
    impact_summary: str | None = Field(
        default=None,
        description="Optional human-readable impact summary composed from selected strategy choices.",
    )
    before_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Best-effort snapshot of relevant resource state before apply.",
    )
    after_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Best-effort predicted resource state after apply.",
    )
    diff_lines: list[dict[str, str]] = Field(
        default_factory=list,
        description="Line-by-line before/after delta entries.",
    )
    resolution: "RemediationPreviewResolutionResponse | None" = Field(
        default=None,
        description="Optional Wave 2 profile-resolution metadata for the selected strategy family.",
    )


class DependencyCheckResponse(BaseModel):
    """One dependency check entry for remediation strategy safety."""

    code: str
    status: Literal["pass", "warn", "unknown", "fail"]
    message: str


class RemediationOptionResponse(BaseModel):
    """One remediation strategy option for an action."""

    strategy_id: str
    label: str
    mode: Literal["pr_only"]
    risk_level: Literal["low", "medium", "high"]
    recommended: bool
    requires_inputs: bool
    input_schema: dict[str, Any]
    dependency_checks: list[DependencyCheckResponse]
    warnings: list[str]
    supports_exception_flow: bool
    exception_only: bool
    impact_text: str | None = None
    rollback_command: str | None = None
    estimated_resolution_time: str = "12-24 hours"
    supports_immediate_reeval: bool = False
    blast_radius: Literal["account", "resource", "access_changing"] = "resource"
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional strategy-specific runtime context for UI defaults and helper options.",
    )
    profiles: list["RemediationProfileResponse"] = Field(
        default_factory=list,
        description="Additive Wave 2 compatibility profiles nested beneath the strategy row.",
    )
    recommended_profile_id: str | None = Field(
        default=None,
        description="Recommended profile ID for this strategy in the current action context.",
    )
    missing_defaults: list[str] = Field(
        default_factory=list,
        description="Tenant remediation defaults that are still missing for this strategy/profile row.",
    )
    blocked_reasons: list[str] = Field(
        default_factory=list,
        description="Blocking reasons currently known for this strategy/profile row.",
    )
    preservation_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Resolver-side preservation evidence summary for the current strategy/profile row.",
    )
    decision_rationale: str = Field(
        default="",
        description="Short rationale for the current strategy/profile recommendation.",
    )


class RemediationProfileResponse(BaseModel):
    """One additive compatibility-profile row exposed beneath a strategy."""

    profile_id: str
    support_tier: Literal[
        "deterministic_bundle",
        "review_required_bundle",
        "manual_guidance_only",
    ]
    recommended: bool
    requires_inputs: bool
    supports_exception_flow: bool
    exception_only: bool


class RemediationPreviewResolutionResponse(BaseModel):
    """Canonical normalized resolution metadata exposed on remediation preview."""

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


class TriggerReevalRequest(BaseModel):
    """Optional payload to scope immediate re-evaluation behavior by strategy."""

    strategy_id: str | None = Field(default=None, description="Optional selected strategy ID.")


class TriggerReevalResponse(BaseModel):
    """Response for POST /actions/{id}/trigger-reeval."""

    message: str = "Immediate re-evaluation jobs queued"
    tenant_id: str
    action_id: str
    strategy_id: str | None = None
    estimated_resolution_time: str
    supports_immediate_reeval: bool
    scope: dict[str, str] = Field(default_factory=dict)
    enqueued_jobs: int


class RemediationOptionsResponse(BaseModel):
    """Available remediation options for an action, including risk signals."""

    action_id: str
    action_type: str
    mode_options: list[Literal["pr_only"]]
    strategies: list[RemediationOptionResponse]
    recommendation: ActionRecommendationResponse
    manual_high_risk: bool = False
    pre_execution_notice: str | None = None
    runbook_url: str | None = None


def _mode_options_for_action(action_type: str) -> list[Literal["pr_only"]]:
    strategies = list_strategies_for_action_type(action_type)
    if strategies:
        return list_mode_options_for_action_type(action_type)

    # Backward-compatible behavior for action types not yet migrated to strategy catalog.
    return ["pr_only"]


def _action_score_value(action: Action) -> int:
    raw_score = getattr(action, "score", None)
    if raw_score is None:
        raw_score = getattr(action, "priority", 0)
    return int(raw_score or 0)


def _score_components_payload(action: Action) -> dict[str, Any] | None:
    payload = getattr(action, "score_components", None)
    return payload if isinstance(payload, dict) else None


def _score_factors_payload(
    action: Action | None,
    *,
    fallback_score: int | None = None,
    legacy_source: str = "stored action.score",
) -> list[ActionScoreFactor]:
    if action is None:
        raw_factors = build_score_factors(None, stored_score=fallback_score, legacy_source=legacy_source)
    else:
        raw_factors = build_score_factors(
            _score_components_payload(action),
            stored_score=_action_score_value(action),
            legacy_source=legacy_source,
    )
    return [ActionScoreFactor(**factor) for factor in raw_factors]


def _context_incomplete_payload(action: Action | None) -> bool:
    components = _score_components_payload(action) if action is not None else None
    if not isinstance(components, dict):
        return True
    marker = components.get("context_incomplete")
    if isinstance(marker, bool):
        return marker
    toxic = components.get("toxic_combinations")
    if isinstance(toxic, dict):
        return bool(toxic.get("context_incomplete"))
    return True


def _action_recommendation_payload(
    action: Action,
    *,
    mode_options: list[Literal["pr_only"]] | None = None,
    manual_high_risk: bool = False,
) -> ActionRecommendationResponse:
    payload = build_action_recommendation(
        action,
        mode_options=list(mode_options or []),
        manual_high_risk=manual_high_risk,
    )
    return ActionRecommendationResponse(**payload)


def _owner_attr(action: Action, attr_name: str, default: str | None) -> str | None:
    value = getattr(action, attr_name, default)
    if isinstance(value, str) and value.strip():
        return value
    return default


def _has_active_exception(exception_state: dict | None) -> bool:
    return bool((exception_state or {}).get("exception_id"))


def _action_sla_payload(
    action: Action,
    *,
    exception_state: dict | None = None,
    now: datetime | None = None,
) -> ActionSLAStatus | None:
    computed = compute_action_sla(
        created_at=getattr(action, "created_at", None),
        score=_action_score_value(action),
        now=now,
        has_active_exception=_has_active_exception(exception_state),
    )
    if computed is None:
        return None
    return _serialize_action_sla(computed)


def _serialize_action_sla(sla: ComputedActionSLAStatus) -> ActionSLAStatus:
    return ActionSLAStatus(
        risk_tier=sla.risk_tier,
        due_in_hours=sla.due_in_hours,
        expiring_in_hours=sla.expiring_in_hours,
        due_at=sla.due_at.isoformat(),
        expiring_at=sla.expiring_at.isoformat(),
        state=sla.state,
        is_expiring=sla.is_expiring,
        is_overdue=sla.is_overdue,
        hours_until_due=sla.hours_until_due,
        hours_overdue=sla.hours_overdue,
        escalation_level=sla.escalation_level,
        escalation_eligible=sla.escalation_eligible,
        escalation_reason=sla.escalation_reason,
        has_active_exception=sla.has_active_exception,
    )


def _action_score_sql_expr() -> object:
    return func.coalesce(Action.score, Action.priority, 0)


def _business_impact_json_int(*keys: str) -> object:
    expr = Action.score_components
    for key in keys:
        expr = expr[key]
    return cast(expr.astext, Integer)


def _risk_weight_sql_expr(score_expr: object | None = None) -> object:
    resolved_score = score_expr if score_expr is not None else _action_score_sql_expr()
    fallback = case((resolved_score >= 85, 4), (resolved_score >= 65, 3), (resolved_score >= 40, 2), else_=1)
    return func.coalesce(_business_impact_json_int("business_impact", "matrix_position", "risk_weight"), fallback)


def _criticality_weight_sql_expr() -> object:
    return func.coalesce(_business_impact_json_int("business_impact", "matrix_position", "criticality_weight"), 1)


def _business_impact_rank_sql_expr(score_expr: object | None = None) -> object:
    resolved_score = score_expr if score_expr is not None else _action_score_sql_expr()
    return (_risk_weight_sql_expr(resolved_score) * 10000) + (_criticality_weight_sql_expr() * 100) + resolved_score


def _active_action_exception_subquery(tenant_uuid: Any, now: datetime) -> object:
    return (
        select(
            Exception.entity_id.label("action_id"),
            Exception.expires_at.label("exception_expires_at"),
        )
        .where(Exception.tenant_id == tenant_uuid)
        .where(Exception.entity_type == EntityType.action)
        .where(Exception.expires_at > now)
        .subquery()
    )


def _unresolved_action_expr(use_effective_visibility: bool, effective_open_expr: object) -> object:
    currently_open = or_(Action.status == "open", Action.status == "in_progress")
    if not use_effective_visibility:
        return currently_open
    return or_(currently_open, and_(Action.status == "resolved", effective_open_expr))


def _overdue_cutoff_expr(now: datetime) -> object:
    return action_sla_overdue_cutoff_expr(
        now=now,
        score_expr=_action_score_sql_expr(),
    )


def _overdue_action_expr(now: datetime) -> object:
    return Action.created_at <= _overdue_cutoff_expr(now)


def _expiring_action_expr(now: datetime) -> object:
    return action_sla_expiring_expr(
        created_at_expr=Action.created_at,
        now=now,
        score_expr=_action_score_sql_expr(),
    )


def _expiring_exception_expr(active_exception_sq: object, now: datetime) -> object:
    return and_(
        active_exception_sq.c.action_id.is_not(None),
        active_exception_sq.c.exception_expires_at
        <= now + timedelta(days=settings.ACTIONS_OWNER_QUEUE_EXPIRING_EXCEPTION_DAYS),
    )


def _owner_queue_filter_expr(
    owner_queue: str,
    *,
    unresolved_expr: object,
    active_exception_sq: object,
    now: datetime,
) -> object:
    has_active_exception = active_exception_sq.c.action_id.is_not(None)
    expiring_exception = _expiring_exception_expr(active_exception_sq, now)
    overdue = _overdue_action_expr(now)
    expiring = _expiring_action_expr(now)
    if owner_queue == "expiring_exceptions":
        return and_(unresolved_expr, expiring_exception)
    if owner_queue == "blocked_fixes":
        return and_(unresolved_expr, has_active_exception, ~expiring_exception)
    if owner_queue == "overdue":
        return and_(unresolved_expr, ~has_active_exception, overdue)
    if owner_queue == "expiring":
        return and_(unresolved_expr, ~has_active_exception, expiring)
    return and_(unresolved_expr, ~has_active_exception, ~overdue, ~expiring)


async def _load_owner_queue_counters(
    db: AsyncSession,
    *,
    scope_filters: list[object],
    finding_counts: object,
    active_exception_sq: object,
    unresolved_expr: object,
    now: datetime,
) -> OwnerQueueCounters:
    has_active_exception = active_exception_sq.c.action_id.is_not(None)
    expiring_exception = _expiring_exception_expr(active_exception_sq, now)
    overdue = _overdue_action_expr(now)
    expiring = _expiring_action_expr(now)
    open_queue = and_(unresolved_expr, ~has_active_exception, ~overdue, ~expiring)
    expiring_queue = and_(unresolved_expr, ~has_active_exception, expiring)
    overdue_queue = and_(unresolved_expr, ~has_active_exception, overdue)
    blocked_queue = and_(unresolved_expr, has_active_exception, ~expiring_exception)
    expiring_exception_queue = and_(unresolved_expr, expiring_exception)

    result = await db.execute(
        select(
            func.coalesce(func.sum(case((open_queue, 1), else_=0)), 0).label("open"),
            func.coalesce(func.sum(case((expiring_queue, 1), else_=0)), 0).label("expiring"),
            func.coalesce(func.sum(case((overdue_queue, 1), else_=0)), 0).label("overdue"),
            func.coalesce(func.sum(case((blocked_queue, 1), else_=0)), 0).label("blocked_fixes"),
            func.coalesce(func.sum(case((expiring_exception_queue, 1), else_=0)), 0).label("expiring_exceptions"),
        )
        .select_from(Action)
        .outerjoin(finding_counts, Action.id == finding_counts.c.action_id)
        .outerjoin(active_exception_sq, active_exception_sq.c.action_id == Action.id)
        .where(*scope_filters)
    )
    row = result.one()
    return OwnerQueueCounters(
        open=int(row.open or 0),
        expiring=int(row.expiring or 0),
        overdue=int(row.overdue or 0),
        blocked_fixes=int(row.blocked_fixes or 0),
        expiring_exceptions=int(row.expiring_exceptions or 0),
    )


def _action_to_list_item(
    action: Action,
    exception_state: dict | None = None,
    finding_count: int | None = None,
    status_override: str | None = None,
    now: datetime | None = None,
) -> ActionListItem:
    """Build list item from Action; finding_count may be supplied from SQL aggregation."""
    state = exception_state or {}
    resolved_finding_count = finding_count
    if resolved_finding_count is None:
        resolved_finding_count = len(action.action_finding_links or [])
    return ActionListItem(
        id=str(action.id),
        action_type=action.action_type,
        target_id=action.target_id,
        account_id=action.account_id,
        region=action.region,
        score=_action_score_value(action),
        score_components=_score_components_payload(action),
        score_factors=_score_factors_payload(action),
        business_impact=_business_impact_payload(action),
        priority=int(getattr(action, "priority", 0) or 0),
        status=status_override or action.status,
        title=action.title,
        control_id=action.control_id,
        resource_id=action.resource_id,
        owner_type=_owner_attr(action, "owner_type", None),
        owner_key=_owner_attr(action, "owner_key", None),
        owner_label=_owner_attr(action, "owner_label", None),
        updated_at=action.updated_at.isoformat() if action.updated_at else None,
        finding_count=resolved_finding_count,
        exception_id=state.get("exception_id"),
        exception_expires_at=state.get("exception_expires_at"),
        exception_expired=state.get("exception_expired"),
        sla=_action_sla_payload(action, exception_state=state, now=now),
    )


def _finding_effective_status_sql_expr() -> object:
    """SQL expression for user-facing finding status (shadow-aware)."""
    shadow_status = func.upper(func.coalesce(Finding.shadow_status_normalized, ""))
    canonical_status = func.upper(func.coalesce(Finding.status, ""))
    return case(
        (shadow_status == "RESOLVED", "RESOLVED"),
        ((shadow_status == "OPEN") & (canonical_status == "RESOLVED"), "NEW"),
        else_=canonical_status,
    )


def _action_has_effective_open_finding_expr(tenant_uuid: Any) -> object:
    """Correlated SQL expression: action has at least one effective-open linked finding."""
    return exists(
        select(1)
        .select_from(ActionFinding)
        .join(Finding, Finding.id == ActionFinding.finding_id)
        .where(ActionFinding.action_id == Action.id)
        .where(Finding.tenant_id == tenant_uuid)
        .where(_finding_effective_status_sql_expr() != "RESOLVED")
    )


_BATCH_TITLE_BY_ACTION_TYPE = {
    "s3_block_public_access": "S3 account public access hardening",
    "enable_security_hub": "Enable Security Hub",
    "enable_guardduty": "Enable GuardDuty",
    "s3_bucket_block_public_access": "Enforce S3 bucket public access hardening",
    "s3_bucket_encryption": "Enforce S3 bucket encryption",
    "s3_bucket_access_logging": "Enable S3 bucket access logging",
    "s3_bucket_lifecycle_configuration": "Configure S3 bucket lifecycle",
    "s3_bucket_encryption_kms": "Enforce S3 bucket SSE-KMS encryption",
    "sg_restrict_public_ports": "Restrict security-group public ports",
    "cloudtrail_enabled": "Enable CloudTrail",
    "aws_config_enabled": "Enable AWS Config recording",
    "ssm_block_public_sharing": "Block public SSM document sharing",
    "ebs_snapshot_block_public_access": "Restrict EBS snapshot public sharing",
    "ebs_default_encryption": "Enable EBS default encryption",
    "s3_bucket_require_ssl": "Enforce SSL-only S3 access",
    "iam_root_access_key_absent": "Remove IAM root access keys",
}


_MIN_UPDATED_AT = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _batch_title(action_type: str, action_count: int) -> str:
    base = _BATCH_TITLE_BY_ACTION_TYPE.get(action_type, f"{action_type}")
    return f"{base} ({action_count} action{'s' if action_count != 1 else ''})"


def _build_batch_target_id(action: Action) -> str:
    region = action.region or "global"
    return f"batch|{action.action_type}|{action.account_id}|{region}|{action.status}"


def _build_batch_target_id_from_fields(
    action_type: str,
    account_id: str,
    region: str | None,
    status: str,
) -> str:
    resolved_region = region or "global"
    return f"batch|{action_type}|{account_id}|{resolved_region}|{status}"


def _batch_sort_key(item: ActionListItem) -> tuple[int, str, str]:
    return (
        item.business_impact.matrix_position.rank,
        item.updated_at or "",
        item.id,
    )


def _normalize_updated_at(value: datetime | None) -> datetime:
    if value is None:
        return _MIN_UPDATED_AT
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _representative_action_key(action: Action) -> tuple[int, datetime, str]:
    return (_business_impact_rank_value(action), _normalize_updated_at(action.updated_at), str(action.id))


async def _load_batch_representatives(
    db: AsyncSession,
    tenant_uuid: uuid.UUID,
    group_ids: list[str],
) -> dict[str, Action]:
    if not group_ids:
        return {}
    result = await db.execute(
        select(ActionGroupMembership.group_id, Action)
        .join(Action, (Action.id == ActionGroupMembership.action_id) & (Action.tenant_id == ActionGroupMembership.tenant_id))
        .where(ActionGroupMembership.tenant_id == tenant_uuid)
        .where(cast(ActionGroupMembership.group_id, String).in_(group_ids))
    )
    grouped: defaultdict[str, list[Action]] = defaultdict(list)
    for group_id, action in result.all():
        grouped[str(group_id)].append(action)
    return {group_id: max(actions, key=_representative_action_key) for group_id, actions in grouped.items()}


def _group_actions_into_batches(actions: list[Action]) -> list[ActionListItem]:
    """
    Build execution-group list items from individual actions.

    Grouping key: (action_type, account_id, region, status).
    """
    grouped: defaultdict[tuple[str, str, str | None, str], list[Action]] = defaultdict(list)
    for action in actions:
        grouped[(action.action_type, action.account_id, action.region, action.status)].append(action)

    items: list[ActionListItem] = []
    for key, group in grouped.items():
        action_type, account_id, region, status = key
        representative = max(group, key=_representative_action_key)
        max_score = max(_action_score_value(action) for action in group)
        max_updated_at = max((_normalize_updated_at(a.updated_at) for a in group), default=None)
        total_findings = sum(len(a.action_finding_links or []) for a in group)
        action_count = len(group)

        # Skip orphan groups (no linked findings). These typically occur when a
        # recompute remaps findings away from older actions; they should not
        # appear as execution groups in the UI.
        if total_findings == 0:
            continue

        items.append(
            ActionListItem(
                id=str(representative.id),
                action_type=action_type,
                target_id=_build_batch_target_id(representative),
                account_id=account_id,
                region=region,
                score=max_score,
                score_components=None,
                score_factors=_score_factors_payload(representative),
                business_impact=_business_impact_payload(representative, fallback_score=max_score),
                priority=max_score,
                status=status,
                title=_batch_title(action_type, action_count),
                control_id=representative.control_id,
                resource_id=None,
                updated_at=max_updated_at.isoformat() if max_updated_at else None,
                finding_count=total_findings,
                is_batch=True,
                batch_action_count=action_count,
                batch_finding_count=total_findings,
            )
        )

    items.sort(key=_batch_sort_key, reverse=True)
    return items


def _action_to_detail_response(
    action: Action,
    exception_state: dict | None = None,
    now: datetime | None = None,
    account: AwsAccount | None = None,
    recommendation: ActionRecommendationResponse | None = None,
    implementation_artifacts: list[ActionImplementationArtifactLink] | None = None,
    graph_context: dict[str, Any] | None = None,
    attack_path_graph_context: dict[str, Any] | None = None,
) -> ActionDetailResponse:
    """Build detail response from Action; action_finding_links and finding must be loaded."""
    state = exception_state or {}
    findings = []
    for link in action.action_finding_links or []:
        f = link.finding
        if f is None:
            continue
        findings.append(
            ActionDetailFinding(
                id=str(f.id),
                finding_id=f.finding_id,
                severity_label=f.severity_label,
                title=f.title,
                resource_id=f.resource_id,
                account_id=f.account_id,
                region=f.region,
                updated_at=f.updated_at.isoformat() if f.updated_at else None,
            )
        )
    score_factors = _score_factors_payload(action)
    business_impact = _business_impact_payload(action)
    resolved_sla = _action_sla_payload(action, exception_state=state, now=now)
    resolved_recommendation = recommendation or _action_recommendation_payload(action)
    execution_guidance = [
        ActionExecutionGuidance(**guidance)
        for guidance in build_action_execution_guidance(action, account=account)
    ]
    resolved_graph_context = ActionGraphContext(**(graph_context or _default_graph_context_payload()))
    attack_path_view = _attack_path_view_payload(
        action,
        graph_context=attack_path_graph_context or resolved_graph_context.model_dump(),
        business_impact=business_impact,
        recommendation=resolved_recommendation,
        score_factors=score_factors,
        execution_guidance=execution_guidance,
        sla=resolved_sla,
    )
    return ActionDetailResponse(
        id=str(action.id),
        tenant_id=str(action.tenant_id),
        action_type=action.action_type,
        target_id=action.target_id,
        account_id=action.account_id,
        region=action.region,
        score=_action_score_value(action),
        score_components=_score_components_payload(action),
        score_factors=score_factors,
        business_impact=business_impact,
        context_incomplete=_context_incomplete_payload(action),
        priority=int(getattr(action, "priority", 0) or 0),
        status=action.status,
        title=action.title,
        description=action.description,
        what_is_wrong=_build_what_is_wrong(action),
        what_the_fix_does=_build_what_the_fix_does(action),
        control_id=action.control_id,
        resource_id=action.resource_id,
        resource_type=action.resource_type,
        owner_type=_owner_attr(action, "owner_type", UNASSIGNED_OWNER_TYPE) or UNASSIGNED_OWNER_TYPE,
        owner_key=_owner_attr(action, "owner_key", UNASSIGNED_OWNER_KEY) or UNASSIGNED_OWNER_KEY,
        owner_label=_owner_attr(action, "owner_label", UNASSIGNED_OWNER_LABEL) or UNASSIGNED_OWNER_LABEL,
        created_at=action.created_at.isoformat() if action.created_at else None,
        updated_at=action.updated_at.isoformat() if action.updated_at else None,
        findings=findings,
        exception_id=state.get("exception_id"),
        exception_expires_at=state.get("exception_expires_at"),
        exception_expired=state.get("exception_expired"),
        sla=resolved_sla,
        recommendation=resolved_recommendation,
        execution_guidance=execution_guidance,
        implementation_artifacts=implementation_artifacts or [],
        graph_context=resolved_graph_context,
        attack_path_view=attack_path_view,
        path_id=attack_path_id_for_graph_context(attack_path_graph_context or {}, action),
    )


def _attack_path_view_payload(
    action: Action,
    *,
    graph_context: dict[str, Any],
    business_impact: ActionBusinessImpact,
    recommendation: ActionRecommendationResponse,
    score_factors: list[ActionScoreFactor],
    execution_guidance: list[ActionExecutionGuidance],
    sla: ActionSLAStatus | None,
) -> ActionAttackPathView:
    payload = build_action_attack_path_view(
        action,
        graph_context=graph_context,
        business_impact=business_impact.model_dump(),
        recommendation=recommendation.model_dump(),
        score_factors=[factor.model_dump() for factor in score_factors],
        execution_guidance=[guidance.model_dump() for guidance in execution_guidance],
        sla=sla.model_dump() if sla is not None else None,
    )
    return ActionAttackPathView(**payload)


async def _load_action_implementation_artifacts(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    action: Action,
) -> list[ActionImplementationArtifactLink]:
    result = await db.execute(
        select(RemediationRun)
        .where(RemediationRun.tenant_id == tenant_uuid, RemediationRun.action_id == action.id)
        .order_by(RemediationRun.created_at.desc())
        .limit(8)
    )
    runs = result.scalars().all()
    return build_action_implementation_artifacts(runs, action_status=action.status)


async def _load_action_graph_context(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    action: Action,
) -> dict[str, Any]:
    return await build_action_graph_context(db, tenant_id=tenant_uuid, action=action)


async def _load_action_attack_path_graph_context(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    action: Action,
) -> dict[str, Any]:
    return await build_attack_path_graph_context(db, tenant_id=tenant_uuid, action=action)


def _default_graph_context_payload() -> dict[str, Any]:
    return {
        "status": "unavailable",
        "availability_reason": "relationship_context_unavailable",
        "source": "finding_relationship_context+inventory_assets",
        "connected_assets": [],
        "identity_path": [],
        "blast_radius_neighborhood": [],
        "truncated_sections": [],
        "limits": {
            "max_related_findings": 24,
            "max_related_actions": 24,
            "max_inventory_assets": 24,
            "max_connected_assets": 6,
            "max_identity_nodes": 6,
            "max_blast_radius_neighbors": 6,
        },
    }


def _business_impact_payload(
    action: Action | None,
    *,
    fallback_score: int | None = None,
) -> ActionBusinessImpact:
    if action is None:
        payload = build_business_impact_from_components(None, stored_score=fallback_score)
    else:
        payload = build_business_impact_from_components(
            _score_components_payload(action),
            stored_score=_action_score_value(action),
        )
    return ActionBusinessImpact(**payload)


def _business_impact_rank_value(action: Action | None, *, fallback_score: int | None = None) -> int:
    if action is None:
        return business_impact_rank(None, stored_score=fallback_score)
    return business_impact_rank(_score_components_payload(action), stored_score=_action_score_value(action))


@router.get("", response_model=ActionsListResponse)
async def list_actions(
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
    action_type: Annotated[str | None, Query(description="Filter by remediation action type")] = None,
    q: Annotated[str | None, Query(description="Case-insensitive text search across key action fields")] = None,
    ids: Annotated[str | None, Query(description="Comma-separated action IDs to load explicitly")] = None,
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="Filter by status (open, in_progress, resolved, suppressed)"),
    ] = None,
    owner_type: Annotated[
        Literal["user", "team", "service", "unassigned"] | None,
        Query(description="Filter by resolved owner type."),
    ] = None,
    owner_key: Annotated[str | None, Query(description="Filter by normalized owner key.")] = None,
    owner_queue: Annotated[
        Literal["open", "expiring", "overdue", "expiring_exceptions", "blocked_fixes"] | None,
        Query(description="Filter by owner queue bucket."),
    ] = None,
    group_by: Annotated[
        Literal["resource", "batch"],
        Query(description="List mode: 'resource' for individual actions, 'batch' for execution groups."),
    ] = "resource",
    include_orphans: Annotated[
        bool,
        Query(description="Include actions with zero linked findings. Defaults to false."),
    ] = False,
    limit: Annotated[int, Query(ge=1, le=200, description="Max items per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
) -> ActionsListResponse:
    """
    List actions with optional filters and pagination.
    Returns actions scoped to the tenant; each item includes finding_count.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)
    now = datetime.now(timezone.utc)

    finding_counts = (
        select(
            ActionFinding.action_id.label("action_id"),
            func.count(ActionFinding.finding_id).label("finding_count"),
        )
        .group_by(ActionFinding.action_id)
        .subquery()
    )
    finding_count_expr = func.coalesce(finding_counts.c.finding_count, 0)
    use_effective_visibility = settings.ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED
    effective_open_expr = _action_has_effective_open_finding_expr(tenant_uuid)
    normalized_status_filter = status_filter.strip().lower() if status_filter is not None else None
    normalized_owner_type = owner_type.strip().lower() if owner_type is not None else None
    normalized_owner_key = None
    if owner_key is not None:
        normalized_owner_key = normalize_owner_lookup_key(owner_key, normalized_owner_type)
    normalized_owner_queue = owner_queue.strip().lower() if owner_queue is not None else None
    normalized_query = q.strip() if q is not None and q.strip() else None
    requested_action_ids: list[uuid.UUID] = []
    if ids is not None and ids.strip():
        try:
            requested_action_ids = [uuid.UUID(raw_id.strip()) for raw_id in ids.split(",") if raw_id.strip()]
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid action id in ids filter.",
            ) from exc
    active_exception_sq = _active_action_exception_subquery(tenant_uuid, now)
    unresolved_expr = _unresolved_action_expr(use_effective_visibility, effective_open_expr)
    status_filter_expr = None

    action_filters = [Action.tenant_id == tenant_uuid]
    if settings.ONLY_IN_SCOPE_CONTROLS:
        action_filters.append(Action.action_type != "pr_only")
    if account_id is not None:
        action_filters.append(Action.account_id == account_id)
    if region is not None:
        action_filters.append(Action.region == region)
    if control_id is not None:
        equivalent_control_ids = equivalent_control_ids_for_control(control_id)
        if equivalent_control_ids:
            action_filters.append(Action.control_id.in_(equivalent_control_ids))
        else:
            action_filters.append(Action.control_id == control_id.strip())
    if resource_id is not None:
        action_filters.append(Action.resource_id == resource_id.strip())
    if action_type is not None:
        action_filters.append(Action.action_type == action_type.strip())
    if requested_action_ids:
        action_filters.append(Action.id.in_(requested_action_ids))
    if normalized_query is not None:
        query_pattern = f"%{normalized_query}%"
        normalized_query_controls = equivalent_control_ids_for_control(normalized_query)
        query_filters = [
            Action.title.ilike(query_pattern),
            Action.action_type.ilike(query_pattern),
            Action.control_id.ilike(query_pattern),
            Action.resource_id.ilike(query_pattern),
            Action.account_id.ilike(query_pattern),
            Action.region.ilike(query_pattern),
        ]
        if normalized_query_controls:
            query_filters.append(Action.control_id.in_(normalized_query_controls))
        action_filters.append(
            or_(*query_filters)
        )
    if normalized_owner_type is not None:
        action_filters.append(Action.owner_type == normalized_owner_type)
    if normalized_owner_key is not None:
        action_filters.append(Action.owner_key == normalized_owner_key)
    if not include_orphans:
        action_filters.append(finding_count_expr > 0)
    queue_scope_filters = list(action_filters)
    if normalized_status_filter is not None:
        if use_effective_visibility and normalized_status_filter == "open":
            status_filter_expr = or_(
                Action.status == "open",
                and_(Action.status == "resolved", effective_open_expr),
            )
        elif use_effective_visibility and normalized_status_filter == "resolved":
            status_filter_expr = and_(Action.status == "resolved", ~effective_open_expr)
        else:
            status_filter_expr = Action.status == normalized_status_filter
    if normalized_owner_queue is not None:
        action_filters.append(
            _owner_queue_filter_expr(
                normalized_owner_queue,
                unresolved_expr=unresolved_expr,
                active_exception_sq=active_exception_sq,
                now=now,
            )
        )
    resource_filters = list(action_filters)
    if status_filter_expr is not None:
        resource_filters.append(status_filter_expr)

    owner_queue_counters = None
    if normalized_owner_queue is not None:
        owner_queue_counters = await _load_owner_queue_counters(
            db,
            scope_filters=queue_scope_filters,
            finding_counts=finding_counts,
            active_exception_sq=active_exception_sq,
            unresolved_expr=unresolved_expr,
            now=now,
        )

    if group_by == "batch":
        group_filters = [ActionGroup.tenant_id == tenant_uuid]
        if settings.ONLY_IN_SCOPE_CONTROLS:
            group_filters.append(ActionGroup.action_type != "pr_only")
        if account_id is not None:
            group_filters.append(ActionGroup.account_id == account_id)
        if region is not None:
            group_filters.append(ActionGroup.region == region)
        if action_type is not None:
            group_filters.append(ActionGroup.action_type == action_type.strip())

        if use_effective_visibility:
            open_count_expr = func.sum(
                case(
                    (
                        or_(
                            Action.status == "open",
                            and_(Action.status == "resolved", effective_open_expr),
                        ),
                        1,
                    ),
                    else_=0,
                )
            )
            resolved_count_expr = func.sum(
                case(
                    (and_(Action.status == "resolved", ~effective_open_expr), 1),
                    else_=0,
                )
            )
        else:
            open_count_expr = func.sum(case((Action.status == "open", 1), else_=0))
            resolved_count_expr = func.sum(case((Action.status == "resolved", 1), else_=0))
        in_progress_count_expr = func.sum(case((Action.status == "in_progress", 1), else_=0))
        suppressed_count_expr = func.sum(case((Action.status == "suppressed", 1), else_=0))

        grouped_query = (
            select(
                cast(ActionGroup.id, String).label("id"),
                ActionGroup.action_type.label("action_type"),
                ActionGroup.account_id.label("account_id"),
                ActionGroup.region.label("region"),
                func.max(Action.score).label("score"),
                func.max(Action.priority).label("priority"),
                func.max(_business_impact_rank_sql_expr()).label("business_rank"),
                func.max(Action.updated_at).label("updated_at"),
                func.max(Action.control_id).label("control_id"),
                func.count(Action.id).label("action_count"),
                func.coalesce(func.sum(finding_count_expr), 0).label("finding_count"),
                func.coalesce(open_count_expr, 0).label("open_count"),
                func.coalesce(in_progress_count_expr, 0).label("in_progress_count"),
                func.coalesce(resolved_count_expr, 0).label("resolved_count"),
                func.coalesce(suppressed_count_expr, 0).label("suppressed_count"),
            )
            .select_from(ActionGroup)
            .join(
                ActionGroupMembership,
                (ActionGroupMembership.group_id == ActionGroup.id)
                & (ActionGroupMembership.tenant_id == ActionGroup.tenant_id),
            )
            .join(
                Action,
                (Action.id == ActionGroupMembership.action_id)
                & (Action.tenant_id == ActionGroupMembership.tenant_id),
            )
            .outerjoin(finding_counts, Action.id == finding_counts.c.action_id)
            .outerjoin(active_exception_sq, active_exception_sq.c.action_id == Action.id)
            .where(*group_filters, *action_filters)
            .group_by(ActionGroup.id, ActionGroup.action_type, ActionGroup.account_id, ActionGroup.region)
        )

        if normalized_status_filter is not None:
            status_value = normalized_status_filter
            if status_value == "open":
                grouped_query = grouped_query.having(func.coalesce(open_count_expr, 0) > 0)
            elif status_value == "in_progress":
                grouped_query = grouped_query.having(func.coalesce(in_progress_count_expr, 0) > 0)
            elif status_value == "resolved":
                grouped_query = grouped_query.having(
                    func.coalesce(open_count_expr, 0) == 0,
                    func.coalesce(in_progress_count_expr, 0) == 0,
                    func.coalesce(resolved_count_expr, 0) > 0,
                )
            elif status_value == "suppressed":
                grouped_query = grouped_query.having(
                    func.coalesce(open_count_expr, 0) == 0,
                    func.coalesce(in_progress_count_expr, 0) == 0,
                    func.coalesce(resolved_count_expr, 0) == 0,
                    func.coalesce(suppressed_count_expr, 0) > 0,
                )

        if not include_orphans:
            grouped_query = grouped_query.having(func.coalesce(func.sum(finding_count_expr), 0) > 0)

        count_query = select(func.count()).select_from(grouped_query.order_by(None).subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        grouped_query = grouped_query.order_by(
            func.max(_business_impact_rank_sql_expr()).desc(),
            func.max(Action.score).desc(),
            func.max(Action.updated_at).desc().nullslast(),
            cast(ActionGroup.id, String).asc(),
        ).limit(limit).offset(offset)
        rows = (await db.execute(grouped_query)).all()
        batch_representatives = await _load_batch_representatives(
            db,
            tenant_uuid,
            [str(row.id) for row in rows],
        )

        paged_items = []
        for row in rows:
            open_count = int(row.open_count or 0)
            in_progress_count = int(row.in_progress_count or 0)
            resolved_count = int(row.resolved_count or 0)
            suppressed_count = int(row.suppressed_count or 0)
            total_actions = int(row.action_count or 0)
            derived_status = "open"
            if normalized_status_filter is not None:
                derived_status = normalized_status_filter
            elif open_count > 0:
                derived_status = "open"
            elif in_progress_count > 0:
                derived_status = "in_progress"
            elif resolved_count > 0 and (resolved_count + suppressed_count) == total_actions:
                derived_status = "resolved"
            elif suppressed_count > 0 and suppressed_count == total_actions:
                derived_status = "suppressed"
            representative = batch_representatives.get(str(row.id))

            paged_items.append(
                ActionListItem(
                    id=str(row.id),
                    action_type=row.action_type,
                    target_id=_build_batch_target_id_from_fields(
                        row.action_type,
                        row.account_id,
                        row.region,
                        derived_status,
                    ),
                    account_id=row.account_id,
                    region=row.region,
                    score=int(row.score or row.priority or 0),
                    score_components=None,
                    score_factors=_score_factors_payload(
                        representative,
                        fallback_score=int(row.score or row.priority or 0),
                        legacy_source="highest member action score in the batch group",
                    ),
                    business_impact=_business_impact_payload(
                        representative,
                        fallback_score=int(row.score or row.priority or 0),
                    ),
                    priority=int(row.priority or row.score or 0),
                    status=derived_status,
                    title=_batch_title(row.action_type, total_actions),
                    control_id=row.control_id,
                    resource_id=None,
                    updated_at=row.updated_at.isoformat() if row.updated_at else None,
                    finding_count=int(row.finding_count or 0),
                    is_batch=True,
                    batch_action_count=total_actions,
                    batch_finding_count=int(row.finding_count or 0),
                )
            )
        logger.info(
            "Listed %d batch action groups for tenant %s (total=%d)",
            len(paged_items),
            tenant_uuid,
            total,
        )
        return ActionsListResponse(items=paged_items, total=total, owner_queue_counters=owner_queue_counters)

    if use_effective_visibility:
        query = (
            select(
                Action,
                finding_count_expr.label("finding_count"),
                effective_open_expr.label("has_effective_open_findings"),
            )
            .outerjoin(finding_counts, Action.id == finding_counts.c.action_id)
            .outerjoin(active_exception_sq, active_exception_sq.c.action_id == Action.id)
            .where(*resource_filters)
        )
    else:
        query = (
            select(
                Action,
                finding_count_expr.label("finding_count"),
            )
            .outerjoin(finding_counts, Action.id == finding_counts.c.action_id)
            .outerjoin(active_exception_sq, active_exception_sq.c.action_id == Action.id)
            .where(*resource_filters)
        )
    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(
        _business_impact_rank_sql_expr().desc(),
        Action.score.desc(),
        Action.updated_at.desc().nullslast(),
        Action.id.asc(),
    ).limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()
    actions = [row[0] for row in rows]
    finding_counts_by_action = {row[0].id: int(row[1] or 0) for row in rows}
    effective_open_by_action: dict[uuid.UUID, bool] = {}
    if use_effective_visibility:
        effective_open_by_action = {row[0].id: bool(row[2]) for row in rows}
    exception_state_by_action = await get_exception_states_for_entities(
        db,
        tenant_id=tenant_uuid,
        entity_type="action",
        entity_ids=[action.id for action in actions],
    )

    items = [
        _action_to_list_item(
            action,
            exception_state=exception_state_by_action.get(action.id),
            finding_count=finding_counts_by_action.get(action.id, 0),
            status_override=(
                "open"
                if use_effective_visibility
                and action.status == "resolved"
                and effective_open_by_action.get(action.id, False)
                else None
            ),
            now=now,
        )
        for action in actions
    ]
    logger.info("Listed %d actions for tenant %s (total=%d)", len(items), tenant_uuid, total)
    return ActionsListResponse(items=items, total=total, owner_queue_counters=owner_queue_counters)


@router.get("/attack-paths", response_model=AttackPathsListResponse)
async def list_attack_paths(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    account_id: Annotated[str | None, Query(description="Filter by AWS account ID")] = None,
    action_id: Annotated[str | None, Query(description="Filter by one action UUID")] = None,
    owner_key: Annotated[str | None, Query(description="Filter by normalized owner key.")] = None,
    resource_id: Annotated[str | None, Query(description="Filter by resource ID")] = None,
    status_filter: Annotated[
        Literal["available", "partial", "unavailable", "context_incomplete"] | None,
        Query(alias="status", description="Filter by attack-path status."),
    ] = None,
    view: Annotated[str | None, Query(description="Optional bounded Attack Paths preset view.")] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Max items per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
) -> AttackPathsListResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)
    selected_view = _normalize_attack_path_view(view)
    has_any_materialized = False
    try:
        items, total, stale_seen = await list_materialized_attack_paths(
            db,
            tenant_id=tenant_uuid,
            account_id=account_id,
            action_id=action_id,
            owner_key=owner_key,
            resource_id=resource_id,
            status_filter=status_filter,
            view=selected_view,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid action_id", "detail": str(exc)},
        ) from exc
    try:
        has_any_materialized = bool(items or total) or await has_materialized_attack_paths(db, tenant_id=tenant_uuid)
    except Exception:
        logger.warning("Attack-path materialized presence check failed; considering fallback.", exc_info=True)
        has_any_materialized = bool(items or total)
    if not has_any_materialized:
        try:
            await materialize_attack_paths(db, tenant_id=tenant_uuid)
            await db.commit()
            items, total, stale_seen = await list_materialized_attack_paths(
                db,
                tenant_id=tenant_uuid,
                account_id=account_id,
                action_id=action_id,
                owner_key=owner_key,
                resource_id=resource_id,
                status_filter=status_filter,
                view=selected_view,
                limit=limit,
                offset=offset,
            )
            has_any_materialized = bool(items or total)
        except Exception:
            logger.warning("Attack-path materialized bootstrap failed; using bounded legacy fallback.", exc_info=True)
            items, total = await _list_attack_paths_legacy(
                db,
                tenant_uuid=tenant_uuid,
                account_id=account_id,
                action_id=action_id,
                owner_key=owner_key,
                resource_id=resource_id,
                status_filter=status_filter,
                view=selected_view,
                limit=limit,
                offset=offset,
            )
            stale_seen = False
    if stale_seen:
        maybe_schedule_attack_path_refresh(tenant_id=tenant_uuid)
    return AttackPathsListResponse(
        items=items,
        total=total,
        selected_view=selected_view,
        available_views=_attack_path_view_options(),
    )


def _normalize_attack_path_view(view: str | None) -> str | None:
    if view is None:
        return None
    value = view.strip()
    if not value:
        return None
    valid = {item.key for item in _attack_path_view_options()}
    return value if value in valid else None


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _attack_path_view_options() -> list[AttackPathViewOption]:
    return [
        AttackPathViewOption(
            key="highest_blast_radius",
            label="Highest blast radius",
            description="Shared paths with broader linked-action and asset spread.",
        ),
        AttackPathViewOption(
            key="business_critical",
            label="Business critical",
            description="Shared paths tied to high or critical business impact.",
        ),
        AttackPathViewOption(
            key="actively_exploited",
            label="Actively exploited",
            description="Shared paths where exploitability pressure is prominent.",
        ),
        AttackPathViewOption(
            key="owned_by_my_team",
            label="Owned by my team",
            description="Best used with an owner filter to stay on your team backlog.",
        ),
    ]


def _apply_attack_path_view_filter(records: list[dict[str, Any]], view: str | None) -> list[dict[str, Any]]:
    if view is None:
        return records
    handlers = {
        "highest_blast_radius": _record_matches_blast_radius_view,
        "business_critical": _record_matches_business_critical_view,
        "actively_exploited": _record_matches_actively_exploited_view,
        "owned_by_my_team": _record_matches_owned_by_team_view,
    }
    matcher = handlers.get(view)
    if matcher is None:
        return records
    return [record for record in records if matcher(record)]


async def _list_attack_paths_legacy(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    account_id: str | None,
    action_id: str | None,
    owner_key: str | None,
    resource_id: str | None,
    status_filter: str | None,
    view: str | None,
    limit: int,
    offset: int,
) -> tuple[list[AttackPathSummaryItem], int]:
    now = datetime.now(timezone.utc)
    action_scan_limit = _attack_path_action_scan_limit(
        action_id=action_id,
        account_id=account_id,
        owner_key=owner_key,
        resource_id=resource_id,
        limit=limit,
        offset=offset,
    )
    actions = await _load_attack_path_actions(
        db,
        tenant_uuid=tenant_uuid,
        account_id=account_id,
        action_id=action_id,
        owner_key=owner_key,
        resource_id=resource_id,
        max_actions=action_scan_limit,
    )
    accounts = await _load_attack_path_accounts(db, tenant_uuid=tenant_uuid, actions=actions)
    records = await _load_shared_attack_path_records(
        db,
        tenant_uuid=tenant_uuid,
        actions=actions,
        status_filter=status_filter,
    )
    records = _apply_attack_path_view_filter(records, view)
    records = await _enrich_attack_path_records(db, tenant_uuid=tenant_uuid, records=records, now=now)
    grouped = await _build_attack_path_summary_items(
        db,
        tenant_uuid=tenant_uuid,
        records=records,
        accounts=accounts,
    )
    total = len(grouped)
    return grouped[offset : offset + limit], total


async def _get_attack_path_legacy(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    path_id: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    actions = await _load_attack_path_actions(
        db,
        tenant_uuid=tenant_uuid,
        account_id=None,
        action_id=None,
        owner_key=None,
        resource_id=None,
    )
    records = await _load_shared_attack_path_records(
        db,
        tenant_uuid=tenant_uuid,
        actions=actions,
        status_filter=None,
    )
    records = await _enrich_attack_path_records(db, tenant_uuid=tenant_uuid, records=records, now=now)
    record = next((item for item in records if item["id"] == path_id), None)
    if record is None:
        return None
    accounts = await _load_attack_path_accounts(db, tenant_uuid=tenant_uuid, actions=actions)
    representative_action = record["representative_action"]
    view = _attack_path_view_for_action(
        representative_action,
        graph_context=record["representative_graph_context"],
        account=accounts.get(representative_action.account_id),
    )
    detail = build_attack_path_detail_record(
        record,
        path_nodes=[node.model_dump() for node in view.path_nodes],
        path_edges=[edge.model_dump() for edge in view.path_edges],
        entry_points=[node.model_dump() for node in view.entry_points],
        target_assets=[node.model_dump() for node in view.target_assets],
    )
    detail["runtime_signals"] = record.get("runtime_signals")
    detail["exposure_validation"] = record.get("exposure_validation")
    detail["code_context"] = record.get("code_context")
    detail["linked_repositories"] = record.get("linked_repositories") or []
    detail["implementation_artifacts"] = record.get("implementation_artifacts") or []
    detail["closure_targets"] = record.get("closure_targets")
    detail["external_workflow_summary"] = record.get("external_workflow_summary")
    detail["exception_summary"] = record.get("exception_summary")
    detail["evidence_exports"] = record.get("evidence_exports")
    detail["access_scope"] = record.get("access_scope")
    return detail


def _record_matches_blast_radius_view(record: dict[str, Any]) -> bool:
    return any(
        item.get("name") == "blast_radius" and float(item.get("weighted_impact") or 0) > 0
        for item in record.get("rank_factors") or []
    )


def _record_matches_business_critical_view(record: dict[str, Any]) -> bool:
    tier = _text((record.get("business_impact") or {}).get("criticality_tier"))
    return tier in {"critical", "high"}


def _record_matches_actively_exploited_view(record: dict[str, Any]) -> bool:
    if any("exploit" in str(reason).lower() for reason in record.get("risk_reasons") or []):
        return True
    return any(
        item.get("name") == "exploitability" and float(item.get("weighted_impact") or 0) >= 0.1
        for item in record.get("rank_factors") or []
    )


def _record_matches_owned_by_team_view(record: dict[str, Any]) -> bool:
    return bool(record.get("owners"))


async def _load_attack_path_actions(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    account_id: str | None,
    action_id: str | None,
    owner_key: str | None,
    resource_id: str | None,
    max_actions: int | None = None,
) -> list[Action]:
    query = (
        select(Action)
        .where(Action.tenant_id == tenant_uuid)
        .options(
            selectinload(Action.action_finding_links)
            .selectinload(ActionFinding.finding)
            .load_only(
                Finding.id,
                Finding.finding_id,
                Finding.severity_label,
                Finding.title,
                Finding.resource_id,
                Finding.resource_type,
                Finding.resource_key,
                Finding.account_id,
                Finding.region,
                Finding.updated_at,
                Finding.raw_json,
            ),
        )
    )
    if account_id is not None:
        query = query.where(Action.account_id == account_id)
    if resource_id is not None:
        query = query.where(Action.resource_id == resource_id.strip())
    if owner_key is not None:
        query = query.where(Action.owner_key == owner_key.strip())
    if action_id is not None:
        try:
            query = query.where(Action.id == uuid.UUID(action_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid action_id", "detail": "action_id must be a valid UUID"},
            ) from exc
    ordered_query = query.order_by(Action.priority.desc(), Action.updated_at.desc().nullslast(), Action.id.asc())
    if max_actions is not None:
        ordered_query = ordered_query.limit(max_actions)
    result = await db.execute(ordered_query)
    return list(result.scalars().all())


def _attack_path_action_scan_limit(
    *,
    action_id: str | None,
    account_id: str | None,
    owner_key: str | None,
    resource_id: str | None,
    limit: int,
    offset: int,
) -> int | None:
    if action_id is not None:
        return 1
    if account_id is not None or owner_key is not None or resource_id is not None:
        return min(max(offset + limit, limit), _ATTACK_PATH_ACTION_SCAN_HARD_CAP)
    return min(max(offset + limit, 10), _ATTACK_PATH_ACTION_SCAN_HARD_CAP)


async def _load_attack_path_accounts(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    actions: list[Action],
) -> dict[str, AwsAccount]:
    account_ids = sorted({action.account_id for action in actions if action.account_id})
    if not account_ids:
        return {}
    result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_uuid,
            AwsAccount.account_id.in_(account_ids),
        )
    )
    return {account.account_id: account for account in result.scalars().all()}


async def _load_shared_attack_path_records(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    actions: list[Action],
    status_filter: str | None,
) -> list[dict[str, Any]]:
    records = await build_shared_attack_path_records(db, tenant_id=tenant_uuid, actions=actions)
    if status_filter is not None:
        records = [record for record in records if record["status"] == status_filter]
    return records


def _attack_path_action_ids(records: list[dict[str, Any]]) -> list[uuid.UUID]:
    action_ids: list[uuid.UUID] = []
    for record in records:
        for raw_id in record.get("linked_action_ids") or []:
            try:
                action_ids.append(uuid.UUID(str(raw_id)))
            except (TypeError, ValueError):
                continue
    return sorted(set(action_ids), key=str)


async def _load_attack_path_exceptions(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    action_ids: list[uuid.UUID],
    now: datetime,
) -> dict[uuid.UUID, list[Exception]]:
    if not action_ids:
        return {}
    result = await db.execute(
        select(Exception).where(
            Exception.tenant_id == tenant_uuid,
            Exception.entity_type == EntityType.action,
            Exception.entity_id.in_(action_ids),
            Exception.expires_at > now,
        )
    )
    grouped: defaultdict[uuid.UUID, list[Exception]] = defaultdict(list)
    for row in result.scalars().all():
        grouped[row.entity_id].append(row)
    return dict(grouped)


async def _load_attack_path_runs(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    action_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[RemediationRun]]:
    if not action_ids:
        return {}
    result = await db.execute(
        select(RemediationRun)
        .where(RemediationRun.tenant_id == tenant_uuid, RemediationRun.action_id.in_(action_ids))
        .order_by(RemediationRun.created_at.desc())
    )
    grouped: defaultdict[uuid.UUID, list[RemediationRun]] = defaultdict(list)
    for run in result.scalars().all():
        grouped[run.action_id].append(run)
    return dict(grouped)


async def _load_attack_path_sync_state(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    action_ids: list[uuid.UUID],
) -> tuple[dict[uuid.UUID, list[ActionRemediationSyncState]], dict[uuid.UUID, list[ActionExternalLink]]]:
    if not action_ids:
        return {}, {}
    sync_result = await db.execute(
        select(ActionRemediationSyncState).where(
            ActionRemediationSyncState.tenant_id == tenant_uuid,
            ActionRemediationSyncState.action_id.in_(action_ids),
        )
    )
    link_result = await db.execute(
        select(ActionExternalLink).where(
            ActionExternalLink.tenant_id == tenant_uuid,
            ActionExternalLink.action_id.in_(action_ids),
        )
    )
    states: defaultdict[uuid.UUID, list[ActionRemediationSyncState]] = defaultdict(list)
    for row in sync_result.scalars().all():
        states[row.action_id].append(row)
    links: defaultdict[uuid.UUID, list[ActionExternalLink]] = defaultdict(list)
    for row in link_result.scalars().all():
        links[row.action_id].append(row)
    return dict(states), dict(links)


def _artifact_links_for_runs(runs: list[RemediationRun], *, action_status: str) -> list[ActionImplementationArtifactLink]:
    try:
        return build_action_implementation_artifacts(runs[:8], action_status=action_status)
    except Exception:
        logger.warning("Attack-path artifact projection failed; dropping additive remediation artifacts.", exc_info=True)
        return []


def _repositories_from_artifacts(artifacts: list[ActionImplementationArtifactLink]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str | None, str | None, str | None]] = set()
    items: list[dict[str, Any]] = []
    for artifact in artifacts:
        metadata = artifact.metadata if isinstance(artifact.metadata, dict) else {}
        repository = metadata.get("repository")
        provider = metadata.get("provider") or "generic_git"
        if not isinstance(repository, str) or not repository.strip():
            continue
        item = (
            str(provider),
            repository.strip(),
            _text(metadata.get("base_branch")),
            _text(metadata.get("root_path")),
            artifact.run_id,
        )
        if item in seen:
            continue
        seen.add(item)
        items.append(
            {
                "provider": item[0],
                "repository": item[1],
                "base_branch": item[2],
                "root_path": item[3],
                "source_run_id": item[4],
            }
        )
    return items


def _runtime_signals_payload(
    record: dict[str, Any],
    *,
    representative_action: Action,
) -> dict[str, Any]:
    graph_context = record.get("representative_graph_context") or {}
    entry_points = graph_context.get("entry_points") or []
    connected_assets = graph_context.get("connected_assets") or []
    identity_path = graph_context.get("identity_path") or []
    status = _text(record.get("status")) or "unavailable"
    confidence = float(record.get("confidence") or 0.0)
    publicly_reachable = bool(entry_points)
    sensitive_targets = sum(
        1
        for asset in connected_assets
        if "sensitive" in str(asset.get("label", "")).lower() or "data" in str(asset.get("relationship", "")).lower()
    )
    workload_presence = "present" if connected_assets else "unknown"
    summary = (
        f"{len(entry_points)} entry point(s), {len(identity_path)} identity hop(s), and {len(connected_assets)} connected asset(s) inform this path."
        if status in {"available", "partial"}
        else "Runtime truth is not fully verified for this path yet."
    )
    return {
        "workload_presence": workload_presence,
        "publicly_reachable": publicly_reachable,
        "sensitive_target_count": sensitive_targets,
        "identity_hops": len(identity_path),
        "confidence": confidence,
        "summary": summary,
    }


def _exposure_validation_payload(record: dict[str, Any]) -> dict[str, Any]:
    status = _text(record.get("status")) or "unavailable"
    freshness = record.get("freshness") or {}
    if status == "available":
        validation = "verified"
        summary = "Persisted graph evidence resolves a bounded entry point and target path."
    elif status == "partial":
        validation = "partial"
        summary = "The path is supported by graph evidence, but some runtime or graph detail is truncated."
    else:
        validation = "unverified"
        summary = "The path remains bounded and fail-closed because runtime or graph evidence is incomplete."
    return {
        "status": validation,
        "summary": summary,
        "observed_at": freshness.get("observed_at"),
    }


def _closure_targets_payload(record: dict[str, Any]) -> dict[str, Any]:
    linked_actions = record.get("linked_actions") or []
    open_ids = [item["id"] for item in linked_actions if item.get("status") == "open"]
    in_progress_ids = [item["id"] for item in linked_actions if item.get("status") == "in_progress"]
    resolved_ids = [item["id"] for item in linked_actions if item.get("status") == "resolved"]
    if in_progress_ids:
        summary = f"{len(in_progress_ids)} linked action(s) are in progress; closing the remaining open items will reduce this path."
    elif open_ids:
        summary = f"{len(open_ids)} open linked action(s) remain before this path can materially drop."
    else:
        summary = "All currently linked actions are resolved; monitor for drift or reopen."
    return {
        "open_action_ids": open_ids,
        "in_progress_action_ids": in_progress_ids,
        "resolved_action_ids": resolved_ids,
        "summary": summary,
    }


def _external_workflow_summary_payload(
    *,
    action_ids: list[uuid.UUID],
    sync_states_by_action: dict[uuid.UUID, list[ActionRemediationSyncState]],
    links_by_action: dict[uuid.UUID, list[ActionExternalLink]],
) -> dict[str, Any]:
    drifted_count = 0
    in_sync_count = 0
    linked_items: list[str] = []
    providers: set[str] = set()
    for action_id in action_ids:
        for state in sync_states_by_action.get(action_id, []):
            providers.add(state.provider)
            if state.sync_status == "drifted":
                drifted_count += 1
            else:
                in_sync_count += 1
        for link in links_by_action.get(action_id, []):
            providers.add(link.provider)
            ref = link.external_key or link.external_id or link.provider
            linked_items.append(f"{link.provider}:{ref}")
    if not providers:
        summary = "No external workflow links are attached to this path."
    elif drifted_count:
        summary = f"{drifted_count} linked external workflow item(s) are drifted across {len(providers)} provider(s)."
    else:
        summary = f"External workflow links are present across {len(providers)} provider(s) and currently aligned."
    return {
        "provider_count": len(providers),
        "drifted_count": drifted_count,
        "in_sync_count": in_sync_count,
        "linked_items": sorted(linked_items),
        "summary": summary,
    }


def _exception_summary_payload(
    *,
    action_ids: list[uuid.UUID],
    exceptions_by_action: dict[uuid.UUID, list[Exception]],
    now: datetime,
) -> dict[str, Any]:
    active_count = 0
    expiring_count = 0
    for action_id in action_ids:
        for row in exceptions_by_action.get(action_id, []):
            active_count += 1
            if row.expires_at <= now + timedelta(days=settings.ACTIONS_OWNER_QUEUE_EXPIRING_EXCEPTION_DAYS):
                expiring_count += 1
    if not active_count:
        summary = "No active action exceptions are attached to this path."
    elif expiring_count:
        summary = f"{expiring_count} active exception(s) are nearing expiry across linked actions."
    else:
        summary = f"{active_count} active exception(s) currently govern linked actions on this path."
    return {
        "active_count": active_count,
        "expiring_count": expiring_count,
        "summary": summary,
    }


def _evidence_exports_payload(
    record: dict[str, Any],
    *,
    artifacts: list[ActionImplementationArtifactLink],
    runs: list[RemediationRun],
    action_status: str,
) -> dict[str, Any]:
    evidence_count = len(record.get("evidence") or [])
    artifact_count = len(artifacts)
    export_ready = bool(evidence_count or artifact_count or runs)
    if export_ready:
        summary = f"{evidence_count} evidence item(s) and {artifact_count} implementation artifact(s) are available for closure review."
    else:
        summary = "No exportable implementation or evidence artifacts are attached yet."
    return {
        "evidence_item_count": evidence_count,
        "implementation_artifact_count": artifact_count,
        "export_ready": export_ready,
        "summary": summary,
    }


def _access_scope_payload() -> dict[str, Any]:
    return {
        "scope": "tenant_scoped",
        "evidence_visibility": "full",
        "restricted_sections": [],
        "export_allowed": True,
    }


def _code_context_payload(
    representative_action: Action,
    *,
    repositories: list[dict[str, Any]],
    artifacts: list[ActionImplementationArtifactLink],
) -> dict[str, Any]:
    owner_label = representative_action.owner_label or "Unassigned"
    repository_count = len(repositories)
    artifact_count = len(artifacts)
    if repositories:
        repo_summary = f"{repository_count} linked repo target(s) and {artifact_count} implementation artifact(s) are available."
    else:
        repo_summary = f"{artifact_count} implementation artifact(s) are available, but no repo-aware target is attached yet."
    return {
        "owner_label": owner_label,
        "service_owner_key": representative_action.owner_key,
        "repository_count": repository_count,
        "implementation_artifact_count": artifact_count,
        "summary": repo_summary,
    }


async def _enrich_attack_path_records(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    records: list[dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:
    action_ids = _attack_path_action_ids(records)
    try:
        exceptions_by_action = await _load_attack_path_exceptions(
            db,
            tenant_uuid=tenant_uuid,
            action_ids=action_ids,
            now=now,
        )
    except SQLAlchemyError:
        logger.warning("Attack-path exception enrichment failed; continuing without exception summaries.", exc_info=True)
        exceptions_by_action = {}
    try:
        runs_by_action = await _load_attack_path_runs(db, tenant_uuid=tenant_uuid, action_ids=action_ids)
    except SQLAlchemyError:
        logger.warning("Attack-path remediation-run enrichment failed; continuing without remediation artifacts.", exc_info=True)
        runs_by_action = {}
    try:
        sync_states_by_action, links_by_action = await _load_attack_path_sync_state(
            db,
            tenant_uuid=tenant_uuid,
            action_ids=action_ids,
        )
    except SQLAlchemyError:
        logger.warning("Attack-path external workflow enrichment failed; continuing without sync projections.", exc_info=True)
        sync_states_by_action, links_by_action = {}, {}
    enriched: list[dict[str, Any]] = []
    for record in records:
        linked_action_rows = record.get("linked_actions") or []
        linked_action_ids: list[uuid.UUID] = []
        for row in linked_action_rows:
            try:
                linked_action_ids.append(uuid.UUID(str(row.get("id"))))
            except (TypeError, ValueError):
                continue
        representative_action = record["representative_action"]
        path_runs = [run for action_id in linked_action_ids for run in runs_by_action.get(action_id, [])]
        artifacts = _artifact_links_for_runs(path_runs, action_status=representative_action.status)
        repositories = _repositories_from_artifacts(artifacts)
        enriched_record = dict(record)
        enriched_record["runtime_signals"] = _runtime_signals_payload(record, representative_action=representative_action)
        enriched_record["exposure_validation"] = _exposure_validation_payload(record)
        enriched_record["linked_repositories"] = repositories
        enriched_record["implementation_artifacts"] = [artifact.model_dump() for artifact in artifacts]
        enriched_record["code_context"] = _code_context_payload(
            representative_action,
            repositories=repositories,
            artifacts=artifacts,
        )
        enriched_record["closure_targets"] = _closure_targets_payload(record)
        workflow = _external_workflow_summary_payload(
            action_ids=linked_action_ids,
            sync_states_by_action=sync_states_by_action,
            links_by_action=links_by_action,
        )
        enriched_record["external_workflow_summary"] = workflow
        enriched_record["governance_summary"] = workflow
        enriched_record["exception_summary"] = _exception_summary_payload(
            action_ids=linked_action_ids,
            exceptions_by_action=exceptions_by_action,
            now=now,
        )
        enriched_record["evidence_exports"] = _evidence_exports_payload(
            record,
            artifacts=artifacts,
            runs=path_runs,
            action_status=representative_action.status,
        )
        enriched_record["access_scope"] = _access_scope_payload()
        enriched.append(enriched_record)
    return enriched


async def _build_attack_path_summary_items(
    db: AsyncSession,
    *,
    tenant_uuid: uuid.UUID,
    records: list[dict[str, Any]],
    accounts: dict[str, AwsAccount],
) -> list[AttackPathSummaryItem]:
    items: list[AttackPathSummaryItem] = []
    for record in records:
        representative_action = record["representative_action"]
        account = accounts.get(representative_action.account_id)
        view = _attack_path_view_for_action(
            representative_action,
            graph_context=record["representative_graph_context"],
            account=account,
        )
        items.append(
            AttackPathSummaryItem(
                id=record["id"],
                status=record["status"],
                rank=int(record["rank"]),
                confidence=float(record["confidence"]),
                entry_points=view.entry_points,
                target_assets=view.target_assets,
                summary=view.summary,
                business_impact_summary=record.get("business_impact_summary"),
                recommended_fix_summary=(record.get("recommended_fix") or {}).get("summary"),
                owner_labels=list(record.get("owner_labels") or []),
                linked_action_ids=list(record.get("linked_action_ids") or []),
                rank_factors=record.get("rank_factors") or [],
                freshness=record.get("freshness"),
                remediation_summary=record.get("remediation_summary"),
                runtime_signals=record.get("runtime_signals"),
                closure_targets=record.get("closure_targets"),
                governance_summary=record.get("governance_summary"),
                access_scope=record.get("access_scope"),
            )
        )
    return items


def _attack_path_view_for_action(
    action: Action,
    *,
    graph_context: dict[str, Any],
    account: AwsAccount | None,
) -> ActionAttackPathView:
    recommendation = _action_recommendation_payload(
        action,
        mode_options=_mode_options_for_action(action.action_type),
        manual_high_risk=is_root_credentials_required_action(action.action_type),
    )
    execution_guidance = [
        ActionExecutionGuidance(**payload)
        for payload in build_action_execution_guidance(action, account=account)
    ]
    return _attack_path_view_payload(
        action,
        graph_context=graph_context,
        business_impact=_business_impact_payload(action),
        recommendation=recommendation,
        score_factors=_score_factors_payload(action),
        execution_guidance=execution_guidance,
        sla=_action_sla_payload(action, exception_state=None, now=datetime.now(timezone.utc)),
    )


@router.get("/attack-paths/{path_id}", response_model=AttackPathDetailResponse)
async def get_attack_path(
    path_id: Annotated[str, Path(description="Shared attack path ID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> AttackPathDetailResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)
    used_legacy_fallback = False
    detail, is_stale = await get_materialized_attack_path(db, tenant_id=tenant_uuid, path_id=path_id)
    has_any_materialized = False
    if detail is None:
        try:
            has_any_materialized = await has_materialized_attack_paths(db, tenant_id=tenant_uuid)
        except Exception:
            logger.warning("Attack-path materialized presence check failed on detail read.", exc_info=True)
            has_any_materialized = False
    if detail is None and not has_any_materialized:
        try:
            await materialize_attack_paths(db, tenant_id=tenant_uuid)
            await db.commit()
            detail, is_stale = await get_materialized_attack_path(db, tenant_id=tenant_uuid, path_id=path_id)
        except Exception:
            logger.warning("Attack-path materialized bootstrap failed on detail read; using legacy fallback.", exc_info=True)
            detail = await _get_attack_path_legacy(db, tenant_uuid=tenant_uuid, path_id=path_id)
            is_stale = False
    if detail is None:
        try:
            detail = await _get_attack_path_legacy(db, tenant_uuid=tenant_uuid, path_id=path_id)
            is_stale = False
            used_legacy_fallback = detail is not None
        except Exception:
            logger.warning("Attack-path legacy fallback failed on detail read.", exc_info=True)
            detail = None
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Attack path not found", "detail": f"No attack path found with ID {path_id}"},
        )
    if is_stale or used_legacy_fallback:
        maybe_schedule_attack_path_refresh(tenant_id=tenant_uuid)
    return AttackPathDetailResponse(**detail)


@router.get("/{action_id}", response_model=ActionDetailResponse)
async def get_action(
    action_id: Annotated[str, Path(description="Action UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> ActionDetailResponse:
    """
    Get a single action by ID with linked findings.
    Tenant-scoped; 404 if not found.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    try:
        action_uuid = uuid.UUID(action_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid action_id", "detail": "action_id must be a valid UUID"},
        )

    result = await db.execute(
        select(Action)
        .where(Action.id == action_uuid, Action.tenant_id == tenant_uuid)
        .options(
            selectinload(Action.action_finding_links)
            .selectinload(ActionFinding.finding)
            .load_only(
                Finding.id,
                Finding.finding_id,
                Finding.severity_label,
                Finding.title,
                Finding.resource_id,
                Finding.resource_type,
                Finding.resource_key,
                Finding.account_id,
                Finding.region,
                Finding.updated_at,
                Finding.raw_json,
            ),
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Action not found", "detail": f"No action found with ID {action_id}"},
        )

    exception_state = await get_exception_state_for_response(
        db, tenant_uuid, "action", action.id
    )
    implementation_artifacts = await _load_action_implementation_artifacts(
        db,
        tenant_uuid=tenant_uuid,
        action=action,
    )
    graph_context = await _load_action_graph_context(
        db,
        tenant_uuid=tenant_uuid,
        action=action,
    )
    attack_path_graph_context = await _load_action_attack_path_graph_context(
        db,
        tenant_uuid=tenant_uuid,
        action=action,
    )
    account_result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_uuid,
            AwsAccount.account_id == action.account_id,
        )
    )
    account = account_result.scalar_one_or_none()
    recommendation = _action_recommendation_payload(
        action,
        mode_options=_mode_options_for_action(action.action_type),
        manual_high_risk=is_root_credentials_required_action(action.action_type),
    )
    return _action_to_detail_response(
        action,
        exception_state,
        now=datetime.now(timezone.utc),
        account=account,
        recommendation=recommendation,
        implementation_artifacts=implementation_artifacts,
        graph_context=graph_context,
        attack_path_graph_context=attack_path_graph_context,
    )


# ---------------------------------------------------------------------------
# GET /actions/{id}/remediation-options
# ---------------------------------------------------------------------------

@router.get(
    "/{action_id}/remediation-options",
    response_model=RemediationOptionsResponse,
    summary="List remediation options",
    description=(
        "Return available remediation strategies for an action, including dependency checks, "
        "warnings, and whether risk acknowledgement is expected."
    ),
)
async def get_remediation_options(
    action_id: Annotated[str, Path(description="Action UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
) -> RemediationOptionsResponse:
    """List strategy options and risk checks for one action."""
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant(tenant_uuid, db)

    try:
        action_uuid = uuid.UUID(action_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid action_id", "detail": "action_id must be a valid UUID"},
        )

    action_result = await db.execute(
        select(Action).where(Action.id == action_uuid, Action.tenant_id == tenant_uuid)
    )
    action = action_result.scalar_one_or_none()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Action not found", "detail": f"No action found with ID {action_id}"},
        )

    account: AwsAccount | None = None
    account_result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_uuid,
            AwsAccount.account_id == action.account_id,
        )
    )
    account = account_result.scalar_one_or_none()
    tenant_settings = getattr(tenant, "remediation_settings", None)

    strategies = list_strategies_for_action_type(action.action_type)
    root_required = is_root_credentials_required_action(action.action_type)
    pre_execution_notice = ROOT_CREDENTIALS_REQUIRED_MESSAGE if root_required else None
    runbook_url = ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH if root_required else None
    mode_options = _mode_options_for_action(action.action_type)
    recommendation = _action_recommendation_payload(
        action,
        mode_options=mode_options,
        manual_high_risk=root_required,
    )
    if not strategies:
        return RemediationOptionsResponse(
            action_id=str(action.id),
            action_type=action.action_type,
            mode_options=mode_options,
            strategies=[],
            recommendation=recommendation,
            manual_high_risk=root_required,
            pre_execution_notice=pre_execution_notice,
            runbook_url=runbook_url,
        )

    option_items: list[RemediationOptionResponse] = []
    for strategy in strategies:
        # Defensive validation: ensures registry entries stay internally consistent.
        validate_strategy(action.action_type, strategy["strategy_id"], strategy["mode"])
        runtime_signals: dict[str, Any] = {}
        risk_inputs: dict[str, Any] = {}
        if (
            strategy["strategy_id"] in _RUNTIME_RISK_OPTION_STRATEGIES
            or strategy["strategy_id"] in _RUNTIME_CONTEXT_OPTION_STRATEGIES
        ):
            probe_inputs = resolve_runtime_probe_inputs(
                action_type=action.action_type,
                strategy=strategy,
                requested_profile_id=None,
                explicit_inputs=None,
                tenant_settings=tenant_settings,
                action=action,
            )
            risk_inputs = probe_inputs
            runtime_signals = collect_runtime_risk_signals(
                action=action,
                strategy=strategy,
                strategy_inputs=probe_inputs,
                account=account,
            )
        runtime_context = runtime_signals.get("context")
        if not isinstance(runtime_context, dict):
            runtime_context = {}
        risk_snapshot = evaluate_strategy_impact(
            action,
            strategy,
            risk_inputs,
            account=account,
            runtime_signals=runtime_signals,
        )
        checks: list[DependencyCheckResponse] = [
            DependencyCheckResponse(
                code=check["code"],
                status=check["status"],
                message=check["message"],
            )
            for check in risk_snapshot["checks"]
        ]
        option_items.append(
            RemediationOptionResponse(
                strategy_id=strategy["strategy_id"],
                label=strategy["label"],
                mode=strategy["mode"],
                risk_level=strategy["risk_level"],
                recommended=_option_recommended(strategy, tenant_settings),
                requires_inputs=strategy["requires_inputs"],
                input_schema=strategy["input_schema"],
                dependency_checks=checks,
                warnings=risk_snapshot["warnings"],
                supports_exception_flow=strategy["supports_exception_flow"],
                exception_only=strategy["exception_only"],
                impact_text=strategy.get("impact_text"),
                rollback_command=get_rollback_command(action.action_type, strategy["strategy_id"]),
                estimated_resolution_time=get_estimated_resolution_time(
                    action.action_type,
                    strategy["strategy_id"],
                ),
                supports_immediate_reeval=supports_immediate_reeval(
                    action.action_type,
                    strategy["strategy_id"],
                ),
                blast_radius=get_blast_radius(
                    action.action_type,
                    strategy["strategy_id"],
                ),
                context=runtime_context,
                **build_strategy_profile_metadata(
                    action_type=action.action_type,
                    strategy=strategy,
                    tenant_settings=tenant_settings,
                    runtime_signals=runtime_signals,
                    dependency_checks=risk_snapshot["checks"],
                    action=action,
                ),
            )
        )

    return RemediationOptionsResponse(
        action_id=str(action.id),
        action_type=action.action_type,
        mode_options=mode_options,
        strategies=option_items,
        recommendation=recommendation,
        manual_high_risk=root_required,
        pre_execution_notice=pre_execution_notice,
        runbook_url=runbook_url,
    )


# ---------------------------------------------------------------------------
# POST /actions/{id}/trigger-reeval
# ---------------------------------------------------------------------------

@router.post(
    "/{action_id}/trigger-reeval",
    response_model=TriggerReevalResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger immediate re-evaluation",
    description=(
        "Enqueue targeted inventory reconciliation shard jobs for this action so "
        "security posture/status can be re-evaluated after remediation apply."
    ),
    responses={
        400: {"description": "Invalid action/strategy selection or unsupported control"},
        404: {"description": "Action or account not found"},
        503: {"description": "Queue unavailable or SQS send failed"},
    },
)
async def trigger_action_reevaluation(
    action_id: Annotated[str, Path(description="Action UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    body: TriggerReevalRequest = Body(default_factory=TriggerReevalRequest),
) -> TriggerReevalResponse:
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    try:
        action_uuid = uuid.UUID(action_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid action_id", "detail": "action_id must be a valid UUID"},
        )

    action_result = await db.execute(
        select(Action).where(Action.id == action_uuid, Action.tenant_id == tenant_uuid)
    )
    action = action_result.scalar_one_or_none()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Action not found", "detail": f"No action found with ID {action_id}"},
        )

    strategy_id = (body.strategy_id or "").strip() or None
    if strategy_id and get_strategy(action.action_type, strategy_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid strategy_id",
                "detail": f"strategy_id '{strategy_id}' is not valid for action_type '{action.action_type}'.",
            },
        )

    estimated_resolution_time = get_estimated_resolution_time(action.action_type, strategy_id)
    supports_reeval = supports_immediate_reeval(action.action_type, strategy_id)
    if not supports_reeval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Immediate re-evaluation not supported",
                "detail": "Immediate re-evaluation is not supported for this remediation strategy.",
            },
        )

    if not settings.has_inventory_reconcile_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Action re-evaluation unavailable",
                "detail": "Queue URL not configured. Set SQS_INVENTORY_RECONCILE_QUEUE_URL.",
            },
        )

    account = await get_account_for_tenant(tenant_uuid, action.account_id, db)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Account not found",
                "detail": "No AWS account found for this action in the current tenant.",
            },
        )

    account_regions = list(account.regions or [])
    action_region = (action.region or "").strip() or None
    if action_region is not None and action_region not in set(account_regions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Action region not configured",
                "detail": "Action region is not in the account's configured regions.",
            },
        )

    target_regions = [action_region] if action_region else (account_regions or [settings.AWS_REGION])
    services = settings.control_plane_inventory_services_list
    max_resources = int(settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD or 500)

    queue_url = settings.SQS_INVENTORY_RECONCILE_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    now = datetime.now(timezone.utc).isoformat()
    enqueued_jobs = 0

    try:
        for region in target_regions:
            for service in services:
                payload = build_reconcile_inventory_shard_job_payload(
                    tenant_id=tenant_uuid,
                    account_id=action.account_id,
                    region=region,
                    service=service,
                    created_at=now,
                    sweep_mode="global",
                    max_resources=max_resources,
                )
                sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
                enqueued_jobs += 1
    except ClientError as e:
        logger.exception("SQS send_message failed for trigger_action_reevaluation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Action re-evaluation unavailable",
                "detail": "Could not enqueue re-evaluation jobs. Please try again later.",
            },
        ) from e

    scope: dict[str, str] = {"account_id": action.account_id}
    if action_region:
        scope["region"] = action_region

    return TriggerReevalResponse(
        message="Immediate re-evaluation jobs queued",
        tenant_id=str(tenant_uuid),
        action_id=str(action.id),
        strategy_id=strategy_id,
        estimated_resolution_time=estimated_resolution_time,
        supports_immediate_reeval=supports_reeval,
        scope=scope,
        enqueued_jobs=enqueued_jobs,
    )


# ---------------------------------------------------------------------------
# GET /actions/{id}/remediation-preview (Step 8.4 dry-run)
# ---------------------------------------------------------------------------

@router.get(
    "/{action_id}/remediation-preview",
    response_model=RemediationPreviewResponse,
    summary="Remediation preview (dry-run)",
    description=(
        "Return an informational preview for the currently supported PR-bundle path. "
        "Deprecated direct-fix requests fail closed."
    ),
    responses={
        400: {"description": "Action not found or direct-fix request rejected"},
        404: {"description": "Action not found"},
    },
)
async def get_remediation_preview(
    action_id: Annotated[str, Path(description="Action UUID")],
    mode: Annotated[
        str,
        Query(
            description=(
                "Remediation mode. The only supported value is `pr_only`. "
                "Deprecated `direct_fix` requests are rejected."
            )
        ),
    ] = "pr_only",
    strategy_id: Annotated[
        str | None,
        Query(description="Optional remediation strategy ID for direct-fix preview."),
    ] = None,
    profile_id: Annotated[
        str | None,
        Query(description="Optional remediation profile ID within the selected strategy family."),
    ] = None,
    strategy_inputs_json: Annotated[
        str | None,
        Query(alias="strategy_inputs", description="Optional JSON object string for strategy inputs."),
    ] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = ...,
    current_user: Annotated[Optional[User], Depends(get_optional_user)] = ...,
    tenant_id: Annotated[Optional[str], Query(description="Tenant ID. Optional when authenticated.")] = None,
) -> RemediationPreviewResponse:
    """
    Informational preview for the supported PR-bundle path.

    Direct-fix requests are intentionally rejected while direct-fix and
    customer WriteRole stay out of scope.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    tenant = await get_tenant(tenant_uuid, db)

    try:
        action_uuid = uuid.UUID(action_id)
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
            detail={"error": "Action not found", "detail": f"No action found with ID {action_id}"},
        )

    parsed_strategy_inputs: dict[str, Any] | None = None
    strategy_inputs_error: str | None = None
    if strategy_inputs_json:
        try:
            raw = json.loads(strategy_inputs_json)
            if isinstance(raw, dict):
                parsed_strategy_inputs = raw
            else:
                raise ValueError("strategy_inputs must be a JSON object")
        except Exception as exc:
            if mode == "pr_only":
                parsed_strategy_inputs = None
            else:
                strategy_inputs_error = str(exc)

    selected_strategy = get_strategy(action.action_type, strategy_id) if strategy_id else None
    tenant_settings = getattr(tenant, "remediation_settings", None)
    if profile_id is not None and selected_strategy is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid profile_id",
                "detail": "profile_id requires a valid strategy_id for this action.",
            },
        )
    needs_state_simulation = (
        selected_strategy is not None and strategy_supports_state_simulation(selected_strategy["strategy_id"])
    )
    needs_runtime_risk = selected_strategy is not None and (
        selected_strategy["strategy_id"] in _RUNTIME_RISK_OPTION_STRATEGIES
        or selected_strategy["strategy_id"] in _RUNTIME_CONTEXT_OPTION_STRATEGIES
    )
    needs_runtime_signals = needs_state_simulation or needs_runtime_risk

    account: AwsAccount | None = None
    if needs_runtime_signals:
        acc_result = await db.execute(
            select(AwsAccount).where(
                AwsAccount.tenant_id == tenant_uuid,
                AwsAccount.account_id == action.account_id,
            )
        )
        account = acc_result.scalar_one_or_none()

    runtime_signals: dict[str, Any] = {}
    if needs_runtime_signals and selected_strategy is not None:
        try:
            probe_inputs = resolve_runtime_probe_inputs(
                action_type=action.action_type,
                strategy=selected_strategy,
                requested_profile_id=profile_id,
                explicit_inputs=parsed_strategy_inputs,
                tenant_settings=tenant_settings,
                action=action,
            )
        except ValueError as exc:
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
    runtime_context = runtime_signals.get("context")
    if not isinstance(runtime_context, dict):
        runtime_context = {}
    preview_strategy_inputs = parsed_strategy_inputs or {}
    if selected_strategy is not None:
        try:
            preview_selection = resolve_profile_selection(
                action_type=action.action_type,
                strategy=selected_strategy,
                requested_profile_id=profile_id,
                explicit_inputs=parsed_strategy_inputs,
                tenant_settings=tenant_settings,
                runtime_signals=runtime_signals,
                action=action,
            )
            preview_strategy_inputs = preview_selection.persisted_strategy_inputs
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid profile_id", "detail": str(exc)},
            ) from exc
    dependency_checks: list[dict[str, Any]] = []
    if selected_strategy is not None:
        dependency_checks = evaluate_strategy_impact(
            action,
            selected_strategy,
            preview_strategy_inputs,
            account=account,
            runtime_signals=runtime_signals,
        )["checks"]

    state_simulation = build_remediation_state_simulation(
        strategy_id=strategy_id,
        strategy_inputs=preview_strategy_inputs,
        runtime_signals=runtime_signals,
    )
    impact_summary = get_impact_summary(strategy_id, preview_strategy_inputs) or None
    try:
        resolution = build_preview_resolution(
            action_type=action.action_type,
            strategy=selected_strategy,
            profile_id=profile_id,
            strategy_inputs=parsed_strategy_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            dependency_checks=dependency_checks,
            action=action,
        )
    except InvalidProfileSelection as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid profile_id", "detail": str(exc)},
        ) from exc

    def _preview_response(
        *,
        compliant: bool,
        message: str,
        will_apply: bool,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        diff_lines: list[dict[str, str]] | None = None,
        resolution_payload: RemediationPreviewResolutionResponse | None = None,
    ) -> RemediationPreviewResponse:
        return RemediationPreviewResponse(
            compliant=compliant,
            message=message,
            will_apply=will_apply,
            impact_summary=impact_summary,
            before_state=before_state if isinstance(before_state, dict) else state_simulation["before_state"],
            after_state=after_state if isinstance(after_state, dict) else state_simulation["after_state"],
            diff_lines=diff_lines if isinstance(diff_lines, list) else state_simulation["diff_lines"],
            resolution=resolution_payload or resolution,
        )

    if strategy_inputs_error:
        return _preview_response(
            compliant=False,
            message=f"Invalid strategy_inputs: {strategy_inputs_error}",
            will_apply=False,
        )

    normalized_mode = mode.strip()

    if normalized_mode == "direct_fix":
        return _preview_response(
            compliant=False,
            message=DIRECT_FIX_OUT_OF_SCOPE_MESSAGE,
            will_apply=False,
        )

    if normalized_mode != "pr_only":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Unsupported remediation mode",
                "detail": "Only `pr_only` is supported for remediation preview.",
            },
        )

    if normalized_mode == "pr_only":
        return _preview_response(
            compliant=False,
            message="Preview for mode 'pr_only' is informational only. Generate a PR bundle to review the change set.",
            will_apply=False,
        )


@router.patch("/{action_id}", response_model=ActionDetailResponse)
async def patch_action(
    action_id: Annotated[str, Path(description="Action UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    body: PatchActionRequest = Body(...),
) -> ActionDetailResponse:
    """
    Update action status (in_progress, resolved, suppressed).
    Returns the updated action with linked findings.
    """
    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    try:
        action_uuid = uuid.UUID(action_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid action_id", "detail": "action_id must be a valid UUID"},
        )

    result = await db.execute(
        select(Action)
        .where(Action.id == action_uuid, Action.tenant_id == tenant_uuid)
        .options(
            selectinload(Action.action_finding_links)
            .selectinload(ActionFinding.finding)
            .load_only(
                Finding.id,
                Finding.finding_id,
                Finding.severity_label,
                Finding.title,
                Finding.resource_id,
                Finding.resource_type,
                Finding.resource_key,
                Finding.account_id,
                Finding.region,
                Finding.updated_at,
                Finding.raw_json,
            ),
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Action not found", "detail": f"No action found with ID {action_id}"},
        )

    await db.run_sync(
        lambda session: _patch_action_status_sync(
            session,
            tenant_id=tenant_uuid,
            action_id=action_uuid,
            target_status=body.status,
            actor_user_id=getattr(current_user, "id", None),
        )
    )
    sync_task_ids = await db.run_sync(
        lambda session: plan_action_sync_tasks(
            session,
            tenant_id=tenant_uuid,
            action_ids=[action_uuid],
            reopened_action_ids={action_uuid} if body.status in {"open", "in_progress"} else set(),
            trigger="api.patch_action",
        )
    )
    await db.commit()
    dispatch_sync_tasks(sync_task_ids, tenant_id=tenant_uuid)

    # Re-query with relationships so response has findings
    result2 = await db.execute(
        select(Action)
        .where(Action.id == action_uuid, Action.tenant_id == tenant_uuid)
        .options(
            selectinload(Action.action_finding_links)
            .selectinload(ActionFinding.finding)
            .load_only(
                Finding.id,
                Finding.finding_id,
                Finding.severity_label,
                Finding.title,
                Finding.resource_id,
                Finding.resource_type,
                Finding.resource_key,
                Finding.account_id,
                Finding.region,
                Finding.updated_at,
                Finding.raw_json,
            ),
        )
    )
    action = result2.scalar_one_or_none()
    exception_state = await get_exception_state_for_response(
        db, tenant_uuid, "action", action.id
    )
    implementation_artifacts = await _load_action_implementation_artifacts(
        db,
        tenant_uuid=tenant_uuid,
        action=action,
    )
    graph_context = await _load_action_graph_context(
        db,
        tenant_uuid=tenant_uuid,
        action=action,
    )
    account_result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_uuid,
            AwsAccount.account_id == action.account_id,
        )
    )
    account = account_result.scalar_one_or_none()
    return _action_to_detail_response(
        action,
        exception_state,
        now=datetime.now(timezone.utc),
        account=account,
        implementation_artifacts=implementation_artifacts,
        graph_context=graph_context,
    )


# ---------------------------------------------------------------------------
# POST /actions/compute (Step 5.4)
# ---------------------------------------------------------------------------

@router.post(
    "/compute",
    response_model=ComputeActionsResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger action computation",
    description="Enqueue a compute_actions job for the current tenant. Omit body for tenant-wide; optionally scope by account_id and/or region.",
    responses={
        404: {"description": "Tenant or account not found"},
        400: {"description": "Invalid scope (e.g. region without account_id, or account/region not in tenant)"},
        503: {"description": "Queue unavailable or SQS send failed"},
    },
)
async def trigger_compute_actions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    body: Optional[ComputeActionsRequest] = Body(default=None),
) -> ComputeActionsResponse:
    """
    Enqueue one compute_actions job. Resolves tenant from JWT or tenant_id query.
    Optional body: account_id and/or region to scope computation.
    """
    if not settings.has_ingest_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Action computation unavailable",
                "detail": "Queue URL not configured. Set SQS_INGEST_QUEUE_URL.",
            },
        )

    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    account_id: Optional[str] = None
    region: Optional[str] = None
    scope: dict = {}

    if body:
        if body.region is not None and body.account_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Bad request",
                    "detail": "region requires account_id. Omit region or provide account_id.",
                },
            )
        account_id = body.account_id
        region = body.region
        if account_id is not None:
            scope["account_id"] = account_id
            acc = await get_account_for_tenant(tenant_uuid, account_id, db)
            if not acc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "Account not found",
                        "detail": "No AWS account found with the given ID for this tenant.",
                    },
                )
            if region is not None:
                scope["region"] = region
                allowed = set(acc.regions or [])
                if region not in allowed:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error": "Bad request",
                            "detail": "region must be one of the account's configured regions.",
                        },
                    )

    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    now = datetime.now(timezone.utc).isoformat()
    payload = build_compute_actions_job_payload(tenant_uuid, now, account_id=account_id, region=region)

    try:
        resp = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
        _ = resp["MessageId"]
    except ClientError as e:
        logger.exception("SQS send_message failed for compute_actions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Action computation unavailable",
                "detail": "Could not enqueue job. Please try again later.",
            },
        ) from e

    return ComputeActionsResponse(
        message="Action computation job queued",
        tenant_id=str(tenant_uuid),
        scope=scope,
    )


# ---------------------------------------------------------------------------
# POST /actions/reconcile
# ---------------------------------------------------------------------------

@router.post(
    "/reconcile",
    response_model=ReconcileActionsResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger action reconciliation",
    description=(
        "Enqueue inventory reconciliation shard jobs for the current tenant and account. "
        "If region is omitted, all configured account regions are enqueued."
    ),
    responses={
        404: {"description": "Tenant or account not found"},
        400: {"description": "Invalid scope (e.g. unknown region for account)"},
        503: {"description": "Queue unavailable or SQS send failed"},
    },
)
async def trigger_action_reconcile(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_user)],
    tenant_id: Annotated[
        Optional[str],
        Query(description="Tenant ID (UUID). Optional when authenticated via Bearer token."),
    ] = None,
    body: ReconcileActionsRequest = Body(...),
) -> ReconcileActionsResponse:
    """Enqueue one reconciliation sweep per (region, service) for an account in the current tenant."""
    if not settings.has_inventory_reconcile_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Action reconciliation unavailable",
                "detail": "Queue URL not configured. Set SQS_INVENTORY_RECONCILE_QUEUE_URL.",
            },
        )

    tenant_uuid = resolve_tenant_id(current_user, tenant_id)
    await get_tenant(tenant_uuid, db)

    account = await get_account_for_tenant(tenant_uuid, body.account_id, db)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Account not found",
                "detail": "No AWS account found with the given ID for this tenant.",
            },
        )

    account_regions = list(account.regions or [])
    if body.region is not None and body.region not in set(account_regions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Bad request",
                "detail": "region must be one of the account's configured regions.",
            },
        )

    target_regions = [body.region] if body.region else (account_regions or [settings.AWS_REGION])
    services = settings.control_plane_inventory_services_list
    max_resources = int(settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD or 500)

    queue_url = settings.SQS_INVENTORY_RECONCILE_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    now = datetime.now(timezone.utc).isoformat()
    enqueued_jobs = 0

    try:
        for region in target_regions:
            for service in services:
                payload = build_reconcile_inventory_shard_job_payload(
                    tenant_id=tenant_uuid,
                    account_id=body.account_id,
                    region=region,
                    service=service,
                    created_at=now,
                    sweep_mode="global",
                    max_resources=max_resources,
                )
                sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
                enqueued_jobs += 1
    except ClientError as e:
        logger.exception("SQS send_message failed for action_reconcile: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Action reconciliation unavailable",
                "detail": "Could not enqueue reconcile jobs. Please try again later.",
            },
        ) from e

    scope: dict[str, str] = {"account_id": body.account_id}
    if body.region:
        scope["region"] = body.region

    return ReconcileActionsResponse(
        message="Action reconciliation jobs queued",
        tenant_id=str(tenant_uuid),
        scope=scope,
        enqueued_jobs=enqueued_jobs,
    )
