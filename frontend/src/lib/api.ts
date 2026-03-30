/**
 * API Client for AWS Security Autopilot
 * 
 * Handles all communication with the FastAPI backend.
 * Includes error handling and typed responses.
 */

import { getApiBaseUrl } from '@/lib/api-base-url';
const SESSION_EXPIRED_PATH = '/session-expired';
const CSRF_COOKIE_NAME = 'csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function getCookieValue(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const cookieEntry = document.cookie
    .split(';')
    .map(token => token.trim())
    .find(token => token.startsWith(`${name}=`));
  if (!cookieEntry) return null;
  return decodeURIComponent(cookieEntry.slice(name.length + 1));
}

function getCsrfToken(): string | null {
  return getCookieValue(CSRF_COOKIE_NAME);
}

function hasCookieSession(): boolean {
  return Boolean(getCsrfToken());
}

function applyCsrfHeader(headers: Headers, method?: string): void {
  const normalizedMethod = (method || 'GET').toUpperCase();
  if (!UNSAFE_METHODS.has(normalizedMethod)) return;
  if (headers.has(CSRF_HEADER_NAME)) return;
  const csrfToken = getCsrfToken();
  if (!csrfToken) return;
  headers.set(CSRF_HEADER_NAME, csrfToken);
}

// ============================================
// Types
// ============================================

export interface ApiError {
  error: string;
  detail?: string | unknown;  // FastAPI can return string, object, or array
  status: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

// Finding types
export interface FindingShadowOverlay {
  fingerprint?: string | null;
  source?: string | null;
  status_raw: string;
  status_normalized: string;
  status_reason?: string | null;
  last_observed_event_time?: string | null;
  last_evaluated_at?: string | null;
}

export interface ControlFamily {
  source_control_ids: string[];
  canonical_control_id: string | null;
  related_control_ids: string[];
  is_mapped: boolean;
}

export type RemediationVisibilityReason =
  | 'historical_resolved'
  | 'managed_on_account_scope'
  | 'managed_on_resource_scope'
  | 'no_current_remediation';

export interface Finding {
  id: string;
  finding_id: string;
  tenant_id: string;
  account_id: string;
  region: string;
  service?: string | null;
  aws_service?: string | null;
  severity_label: string;
  severity_normalized: number;
  status: string;
  canonical_status?: string;
  effective_status?: string;
  risk_acknowledged?: boolean;
  risk_acknowledged_at?: string | null;
  risk_acknowledged_by_user_id?: string | null;
  risk_acknowledged_group_key?: string | null;
  in_scope?: boolean;
  title: string;
  description: string | null;
  resource_id: string | null;
  resource_type: string | null;
  control_id: string | null;
  control_family?: ControlFamily | null;
  standard_name: string | null;
  first_observed_at: string | null;
  last_observed_at: string | null;
  updated_at: string | null;
  created_at: string;
  updated_at_db: string;
  raw_json?: Record<string, unknown>;
  shadow?: FindingShadowOverlay | null;
  // Step 6.3: exception state
  exception_id?: string | null;
  exception_expires_at?: string | null;
  exception_expired?: boolean | null;
  // Step 2B.1: finding source (security_hub | access_analyzer | inspector)
  source?: string;
  // Actionability hints for finding-level UX actions
  remediation_action_id?: string | null;
  remediation_action_type?: string | null;
  remediation_action_status?: string | null;
  remediation_action_account_id?: string | null;
  remediation_action_region?: string | null;
  remediation_action_group_id?: string | null;
  remediation_action_group_status_bucket?: string | null;
  remediation_action_group_latest_run_status?: string | null;
  latest_pr_bundle_run_id?: string | null;
  pending_confirmation?: boolean;
  pending_confirmation_started_at?: string | null;
  pending_confirmation_deadline_at?: string | null;
  pending_confirmation_message?: string | null;
  pending_confirmation_severity?: 'info' | 'warning' | null;
  status_message?: string | null;
  status_severity?: 'info' | 'warning' | null;
  followup_kind?: string | null;
  remediation_visibility_reason?: RemediationVisibilityReason | null;
  remediation_scope_owner?: 'account' | 'resource' | null;
  remediation_scope_message?: string | null;
}

export interface FindingsFilters {
  account_id?: string;
  region?: string;
  control_id?: string;
  resource_type?: string;
  resource_id?: string;
  severity?: string;
  status?: string;
  /** Step 2B.4: filter by source (security_hub, access_analyzer, inspector; single value or comma-separated) */
  source?: string;
  first_observed_since?: string;  // ISO8601 datetime
  last_observed_since?: string;   // ISO8601 datetime
  updated_since?: string;         // ISO8601 datetime
  limit?: number;
  offset?: number;
}

// Phase B: Grouped findings (GET /findings/grouped)
export interface FindingGroup {
  group_key: string;
  control_id?: string | null;
  control_family?: ControlFamily | null;
  rule_title: string;
  resource_type: string | null;
  finding_count: number;
  severity_distribution: Record<string, number>;
  account_ids: string[];
  regions: string[];
  risk_acknowledged: boolean;
  risk_acknowledged_count: number;
  remediation_action_id: string | null;
  remediation_action_type: string | null;
  remediation_action_status: string | null;
  remediation_action_group_id?: string | null;
  remediation_action_group_status_bucket?: string | null;
  remediation_action_group_latest_run_status?: string | null;
  pending_confirmation?: boolean;
  pending_confirmation_started_at?: string | null;
  pending_confirmation_deadline_at?: string | null;
  pending_confirmation_message?: string | null;
  pending_confirmation_severity?: 'info' | 'warning' | null;
  status_message?: string | null;
  status_severity?: 'info' | 'warning' | null;
  followup_kind?: string | null;
  remediation_visibility_reason?: RemediationVisibilityReason | null;
  remediation_scope_owner?: 'account' | 'resource' | null;
  remediation_scope_message?: string | null;
  is_shared_resource?: boolean;
}

export interface FindingGroupsFilters {
  account_id?: string;
  region?: string;
  control_id?: string;
  resource_id?: string;
  severity?: string;
  source?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export type FindingGroupActionType = 'suppress' | 'acknowledge_risk' | 'false_positive';

export interface FindingGroupActionRequest {
  action: FindingGroupActionType;
  group_key: string;
  reason?: string;
  ticket_link?: string;
  expires_at?: string;
  account_id?: string;
  region?: string;
  severity?: string;
  source?: string;
  status?: string;
  control_id?: string;
  resource_id?: string;
}

export interface FindingGroupActionResponse {
  action: FindingGroupActionType;
  group_key: string;
  matched_findings: number;
  acknowledged_findings: number;
  status_updates: number;
  exceptions_created: number;
  exceptions_updated: number;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}


// Meta / feature flags
export interface ScopeMetaResponse {
  only_in_scope_controls: boolean;
  in_scope_controls_count: number;
  disabled_sources: string[];
}

// AWS Account types
export interface AwsAccount {
  id: string;
  account_id: string;
  role_read_arn: string;
  role_write_arn: string | null;
  regions: string[];
  status: 'pending' | 'validated' | 'error' | 'disabled';
  last_validated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AwsAccountValidationResponse {
  status: 'validated' | 'error';
  account_id: string;
  last_validated_at: string | null;
  permissions_ok: boolean;
  missing_permissions: string[];
  warnings: string[];
}

export interface RegisterAccountRequest {
  account_id: string;
  role_read_arn: string;
  role_write_arn?: string | null;  // Optional at onboarding; required only for direct fixes
  regions: string[];
  tenant_id: string; // TODO: Remove when auth is implemented
}

export interface UpdateAccountRequest {
  role_read_arn?: string;
  role_write_arn?: string | null;
  regions?: string[];
  status?: 'disabled' | 'validated';
}

export interface IngestResponse {
  account_id: string;
  jobs_queued: number;
  regions: string[];
  message_ids: string[];
  message: string;
}

export interface IngestProgressResponse {
  account_id: string;
  source?: 'security_hub' | 'access_analyzer' | 'inspector' | null;
  started_after: string;
  elapsed_seconds: number;
  status: 'queued' | 'running' | 'completed' | 'no_changes_detected';
  progress: number;
  percent_complete?: number;
  estimated_time_remaining?: number | null;
  updated_findings_count: number;
  last_finding_update_at?: string | null;
  message: string;
}

export interface RegionServiceReadiness {
  region: string;
  security_hub_enabled: boolean;
  aws_config_enabled: boolean;
  access_analyzer_enabled: boolean;
  inspector_enabled: boolean;
  security_hub_error: string | null;
  aws_config_error: string | null;
  access_analyzer_error: string | null;
  inspector_error: string | null;
}

export interface AccountServiceReadiness {
  account_id: string;
  overall_ready: boolean;
  all_security_hub_enabled: boolean;
  all_aws_config_enabled: boolean;
  all_access_analyzer_enabled: boolean;
  all_inspector_enabled: boolean;
  missing_security_hub_regions: string[];
  missing_aws_config_regions: string[];
  missing_access_analyzer_regions: string[];
  missing_inspector_regions: string[];
  regions: RegionServiceReadiness[];
}

export interface RegionControlPlaneReadiness {
  region: string;
  last_event_time: string | null;
  last_intake_time: string | null;
  is_recent: boolean;
  age_minutes: number | null;
}

export interface AccountControlPlaneReadiness {
  account_id: string;
  stale_after_minutes: number;
  overall_ready: boolean;
  missing_regions: string[];
  regions: RegionControlPlaneReadiness[];
}

export interface ControlPlaneIntakeResponse {
  enqueued: number;
  dropped: number;
  drop_reasons: Record<string, number>;
}

export interface OnboardingFastPathResponse {
  account_id: string;
  fast_path_triggered: boolean;
  triggered_at: string;
  ingest_jobs_queued: number;
  ingest_regions: string[];
  ingest_message_ids: string[];
  compute_actions_queued: boolean;
  compute_actions_message_id: string | null;
  missing_security_hub_regions: string[];
  missing_aws_config_regions: string[];
  missing_inspector_regions: string[];
  missing_control_plane_regions: string[];
  missing_access_analyzer_regions: string[];
  message: string;
}

export interface ReadRoleUpdateRequest {
  stack_name?: string;
}

export interface ReadRoleUpdateResponse {
  account_id: string;
  stack_name: string;
  template_url: string;
  template_version?: string | null;
  status: 'update_started' | 'already_up_to_date';
  stack_id?: string | null;
  message: string;
}

export interface ReadRoleUpdateStatusResponse {
  account_id: string;
  stack_name: string;
  current_template_url?: string | null;
  current_template_version?: string | null;
  latest_template_url: string;
  latest_template_version?: string | null;
  update_available: boolean;
  message: string;
}

export interface ReconciliationServiceCheck {
  service: string;
  ok: boolean;
  missing_permissions: string[];
  warnings: string[];
}

export interface ReconciliationPreflightResponse {
  account_id: string;
  region_used: string;
  services: string[];
  ok: boolean;
  assume_role_ok: boolean;
  assume_role_error?: string | null;
  missing_permissions: string[];
  warnings: string[];
  service_checks: ReconciliationServiceCheck[];
}

export interface ReconciliationRunResponse {
  run_id: string;
  account_id: string;
  status: string;
  submitted_at: string;
  total_shards: number;
  enqueued_shards: number;
  failed_shards: number;
  preflight?: ReconciliationPreflightResponse | null;
}

export interface ReconciliationRunItem {
  id: string;
  account_id: string;
  trigger_type: string;
  status: string;
  services: string[];
  regions: string[];
  sweep_mode: string;
  max_resources: number | null;
  total_shards: number;
  enqueued_shards: number;
  running_shards: number;
  succeeded_shards: number;
  failed_shards: number;
  last_error?: string | null;
  submitted_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ReconciliationAlert {
  code: string;
  count: number;
  detail: string;
}

export interface ReconciliationStatusSummary {
  total_runs: number;
  queued_runs: number;
  running_runs: number;
  succeeded_runs: number;
  partial_failed_runs: number;
  failed_runs: number;
  success_rate: number;
  lag_since_last_success_minutes: number | null;
  last_error: string | null;
  failure_reasons: Record<string, number>;
  alerts: ReconciliationAlert[];
}

export interface ReconciliationStatusResponse {
  generated_at: string;
  account_id?: string | null;
  summary: ReconciliationStatusSummary;
  runs: ReconciliationRunItem[];
}

export interface ReconciliationCoverageTopControl {
  control_id: string;
  unmatched_count: number;
}

export interface ReconciliationCoverageResponse {
  generated_at: string;
  account_id?: string | null;
  in_scope_total: number;
  in_scope_matched: number;
  in_scope_unmatched: number;
  coverage_rate: number;
  in_scope_new_total: number;
  in_scope_new_matched: number;
  in_scope_new_coverage_rate: number;
  top_unmatched_controls: ReconciliationCoverageTopControl[];
}

export interface ReconciliationSettings {
  account_id: string;
  enabled: boolean;
  interval_minutes: number;
  services: string[];
  regions: string[];
  max_resources: number;
  sweep_mode: string;
  cooldown_minutes: number;
  last_enqueued_at?: string | null;
  last_run_id?: string | null;
}

export interface ReconciliationRunRequest {
  account_id: string;
  regions?: string[];
  services?: string[];
  max_resources?: number;
  sweep_mode?: string;
  require_preflight_pass?: boolean;
  force?: boolean;
}

export interface ReconciliationPreflightRequest {
  account_id: string;
  regions?: string[];
  services?: string[];
}

export interface ReconciliationSettingsUpdateRequest {
  enabled?: boolean;
  interval_minutes?: number;
  services?: string[];
  regions?: string[];
  max_resources?: number;
  sweep_mode?: string;
  cooldown_minutes?: number;
}

// Action types (Step 5.5)
export interface ActionScoreFactorProvenance {
  source: string;
  observed_at?: string | null;
  decay_applied: number;
  final_contribution: number;
  base_contribution?: number | null;
}

export interface ActionScoreFactor {
  factor_name: string;
  weight: number;
  contribution: number;
  evidence_source: string;
  signals: string[];
  explanation: string;
  provenance: ActionScoreFactorProvenance[];
}

export interface ActionThreatSignal {
  source: string;
  source_label?: string | null;
  signal_type?: string | null;
  identifier?: string | null;
  cve_id?: string | null;
  timestamp?: string | null;
  confidence?: number | null;
  requested_points?: number | null;
  applied_points?: number | null;
  base_points?: number | null;
  decay_applied?: number | null;
  final_contribution?: number | null;
  capped?: boolean | null;
}

export interface ActionExploitScoreComponent {
  points?: number;
  heuristic_points?: number;
  threat_intel_points_requested?: number;
  threat_intel_points_applied?: number;
  applied_threat_signals?: ActionThreatSignal[];
  [key: string]: unknown;
}

export interface ActionScoreComponents {
  exploit_signals?: ActionExploitScoreComponent;
  [key: string]: unknown;
}

export interface ActionCriticalityDimension {
  dimension: string;
  label: string;
  weight: number;
  matched: boolean;
  contribution: number;
  signals: string[];
  explanation: string;
}

export interface ActionCriticality {
  status: 'known' | 'unknown';
  score: number;
  tier: 'critical' | 'high' | 'medium' | 'unknown';
  weight: number;
  dimensions: ActionCriticalityDimension[];
  explanation: string;
}

export interface ActionBusinessImpactMatrixPosition {
  row: 'critical' | 'high' | 'medium' | 'low';
  column: 'critical' | 'high' | 'medium' | 'unknown';
  cell: string;
  risk_weight: number;
  criticality_weight: number;
  rank: number;
  explanation: string;
}

export interface ActionBusinessImpact {
  technical_risk_score: number;
  technical_risk_tier: 'critical' | 'high' | 'medium' | 'low';
  criticality: ActionCriticality;
  matrix_position: ActionBusinessImpactMatrixPosition;
  summary: string;
}

export interface ActionListItem {
  id: string;
  action_type: string;
  target_id: string;
  account_id: string;
  region: string | null;
  score: number;
  score_components?: ActionScoreComponents | null;
  score_factors?: ActionScoreFactor[];
  business_impact: ActionBusinessImpact;
  priority: number;
  status: string;
  title: string;
  control_id: string | null;
  control_family?: ControlFamily | null;
  resource_id: string | null;
  owner_type?: string | null;
  owner_key?: string | null;
  owner_label?: string | null;
  updated_at: string | null;
  finding_count: number;
  // Step 6.3: exception state
  exception_id?: string | null;
  exception_expires_at?: string | null;
  exception_expired?: boolean | null;
  // Optional execution-group fields (group_by=batch)
  is_batch?: boolean;
  batch_action_count?: number | null;
  batch_finding_count?: number | null;
}

export interface ActionDetailFinding {
  id: string;
  finding_id: string;
  severity_label: string;
  title: string;
  resource_id: string | null;
  account_id: string;
  region: string;
  updated_at: string | null;
}

export interface ActionRecommendationMatrixPosition {
  risk_tier: 'low' | 'medium' | 'high';
  business_criticality: 'low' | 'medium' | 'high';
  cell: string;
}

export interface ActionRecommendationEvidence {
  score: number;
  context_incomplete: boolean;
  data_sensitivity: number;
  internet_exposure: number;
  privilege_level: number;
  exploit_signals: number;
  matched_signals: string[];
}

export interface ActionRecommendation {
  mode: 'direct_fix_candidate' | 'pr_only' | 'exception_review';
  default_mode: 'direct_fix_candidate' | 'pr_only' | 'exception_review';
  advisory: boolean;
  enforced_by_policy?: string | null;
  rationale: string;
  matrix_position: ActionRecommendationMatrixPosition;
  evidence: ActionRecommendationEvidence;
}

export interface ActionImplementationArtifact {
  run_id: string;
  run_status: string;
  run_mode: string;
  artifact_key: string;
  kind: string;
  label: string;
  description: string;
  href: string;
  executable: boolean;
  generated_at: string | null;
  closure_status: string;
  metadata: Record<string, unknown>;
}

export interface ExecutionGuidanceCheck {
  code: string;
  status: 'pass' | 'warn' | 'unknown' | 'fail' | 'info';
  message: string;
}

export interface ExecutionGuidanceRollback {
  summary: string;
  command: string;
  notes: string[];
}

export interface ActionExecutionGuidance {
  strategy_id: string;
  label: string;
  mode: 'pr_only' | 'direct_fix';
  recommended: boolean;
  blast_radius: 'account' | 'resource' | 'access_changing';
  blast_radius_summary: string;
  pre_checks: ExecutionGuidanceCheck[];
  expected_outcome: string;
  post_checks: ExecutionGuidanceCheck[];
  rollback: ExecutionGuidanceRollback;
}

export interface ActionGraphLimits {
  max_related_findings: number;
  max_related_actions: number;
  max_inventory_assets: number;
  max_connected_assets: number;
  max_identity_nodes: number;
  max_blast_radius_neighbors: number;
}

export interface ActionGraphAsset {
  label: string;
  resource_id?: string | null;
  resource_type?: string | null;
  resource_key?: string | null;
  relationship: string;
  finding_count: number;
  action_count: number;
  inventory_services: string[];
}

export interface ActionGraphIdentityNode {
  node_type: 'principal' | 'account' | 'resource';
  label: string;
  value: string;
  source: string;
}

export interface ActionBlastRadiusNeighbor {
  scope: 'anchor' | 'account' | 'related';
  label: string;
  resource_id?: string | null;
  resource_type?: string | null;
  resource_key?: string | null;
  finding_count: number;
  open_action_count: number;
  inventory_service_count: number;
  controls: string[];
}

export interface ActionGraphContext {
  status: 'available' | 'unavailable';
  availability_reason?: string | null;
  source: string;
  self_resolved: boolean;
  connected_assets: ActionGraphAsset[];
  identity_path: ActionGraphIdentityNode[];
  blast_radius_neighborhood: ActionBlastRadiusNeighbor[];
  truncated_sections: string[];
  limits: ActionGraphLimits;
}

export interface ActionAttackPathNode {
  node_id: string;
  kind: 'entry_point' | 'identity' | 'target_asset' | 'business_impact' | 'next_step';
  label: string;
  detail?: string | null;
  badges?: string[];
  facts?: ActionAttackPathFact[];
}

export interface ActionAttackPathFact {
  label: string;
  value: string;
  tone: 'default' | 'accent' | 'code';
}

export interface ActionAttackPathEdge {
  source_node_id: string;
  target_node_id: string;
  label: string;
}

export interface ActionAttackPathView {
  status: 'available' | 'partial' | 'unavailable' | 'context_incomplete';
  summary: string;
  path_nodes: ActionAttackPathNode[];
  path_edges: ActionAttackPathEdge[];
  entry_points: ActionAttackPathNode[];
  target_assets: ActionAttackPathNode[];
  business_impact_summary?: string | null;
  risk_reasons: string[];
  recommendation_summary?: string | null;
  confidence: number;
  truncated: boolean;
  availability_reason?: string | null;
}

export interface AttackPathSummaryItem {
  id: string;
  status: 'available' | 'partial' | 'unavailable' | 'context_incomplete';
  rank: number;
  confidence: number;
  entry_points: ActionAttackPathNode[];
  target_assets: ActionAttackPathNode[];
  summary: string;
  business_impact_summary?: string | null;
  recommended_fix_summary?: string | null;
  owner_labels: string[];
  linked_action_ids: string[];
  rank_factors?: AttackPathRankFactor[];
  freshness?: AttackPathFreshness | null;
  remediation_summary?: AttackPathRemediationSummary | null;
  runtime_signals?: AttackPathRuntimeSignals | null;
  closure_targets?: AttackPathClosureTargets | null;
  governance_summary?: AttackPathExternalWorkflowSummary | null;
  access_scope?: AttackPathAccessScope | null;
  computed_at?: string | null;
  stale_after?: string | null;
  is_stale?: boolean;
}

export interface AttackPathRankFactor {
  factor_name?: string;
  label?: string;
  contribution?: number;
  explanation?: string;
  tone?: 'default' | 'accent' | 'code' | 'positive' | 'negative' | 'warning';
}

export interface AttackPathFreshness {
  label?: string;
  summary?: string;
  observed_at?: string | null;
  score?: number;
  stale?: boolean;
}

export interface AttackPathRuntimeSignals {
  workload_presence: 'present' | 'unknown';
  publicly_reachable: boolean;
  sensitive_target_count: number;
  identity_hops: number;
  confidence: number;
  summary: string;
}

export interface AttackPathExposureValidation {
  status: 'verified' | 'partial' | 'unverified';
  summary: string;
  observed_at?: string | null;
}

export interface AttackPathOwner {
  owner_key?: string;
  owner_label?: string;
  owner_type?: string;
}

export interface AttackPathLinkedAction {
  id: string;
  title?: string;
  priority?: number;
  status?: string;
  owner_label?: string;
  account_id?: string;
  resource_id?: string | null;
}

export interface AttackPathRemediationSummary {
  linked_actions_total: number;
  open_actions: number;
  in_progress_actions: number;
  resolved_actions: number;
  highest_priority_open?: number | null;
  coverage_summary: string;
}

export interface AttackPathViewOption {
  key: string;
  label: string;
  description: string;
}

export interface AttackPathRepositoryLink {
  provider: string;
  repository: string;
  base_branch?: string | null;
  root_path?: string | null;
  source_run_id?: string | null;
}

export interface AttackPathCodeContext {
  owner_label: string;
  service_owner_key?: string | null;
  repository_count: number;
  implementation_artifact_count: number;
  summary: string;
}

export interface AttackPathClosureTargets {
  open_action_ids: string[];
  in_progress_action_ids: string[];
  resolved_action_ids: string[];
  summary: string;
}

export interface AttackPathExternalWorkflowSummary {
  provider_count: number;
  drifted_count: number;
  in_sync_count: number;
  linked_items: string[];
  summary: string;
}

export interface AttackPathExceptionSummary {
  active_count: number;
  expiring_count: number;
  summary: string;
}

export interface AttackPathEvidenceExports {
  evidence_item_count: number;
  implementation_artifact_count: number;
  export_ready: boolean;
  summary: string;
}

export interface AttackPathAccessScope {
  scope: 'tenant_scoped';
  evidence_visibility: 'full';
  restricted_sections: string[];
  export_allowed: boolean;
}

export interface AttackPathEvidence {
  label?: string;
  value?: string;
  source?: string;
}

export interface AttackPathProvenance {
  source?: string;
  label?: string;
  value?: string;
}

export interface AttackPathBusinessImpact {
  summary?: string | null;
  criticality?: Record<string, unknown>;
  matrix_position?: Record<string, unknown>;
}

export interface AttackPathRecommendedFix {
  summary?: string | null;
  strategy_id?: string | null;
  mode?: string | null;
}

export interface ActionAttackPathDetail extends AttackPathSummaryItem {
  rank_factors: AttackPathRankFactor[];
  freshness?: AttackPathFreshness | null;
  path_nodes: ActionAttackPathNode[];
  path_edges: ActionAttackPathEdge[];
  business_impact?: AttackPathBusinessImpact | null;
  risk_reasons: string[];
  owners: AttackPathOwner[];
  recommended_fix?: AttackPathRecommendedFix | null;
  linked_actions: AttackPathLinkedAction[];
  evidence: AttackPathEvidence[];
  provenance: AttackPathProvenance[];
  exposure_validation?: AttackPathExposureValidation | null;
  code_context?: AttackPathCodeContext | null;
  linked_repositories?: AttackPathRepositoryLink[];
  implementation_artifacts?: ActionImplementationArtifact[];
  external_workflow_summary?: AttackPathExternalWorkflowSummary | null;
  exception_summary?: AttackPathExceptionSummary | null;
  evidence_exports?: AttackPathEvidenceExports | null;
  refresh_status?: string | null;
  truncated: boolean;
  availability_reason?: string | null;
}

export interface AttackPathsFilters {
  account_id?: string;
  action_id?: string;
  owner_key?: string;
  resource_id?: string;
  status?: 'available' | 'partial' | 'unavailable' | 'context_incomplete';
  view?: string;
  limit?: number;
  offset?: number;
}

export interface AttackPathsListResponse extends PaginatedResponse<AttackPathSummaryItem> {
  selected_view?: string | null;
  available_views?: AttackPathViewOption[];
}

export interface ActionDetail {
  id: string;
  tenant_id: string;
  action_type: string;
  target_id: string;
  account_id: string;
  region: string | null;
  score: number;
  score_components?: ActionScoreComponents | null;
  score_factors?: ActionScoreFactor[];
  business_impact: ActionBusinessImpact;
  context_incomplete?: boolean;
  path_id?: string | null;
  priority: number;
  status: string;
  title: string;
  description: string | null;
  what_is_wrong: string;
  what_the_fix_does: string;
  control_id: string | null;
  control_family?: ControlFamily | null;
  resource_id: string | null;
  resource_type: string | null;
  owner_type: string;
  owner_key: string;
  owner_label: string;
  created_at: string | null;
  updated_at: string | null;
  findings: ActionDetailFinding[];
  implementation_artifacts?: ActionImplementationArtifact[];
  // Step 6.3: exception state
  exception_id?: string | null;
  exception_expires_at?: string | null;
  exception_expired?: boolean | null;
  execution_guidance?: ActionExecutionGuidance[];
  external_sync?: ActionExternalSyncProvider[];
  graph_context?: ActionGraphContext;
  attack_path_view?: ActionAttackPathView;
  recommendation: ActionRecommendation;
}

export interface ActionExternalSyncEvent {
  id: string;
  source: string;
  event_type: string;
  created_at?: string | null;
  external_status?: string | null;
  mapped_internal_status?: string | null;
  preferred_external_status?: string | null;
  resolution_decision?: string | null;
  decision_detail?: string | null;
}

export interface ActionExternalSyncProvider {
  provider: string;
  external_id?: string | null;
  external_key?: string | null;
  external_url?: string | null;
  external_status?: string | null;
  sync_status?: string | null;
  preferred_external_status?: string | null;
  mapped_internal_status?: string | null;
  canonical_internal_status?: string | null;
  resolution_decision?: string | null;
  conflict_reason?: string | null;
  last_inbound_at?: string | null;
  last_outbound_at?: string | null;
  last_event_at?: string | null;
  last_reconciled_at?: string | null;
  assignee_sync_state: string;
  assignee_sync_detail?: string | null;
  recent_events?: ActionExternalSyncEvent[];
}

export interface ActionsFilters {
  action_type?: string;
  account_id?: string;
  region?: string;
  control_id?: string;
  resource_id?: string;
  q?: string;
  ids?: string[];
  status?: string;
  owner_type?: 'user' | 'team' | 'service' | 'unassigned';
  owner_key?: string;
  owner_queue?: 'open' | 'overdue' | 'expiring_exceptions' | 'blocked_fixes';
  group_by?: 'resource' | 'batch';
  include_orphans?: boolean;
  limit?: number;
  offset?: number;
}

export interface ComputeActionsResponse {
  message: string;
  tenant_id: string;
  scope: Record<string, string>;
}

export interface ActionGroupCounters {
  run_successful: number;
  run_not_successful: number;
  metadata_only: number;
  not_run_yet: number;
  total_actions: number;
}

export interface ActionGroupListItem {
  id: string;
  group_key: string;
  action_type: string;
  account_id: string;
  region: string | null;
  created_at: string | null;
  updated_at: string | null;
  metadata: Record<string, unknown>;
  counters: ActionGroupCounters;
}

export interface ActionGroupMember {
  action_id: string;
  title: string;
  control_id: string | null;
  control_family?: ControlFamily | null;
  resource_id: string | null;
  action_status: string;
  priority: number;
  assigned_at: string | null;
  status_bucket:
    | 'not_run_yet'
    | 'run_not_successful'
    | 'run_finished_metadata_only'
    | 'run_successful_pending_confirmation'
    | 'run_successful_needs_followup'
    | 'run_successful_confirmed'
    | string;
  last_attempt_at: string | null;
  last_confirmed_at: string | null;
  last_confirmation_source: 'security_hub' | 'control_plane_reconcile' | null | string;
  latest_run: {
    id: string | null;
    status: string | null;
    started_at: string | null;
    finished_at: string | null;
  };
  pending_confirmation: boolean;
  pending_confirmation_started_at: string | null;
  pending_confirmation_deadline_at: string | null;
  pending_confirmation_message: string | null;
  pending_confirmation_severity: 'info' | 'warning' | null;
  status_message?: string | null;
  status_severity?: 'info' | 'warning' | null;
  followup_kind?: string | null;
}

export interface ActionGroupDetail {
  id: string;
  tenant_id: string;
  group_key: string;
  action_type: string;
  account_id: string;
  region: string | null;
  created_at: string | null;
  updated_at: string | null;
  metadata: Record<string, unknown>;
  counters: ActionGroupCounters;
  members: ActionGroupMember[];
  can_generate_bundle: boolean;
  blocked_reason: string | null;
  blocked_detail: string | null;
  blocked_by_run_id: string | null;
}

export interface ActionGroupRunResultItem {
  action_id: string;
  execution_status: string;
  execution_error_code: string | null;
  execution_error_message: string | null;
  result_type: string | null;
  support_tier: string | null;
  reason: string | null;
  blocked_reasons: string[];
  decision_rationale: string | null;
  preservation_summary: Record<string, unknown>;
  strategy_inputs: Record<string, unknown>;
  execution_started_at: string | null;
  execution_finished_at: string | null;
}

export interface ActionGroupSharedExecutionResultItem {
  folder: string;
  kind: string;
  execution_status: string;
  execution_error_code: string | null;
  execution_error_message: string | null;
  details: Record<string, unknown>;
}

export interface ActionGroupRunTimelineItem {
  id: string;
  remediation_run_id: string | null;
  initiated_by_user_id: string | null;
  mode: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  reporting_source: string;
  created_at: string;
  updated_at: string;
  results: ActionGroupRunResultItem[];
  shared_execution_results: ActionGroupSharedExecutionResultItem[];
}

export interface ActionGroupBundleRunResponse {
  group_run_id: string;
  remediation_run_id: string;
  reporting_token: string;
  reporting_callback_url: string;
  status: string;
}

// Exception types (Step 6.2/6.4)
export interface Exception {
  id: string;
  tenant_id: string;
  entity_type: 'finding' | 'action';
  entity_id: string;
  reason: string;
  approved_by_user_id: string;
  approved_by_email: string | null;
  ticket_link: string | null;
  expires_at: string;
  created_at: string;
  updated_at: string;
}

export interface ExceptionListItem {
  id: string;
  entity_type: 'finding' | 'action';
  entity_id: string;
  reason: string;
  approved_by_user_id: string;
  approved_by_email: string | null;
  ticket_link: string | null;
  expires_at: string;
  created_at: string;
  is_expired: boolean;
}

export interface CreateExceptionRequest {
  entity_type: 'finding' | 'action';
  entity_id: string;
  reason: string;
  expires_at: string;  // ISO8601
  ticket_link?: string;
}

export interface ExceptionsFilters {
  entity_type?: 'finding' | 'action';
  entity_id?: string;
  active_only?: boolean;
  limit?: number;
  offset?: number;
}

// Audit log types (CMP-003)
export interface AuditLogRecord {
  id: string;
  tenant_id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  timestamp: string | null;
  created_at: string | null;
  payload: Record<string, unknown> | null;
}

export interface AuditLogListResponse {
  items: AuditLogRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditLogFilters {
  actor_user_id?: string;
  resource_type?: string;
  resource_id?: string;
  from_date?: string;
  to_date?: string;
  limit?: number;
  offset?: number;
}

// ============================================
// Core request function
// ============================================

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

function getApiUrl(endpoint: string): string {
  return `${getApiBaseUrl()}${endpoint}`;
}

async function request<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, ...fetchOptions } = options;
  
  // Build URL with query params
  let url = getApiUrl(endpoint);
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  const headers = new Headers(fetchOptions.headers);
  const hasFormDataBody = typeof FormData !== 'undefined' && fetchOptions.body instanceof FormData;
  if (!headers.has('Content-Type') && !hasFormDataBody) {
    headers.set('Content-Type', 'application/json');
  }
  applyCsrfHeader(headers, fetchOptions.method);

  const response = await fetch(url, {
    ...fetchOptions,
    headers,
    credentials: 'include',
  });

  // Handle non-2xx responses
  if (!response.ok) {
    // Session expired or invalid: send user to re-auth screen
    if (response.status === 401 && typeof window !== 'undefined') {
      window.location.href = SESSION_EXPIRED_PATH;
    }

    let errorData: ApiError;
    try {
      const json = await response.json();
      const rootError =
        typeof json.error === 'object' && json.error !== null
          ? (json.error as { message?: unknown })
          : null;
      errorData = {
        error:
          typeof json.error === 'string'
            ? json.error
            : typeof rootError?.message === 'string'
              ? rootError.message
              : 'Request failed',
        detail: json.detail ?? rootError ?? undefined,
        status: response.status,
      };
    } catch {
      errorData = {
        error: response.statusText || 'Request failed',
        status: response.status,
      };
    }
    throw errorData;
  }

  // Handle empty responses
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// ============================================
// Findings API
// ============================================

export async function getScopeMeta(): Promise<ScopeMetaResponse> {
  return request<ScopeMetaResponse>('/api/meta/scope');
}

export async function getFindings(
  filters: FindingsFilters = {},
  tenantId?: string
): Promise<PaginatedResponse<Finding>> {
  // Only include tenant_id when no browser session cookie is present.
  const hasSession = hasCookieSession();
  const params: Record<string, string | number | boolean | undefined> = {
    account_id: filters.account_id,
    region: filters.region,
    control_id: filters.control_id,
    resource_type: filters.resource_type,
    resource_id: filters.resource_id,
    severity: filters.severity,
    status: filters.status,
    source: filters.source,
    first_observed_since: filters.first_observed_since,
    last_observed_since: filters.last_observed_since,
    updated_since: filters.updated_since,
    limit: filters.limit ?? 50,
    offset: filters.offset ?? 0,
    tenant_id: hasSession ? undefined : tenantId,
  };

  return request<PaginatedResponse<Finding>>('/api/findings', { params });
}

export async function getFinding(
  id: string,
  tenantId?: string
): Promise<Finding> {
  const hasSession = hasCookieSession();
  const params: Record<string, string | undefined> = {
    tenant_id: hasSession ? undefined : tenantId,
  };

  return request<Finding>(`/api/findings/${id}`, { params });
}

export async function getFindingGroups(
  filters: FindingGroupsFilters = {},
  tenantId?: string
): Promise<PaginatedResponse<FindingGroup>> {
  const hasSession = hasCookieSession();
  const params: Record<string, string | number | undefined> = {
    account_id: filters.account_id,
    region: filters.region,
    control_id: filters.control_id,
    resource_id: filters.resource_id,
    severity: filters.severity,
    source: filters.source,
    status: filters.status,
    limit: filters.limit ?? 50,
    offset: filters.offset ?? 0,
    tenant_id: hasSession ? undefined : tenantId,
  };
  return request<PaginatedResponse<FindingGroup>>('/api/findings/grouped', { params });
}

export async function applyFindingGroupAction(
  body: FindingGroupActionRequest
): Promise<FindingGroupActionResponse> {
  return request<FindingGroupActionResponse>('/api/findings/group-actions', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}



// ============================================
// AWS Accounts API
// ============================================

export async function getAccounts(
  tenantId?: string
): Promise<AwsAccount[]> {
  const hasSession = hasCookieSession();
  const params = { tenant_id: hasSession ? undefined : tenantId };
  return request<AwsAccount[]>('/api/aws/accounts', { params });
}

export async function registerAccount(
  data: RegisterAccountRequest
): Promise<AwsAccount> {
  return request<AwsAccount>('/api/aws/accounts', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function validateAccount(
  accountId: string,
  tenantId?: string
): Promise<AwsAccountValidationResponse> {
  const hasSession = hasCookieSession();
  return request<AwsAccountValidationResponse>(`/api/aws/accounts/${accountId}/validate`, {
    method: 'POST',
    params: { tenant_id: hasSession ? undefined : tenantId },
  });
}

/** Update account roles, regions, and/or status. */
export async function updateAccount(
  accountId: string,
  body: UpdateAccountRequest,
  tenantId?: string
): Promise<AwsAccount> {
  const hasSession = hasCookieSession();
  return request<AwsAccount>(`/api/aws/accounts/${accountId}`, {
    method: 'PATCH',
    params: { tenant_id: hasSession ? undefined : tenantId },
    body: JSON.stringify(body),
  });
}

/** Remove AWS account from the tenant. */
export async function deleteAccount(
  accountId: string,
  tenantId?: string
): Promise<void> {
  const hasSession = hasCookieSession();
  return request<void>(`/api/aws/accounts/${accountId}`, {
    method: 'DELETE',
    params: { tenant_id: hasSession ? undefined : tenantId },
  });
}

export async function triggerIngest(
  accountId: string,
  tenantId?: string,
  regions?: string[]
): Promise<IngestResponse> {
  const hasSession = hasCookieSession();
  return request<IngestResponse>(`/api/aws/accounts/${accountId}/ingest`, {
    method: 'POST',
    params: { tenant_id: hasSession ? undefined : tenantId },
    body: JSON.stringify({ regions }),
  });
}

export async function getIngestProgress(
  accountId: string,
  params: {
    started_after: string;
    source?: 'security_hub' | 'access_analyzer' | 'inspector';
  },
  tenantId?: string
): Promise<IngestProgressResponse> {
  const hasSession = hasCookieSession();
  return request<IngestProgressResponse>(`/api/aws/accounts/${accountId}/ingest-progress`, {
    method: 'GET',
    params: {
      started_after: params.started_after,
      source: params.source,
      tenant_id: hasSession ? undefined : tenantId,
    },
  });
}

export async function checkAccountServiceReadiness(
  accountId: string,
  tenantId?: string
): Promise<AccountServiceReadiness> {
  const hasSession = hasCookieSession();
  return request<AccountServiceReadiness>(`/api/aws/accounts/${accountId}/service-readiness`, {
    method: 'POST',
    params: { tenant_id: hasSession ? undefined : tenantId },
  });
}

export async function checkAccountControlPlaneReadiness(
  accountId: string,
  staleAfterMinutes: number = 30,
  tenantId?: string
): Promise<AccountControlPlaneReadiness> {
  const hasSession = hasCookieSession();
  return request<AccountControlPlaneReadiness>(`/api/aws/accounts/${accountId}/control-plane-readiness`, {
    method: 'GET',
    params: {
      stale_after_minutes: staleAfterMinutes,
      tenant_id: hasSession ? undefined : tenantId,
    },
  });
}

function randomSyntheticEventId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `synthetic-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function sendSyntheticControlPlaneEvent(
  accountId: string,
  region: string,
  token: string
): Promise<ControlPlaneIntakeResponse> {
  const nowIso = new Date().toISOString();
  const eventId = randomSyntheticEventId();
  const detailEventId = `detail-${randomSyntheticEventId()}`;
  return request<ControlPlaneIntakeResponse>('/api/control-plane/events', {
    method: 'POST',
    headers: { 'X-Control-Plane-Token': token.trim() },
    body: JSON.stringify({
      id: eventId,
      time: nowIso,
      account: accountId,
      region,
      source: 'security.autopilot.synthetic',
      'detail-type': 'AWS API Call via CloudTrail',
      detail: {
        eventName: 'AuthorizeSecurityGroupIngress',
        eventTime: nowIso,
        eventID: detailEventId,
        userIdentity: { accountId },
        awsRegion: region,
        eventCategory: 'Management',
      },
    }),
  });
}

export async function sendSyntheticControlPlaneEventForAccount(
  accountId: string,
  region: string,
  tenantId?: string
): Promise<ControlPlaneIntakeResponse> {
  const hasSession = hasCookieSession();
  return request<ControlPlaneIntakeResponse>(`/api/aws/accounts/${accountId}/control-plane-synthetic-event`, {
    method: 'POST',
    params: {
      region,
      tenant_id: hasSession ? undefined : tenantId,
    },
  });
}

export async function triggerOnboardingFastPath(
  accountId: string,
  tenantId?: string
): Promise<OnboardingFastPathResponse> {
  const hasSession = hasCookieSession();
  return request<OnboardingFastPathResponse>(`/api/aws/accounts/${accountId}/onboarding-fast-path`, {
    method: 'POST',
    params: { tenant_id: hasSession ? undefined : tenantId },
  });
}

export async function updateReadRoleStack(
  accountId: string,
  body: ReadRoleUpdateRequest = {},
  tenantId?: string
): Promise<ReadRoleUpdateResponse> {
  const hasSession = hasCookieSession();
  return request<ReadRoleUpdateResponse>(`/api/aws/accounts/${accountId}/read-role/update`, {
    method: 'POST',
    params: { tenant_id: hasSession ? undefined : tenantId },
    body: JSON.stringify(body),
  });
}

export async function getReadRoleUpdateStatus(
  accountId: string,
  stackName?: string,
  tenantId?: string
): Promise<ReadRoleUpdateStatusResponse> {
  const hasSession = hasCookieSession();
  return request<ReadRoleUpdateStatusResponse>(`/api/aws/accounts/${accountId}/read-role/update-status`, {
    method: 'GET',
    params: {
      stack_name: stackName,
      tenant_id: hasSession ? undefined : tenantId,
    },
  });
}

/** Step 2B.1: Trigger IAM Access Analyzer ingestion (one job per region). */
export async function triggerIngestAccessAnalyzer(
  accountId: string,
  tenantId?: string,
  regions?: string[]
): Promise<IngestResponse> {
  const hasSession = hasCookieSession();
  return request<IngestResponse>(`/api/aws/accounts/${accountId}/ingest-access-analyzer`, {
    method: 'POST',
    params: { tenant_id: hasSession ? undefined : tenantId },
    body: JSON.stringify({ regions }),
  });
}

/** Step 2B.2: Trigger Amazon Inspector v2 ingestion (one job per region). */
export async function triggerIngestInspector(
  accountId: string,
  tenantId?: string,
  regions?: string[]
): Promise<IngestResponse> {
  const hasSession = hasCookieSession();
  return request<IngestResponse>(`/api/aws/accounts/${accountId}/ingest-inspector`, {
    method: 'POST',
    params: { tenant_id: hasSession ? undefined : tenantId },
    body: JSON.stringify({ regions }),
  });
}

export async function preflightReconciliation(
  body: ReconciliationPreflightRequest,
  tenantId?: string
): Promise<ReconciliationPreflightResponse> {
  const hasSession = hasCookieSession();
  return request<ReconciliationPreflightResponse>('/api/reconciliation/preflight', {
    method: 'POST',
    params: { tenant_id: hasSession ? undefined : tenantId },
    body: JSON.stringify(body),
  });
}

export async function runReconciliation(
  body: ReconciliationRunRequest,
  tenantId?: string
): Promise<ReconciliationRunResponse> {
  const hasSession = hasCookieSession();
  return request<ReconciliationRunResponse>('/api/reconciliation/run', {
    method: 'POST',
    params: { tenant_id: hasSession ? undefined : tenantId },
    body: JSON.stringify(body),
  });
}

export async function getReconciliationStatus(
  params: { account_id?: string; limit?: number } = {},
  tenantId?: string
): Promise<ReconciliationStatusResponse> {
  const hasSession = hasCookieSession();
  return request<ReconciliationStatusResponse>('/api/reconciliation/status', {
    method: 'GET',
    params: {
      account_id: params.account_id,
      limit: params.limit ?? 20,
      tenant_id: hasSession ? undefined : tenantId,
    },
  });
}

export async function getReconciliationCoverage(
  params: { account_id?: string } = {},
  tenantId?: string
): Promise<ReconciliationCoverageResponse> {
  const hasSession = hasCookieSession();
  return request<ReconciliationCoverageResponse>('/api/reconciliation/coverage', {
    method: 'GET',
    params: {
      account_id: params.account_id,
      tenant_id: hasSession ? undefined : tenantId,
    },
  });
}

export async function getReconciliationSettings(
  accountId: string,
  tenantId?: string
): Promise<ReconciliationSettings> {
  const hasSession = hasCookieSession();
  return request<ReconciliationSettings>(`/api/reconciliation/settings/${accountId}`, {
    method: 'GET',
    params: { tenant_id: hasSession ? undefined : tenantId },
  });
}

export async function updateReconciliationSettings(
  accountId: string,
  body: ReconciliationSettingsUpdateRequest,
  tenantId?: string
): Promise<ReconciliationSettings> {
  const hasSession = hasCookieSession();
  return request<ReconciliationSettings>(`/api/reconciliation/settings/${accountId}`, {
    method: 'PUT',
    params: { tenant_id: hasSession ? undefined : tenantId },
    body: JSON.stringify(body),
  });
}

// ============================================
// Actions API (Step 5.5)
// ============================================

export async function getActions(
  filters: ActionsFilters = {},
  tenantId?: string
): Promise<PaginatedResponse<ActionListItem>> {
  const hasSession = hasCookieSession();
  const params: Record<string, string | number | boolean | undefined> = {
    action_type: filters.action_type,
    account_id: filters.account_id,
    region: filters.region,
    control_id: filters.control_id,
    resource_id: filters.resource_id,
    q: filters.q,
    ids: filters.ids?.join(','),
    status: filters.status,
    group_by: filters.group_by,
    include_orphans: filters.include_orphans,
    limit: filters.limit ?? 50,
    offset: filters.offset ?? 0,
    tenant_id: hasSession ? undefined : tenantId,
  };
  return request<PaginatedResponse<ActionListItem>>('/api/actions', { params });
}

export async function getAction(
  id: string,
  tenantId?: string
): Promise<ActionDetail> {
  const hasSession = hasCookieSession();
  const params: Record<string, string | undefined> = {
    tenant_id: hasSession ? undefined : tenantId,
  };
  return request<ActionDetail>(`/api/actions/${id}`, { params });
}

export async function getAttackPaths(
  filters: AttackPathsFilters = {},
  tenantId?: string
): Promise<AttackPathsListResponse> {
  const hasSession = hasCookieSession();
  const params: Record<string, string | number | undefined> = {
    account_id: filters.account_id,
    action_id: filters.action_id,
    owner_key: filters.owner_key,
    resource_id: filters.resource_id,
    status: filters.status,
    view: filters.view,
    limit: filters.limit ?? 50,
    offset: filters.offset ?? 0,
    tenant_id: hasSession ? undefined : tenantId,
  };
  return request<AttackPathsListResponse>('/api/actions/attack-paths', { params });
}

export async function getAttackPath(
  id: string,
  tenantId?: string
): Promise<ActionAttackPathDetail> {
  const hasSession = hasCookieSession();
  const params: Record<string, string | undefined> = {
    tenant_id: hasSession ? undefined : tenantId,
  };
  return request<ActionAttackPathDetail>(`/api/actions/attack-paths/${id}`, { params });
}

export async function patchAction(
  id: string,
  body: { status: 'in_progress' | 'resolved' | 'suppressed' },
  tenantId?: string
): Promise<ActionDetail> {
  const hasSession = hasCookieSession();
  return request<ActionDetail>(`/api/actions/${id}`, {
    method: 'PATCH',
    params: { tenant_id: hasSession ? undefined : tenantId },
    body: JSON.stringify(body),
  });
}

export async function triggerComputeActions(
  scope?: { account_id?: string; region?: string },
  tenantId?: string
): Promise<ComputeActionsResponse> {
  const hasSession = hasCookieSession();
  return request<ComputeActionsResponse>('/api/actions/compute', {
    method: 'POST',
    params: { tenant_id: hasSession ? undefined : tenantId },
    body: JSON.stringify(scope ?? {}),
  });
}

export async function getActionGroups(
  filters: {
    account_id?: string;
    region?: string;
    action_type?: string;
    limit?: number;
    offset?: number;
  } = {},
  tenantId?: string
): Promise<PaginatedResponse<ActionGroupListItem>> {
  const hasSession = hasCookieSession();
  const params: Record<string, string | number | boolean | undefined> = {
    account_id: filters.account_id,
    region: filters.region,
    action_type: filters.action_type,
    limit: filters.limit ?? 50,
    offset: filters.offset ?? 0,
    tenant_id: hasSession ? undefined : tenantId,
  };
  return request<PaginatedResponse<ActionGroupListItem>>('/api/action-groups', { params });
}

export async function getActionGroup(
  groupId: string,
  tenantId?: string
): Promise<ActionGroupDetail> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  return request<ActionGroupDetail>(`/api/action-groups/${groupId}`, {
    ...(params ? { params } : {}),
  });
}

export async function getActionGroupRuns(
  groupId: string,
  params: { limit?: number; offset?: number } = {},
  tenantId?: string
): Promise<PaginatedResponse<ActionGroupRunTimelineItem>> {
  const hasSession = hasCookieSession();
  const query: Record<string, string | number | boolean | undefined> = {
    limit: params.limit ?? 50,
    offset: params.offset ?? 0,
    tenant_id: hasSession ? undefined : tenantId,
  };
  return request<PaginatedResponse<ActionGroupRunTimelineItem>>(
    `/api/action-groups/${groupId}/runs`,
    {
      params: Object.fromEntries(
        Object.entries(query).filter(([, value]) => value !== undefined && value !== null && value !== '')
      ),
    }
  );
}

export async function getActionGroupRun(
  groupId: string,
  runId: string,
  tenantId?: string
): Promise<ActionGroupRunTimelineItem> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  return request<ActionGroupRunTimelineItem>(`/api/action-groups/${groupId}/runs/${runId}`, {
    ...(params ? { params } : {}),
  });
}

export async function createActionGroupBundleRun(
  groupId: string,
  body: {
    strategy_id?: string;
    strategy_inputs?: Record<string, unknown>;
    risk_acknowledged?: boolean;
    bucket_creation_acknowledged?: boolean;
    pr_bundle_variant?: LegacyPRBundleVariant;
  } = {},
  tenantId?: string
): Promise<ActionGroupBundleRunResponse> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  return request<ActionGroupBundleRunResponse>(`/api/action-groups/${groupId}/bundle-run`, {
    method: 'POST',
    body: JSON.stringify(body ?? {}),
    ...(params ? { params } : {}),
  });
}

// ============================================
// Users API
// ============================================

export interface UserListItem {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'member';
  created_at: string;
}

export async function getUsers(): Promise<UserListItem[]> {
  return request<UserListItem[]>('/api/users');
}

export async function inviteUser(email: string): Promise<{ message: string; email: string }> {
  return request<{ message: string; email: string }>('/api/users/invite', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

export async function deleteUser(userId: string): Promise<void> {
  return request<void>(`/api/users/${userId}`, {
    method: 'DELETE',
  });
}

export interface InviteInfo {
  email: string;
  tenant_name: string;
  inviter_name: string;
}

export async function getInviteInfo(token: string): Promise<InviteInfo> {
  return request<InviteInfo>('/api/users/accept-invite', {
    params: { token },
  });
}

// ============================================
// Exceptions API (Step 6.4)
// ============================================

export async function createException(
  data: CreateExceptionRequest,
  tenantId?: string
): Promise<Exception> {
  return request<Exception>('/api/exceptions', {
    method: 'POST',
    body: JSON.stringify(data),
    params: tenantId ? { tenant_id: tenantId } : {},
  });
}

export async function getExceptions(
  filters?: ExceptionsFilters,
  tenantId?: string
): Promise<PaginatedResponse<ExceptionListItem>> {
  return request<PaginatedResponse<ExceptionListItem>>('/api/exceptions', {
    params: { ...filters, tenant_id: tenantId },
  });
}

export async function getException(
  id: string,
  tenantId?: string
): Promise<Exception> {
  return request<Exception>(`/api/exceptions/${id}`, {
    params: tenantId ? { tenant_id: tenantId } : {},
  });
}

export async function revokeException(
  id: string,
  tenantId?: string
): Promise<void> {
  return request<void>(`/api/exceptions/${id}`, {
    method: 'DELETE',
    params: tenantId ? { tenant_id: tenantId } : {},
  });
}

export async function getAuditLog(filters: AuditLogFilters = {}): Promise<AuditLogListResponse> {
  const params: Record<string, string | number | undefined> = {
    actor_user_id: filters.actor_user_id,
    resource_type: filters.resource_type,
    resource_id: filters.resource_id,
    from_date: filters.from_date,
    to_date: filters.to_date,
    limit: filters.limit ?? 25,
    offset: filters.offset ?? 0,
  };
  return request<AuditLogListResponse>('/api/audit-log', { params });
}

// ============================================
// Remediation runs API (Step 7.2 + 8.4)
// ============================================

export interface RemediationPreview {
  compliant: boolean;
  message: string;
  will_apply: boolean;
  impact_summary?: string | null;
  before_state?: Record<string, unknown>;
  after_state?: Record<string, unknown>;
  diff_lines?: Array<{
    type: 'add' | 'remove' | 'unchanged';
    label: string;
    value: string;
  }>;
  resolution?: {
    strategy_id: string;
    profile_id: string;
    support_tier: 'deterministic_bundle' | 'review_required_bundle' | 'manual_guidance_only';
    resolved_inputs?: Record<string, unknown>;
    missing_inputs?: string[];
    missing_defaults?: string[];
    blocked_reasons?: string[];
    rejected_profiles?: Array<Record<string, unknown>>;
    finding_coverage?: Record<string, unknown>;
    preservation_summary?: Record<string, unknown>;
    decision_rationale?: string | null;
    decision_version?: string;
  } | null;
}

export interface RemediationRunCreated {
  id: string;
  action_id: string;
  mode: string;
  status: string;
  created_at: string;
  updated_at: string;
  manual_high_risk?: boolean;
  pre_execution_notice?: string | null;
  runbook_url?: string | null;
}

export type RemediationStrategyId = string;
export type LegacyPRBundleVariant = string;

export interface DependencyCheck {
  code: string;
  status: 'pass' | 'warn' | 'unknown' | 'fail';
  message: string;
}

export interface StrategyInputOption {
  value: string;
  label?: string;
  description?: string;
  impact_text?: string;
}

export interface StrategyInputVisibleWhen {
  field: string;
  equals: unknown;
}

export interface StrategyInputSchemaField {
  key: string;
  type: 'string' | 'string_array' | 'select' | 'boolean' | 'cidr' | 'number';
  required: boolean;
  description: string;
  enum?: string[];
  placeholder?: string;
  help_text?: string;
  default_value?: unknown;
  options?: StrategyInputOption[];
  visible_when?: StrategyInputVisibleWhen;
  impact_text?: string;
  group?: string;
  min?: number;
  max?: number;
  safe_default_value?: unknown;
  safe_default_label?: string;
}

export interface StrategyInputSchema {
  fields: StrategyInputSchemaField[];
}

export interface RemediationOptionContext {
  kms_key_options?: StrategyInputOption[];
  default_inputs?: Record<string, unknown>;
  [key: string]: unknown;
}

export type RemediationBlastRadius = 'account' | 'resource' | 'access_changing';

export interface RemediationOptionProfile {
  profile_id: string;
  support_tier: string;
  recommended?: boolean;
  requires_inputs?: boolean;
  supports_exception_flow?: boolean;
  exception_only?: boolean;
}

export interface RemediationOption {
  strategy_id: RemediationStrategyId;
  label: string;
  mode: 'pr_only' | 'direct_fix';
  risk_level: 'low' | 'medium' | 'high';
  recommended: boolean;
  requires_inputs: boolean;
  input_schema: StrategyInputSchema;
  dependency_checks: DependencyCheck[];
  warnings: string[];
  supports_exception_flow: boolean;
  exception_only: boolean;
  rollback_command?: string;
  estimated_resolution_time?: string;
  supports_immediate_reeval?: boolean;
  blast_radius?: RemediationBlastRadius;
  context?: RemediationOptionContext;
  profiles?: RemediationOptionProfile[];
  recommended_profile_id?: string | null;
  missing_defaults?: string[];
  blocked_reasons?: string[];
  preservation_summary?: Record<string, unknown>;
  decision_rationale?: string | null;
}

export interface TriggerActionReevaluationResponse {
  message: string;
  tenant_id: string;
  action_id: string;
  strategy_id: string | null;
  estimated_resolution_time: string;
  supports_immediate_reeval: boolean;
  scope: Record<string, string>;
  enqueued_jobs: number;
}

export interface ManualCompletionValidation {
  status: 'planned_not_implemented' | 'not_manual_only' | 'missing_required_evidence' | 'complete';
  detail: string;
  required_evidence_keys: string[];
  received_evidence_keys: string[];
  missing_evidence_keys: string[];
}

export interface ManualWorkflowStep {
  id: string;
  title: string;
  instructions: string;
}

export interface ManualWorkflowEvidenceRequirement {
  key: string;
  description: string;
  required: boolean;
}

export interface ManualWorkflowVerificationCriterion {
  id: string;
  description: string;
}

export interface ManualWorkflow {
  workflow_id: string;
  manual_only: boolean;
  title: string;
  summary: string;
  steps: ManualWorkflowStep[];
  required_evidence: ManualWorkflowEvidenceRequirement[];
  verification_criteria: ManualWorkflowVerificationCriterion[];
  completion_validation: ManualCompletionValidation;
}

export interface RemediationOptionsResponse {
  action_id: string;
  action_type: string;
  mode_options: ('pr_only' | 'direct_fix')[];
  strategies: RemediationOption[];
  recommendation: ActionRecommendation;
  manual_high_risk?: boolean;
  pre_execution_notice?: string | null;
  runbook_url?: string | null;
  manual_workflow?: ManualWorkflow | null;
}

export interface ManualWorkflowEvidenceItem {
  id: string;
  action_id: string;
  workflow_id: string;
  evidence_key: string;
  filename: string;
  content_type: string | null;
  size_bytes: number | null;
  status: string;
  note: string | null;
  uploaded_at: string | null;
  created_at: string;
}

export interface ManualWorkflowValidationResponse {
  action_id: string;
  action_type: string;
  manual_only: boolean;
  status: ManualCompletionValidation['status'];
  detail: string;
  required_evidence_keys: string[];
  received_evidence_keys: string[];
  missing_evidence_keys: string[];
}

export interface CreateGroupPrBundleRunRequest {
  action_type: string;
  account_id: string;
  status: 'open' | 'in_progress' | 'resolved' | 'suppressed';
  region?: string;
  region_is_null?: boolean;
  strategy_id?: RemediationStrategyId;
  strategy_inputs?: Record<string, unknown>;
  risk_acknowledged?: boolean;
  bucket_creation_acknowledged?: boolean;
  pr_bundle_variant?: LegacyPRBundleVariant;
  repo_target?: RepoTargetInput;
}

export interface RepoTargetInput {
  provider?: string;
  repository: string;
  base_branch: string;
  head_branch?: string;
  root_path?: string;
}

export interface RemediationRunListItem {
  id: string;
  action_id: string;
  mode: string;
  status: string;
  outcome: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  artifacts_summary: string | null;
  approved_by_user_id?: string | null;
}

export interface RemediationRunsListResponse {
  items: RemediationRunListItem[];
  total: number;
}

export interface RemediationArtifactLink {
  key: string;
  kind: string;
  label: string;
  description: string;
  href: string | null;
  executable: boolean;
  metadata: Record<string, unknown>;
}

export interface RemediationEvidencePointer {
  key: string;
  kind: string;
  label: string;
  description: string;
  href: string | null;
  metadata: Record<string, unknown>;
}

export interface RemediationClosureChecklistItem {
  id: string;
  title: string;
  status: string;
  detail: string;
  evidence_keys: string[];
}

export interface RemediationRunArtifactMetadata {
  implementation_artifacts: RemediationArtifactLink[];
  evidence_pointers: RemediationEvidencePointer[];
  closure_checklist: RemediationClosureChecklistItem[];
}

export interface RemediationRunDetail {
  id: string;
  action_id: string;
  mode: string;
  status: string;
  outcome: string | null;
  logs: string | null;
  artifacts: Record<string, unknown> | null;
  approved_by_user_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  action: {
    id: string;
    title: string;
    account_id: string;
    region: string | null;
    status?: string | null;
  } | null;
  artifact_metadata: RemediationRunArtifactMetadata;
}

export interface RemediationRunExecutionDetail {
  id: string;
  run_id: string;
  phase: 'plan' | 'apply';
  status: 'queued' | 'running' | 'awaiting_approval' | 'success' | 'failed' | 'cancelled';
  workspace_manifest: Record<string, unknown> | null;
  results: Record<string, unknown> | null;
  logs_ref: string | null;
  error_summary: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  source?: 'execution' | 'run_fallback';
  current_step?: string;
  progress_percent?: number;
  completed_steps?: number;
  total_steps?: number;
}

export interface ListRemediationRunsParams {
  action_id?: string;
  include_group_related?: boolean;
  control_id?: string;
  resource_id?: string;
  approved_by_user_id?: string;
  status?: string;
  mode?: string;
  limit?: number;
  offset?: number;
}

export async function getRemediationPreview(
  actionId: string,
  tenantId?: string,
  mode: 'direct_fix' | 'pr_only' = 'direct_fix',
  strategyId?: RemediationStrategyId,
  strategyInputs?: Record<string, unknown>
): Promise<RemediationPreview> {
  const hasSession = hasCookieSession();
  const params: Record<string, string> = {
    mode,
    ...(strategyId ? { strategy_id: strategyId } : {}),
    ...(strategyInputs ? { strategy_inputs: JSON.stringify(strategyInputs) } : {}),
    ...(hasSession ? {} : tenantId ? { tenant_id: tenantId } : {}),
  };
  return request<RemediationPreview>(`/api/actions/${actionId}/remediation-preview`, {
    params: Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ),
  });
}

export async function getRemediationOptions(
  actionId: string,
  tenantId?: string
): Promise<RemediationOptionsResponse> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  return request<RemediationOptionsResponse>(`/api/actions/${actionId}/remediation-options`, {
    ...(params ? { params } : {}),
  });
}

export async function triggerActionReevaluation(
  actionId: string,
  tenantId?: string,
  strategyId?: RemediationStrategyId
): Promise<TriggerActionReevaluationResponse> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  const body: Record<string, unknown> = {};
  if (strategyId) {
    body.strategy_id = strategyId;
  }
  return request<TriggerActionReevaluationResponse>(`/api/actions/${actionId}/trigger-reeval`, {
    method: 'POST',
    body: JSON.stringify(body),
    ...(params ? { params } : {}),
  });
}

export async function validateManualWorkflowEvidence(
  actionId: string,
  evidence: Record<string, unknown> | undefined,
  tenantId?: string
): Promise<ManualWorkflowValidationResponse> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  return request<ManualWorkflowValidationResponse>(`/api/actions/${actionId}/manual-workflow/validate`, {
    method: 'POST',
    body: JSON.stringify({ evidence: evidence ?? {} }),
    ...(params ? { params } : {}),
  });
}

export async function listManualWorkflowEvidence(
  actionId: string,
  tenantId?: string
): Promise<ManualWorkflowEvidenceItem[]> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  return request<ManualWorkflowEvidenceItem[]>(`/api/actions/${actionId}/manual-workflow/evidence`, {
    ...(params ? { params } : {}),
  });
}

export async function uploadManualWorkflowEvidence(
  actionId: string,
  evidenceKey: string,
  file: File,
  note?: string,
  tenantId?: string
): Promise<ManualWorkflowEvidenceItem> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  const form = new FormData();
  form.append('evidence_key', evidenceKey);
  form.append('file', file);
  if (note && note.trim()) {
    form.append('note', note.trim());
  }
  return request<ManualWorkflowEvidenceItem>(`/api/actions/${actionId}/manual-workflow/evidence/upload`, {
    method: 'POST',
    body: form,
    ...(params ? { params } : {}),
  });
}

export async function getManualWorkflowEvidenceDownloadUrl(
  actionId: string,
  evidenceId: string,
  tenantId?: string
): Promise<string> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  const data = await request<{ download_url: string }>(
    `/api/actions/${actionId}/manual-workflow/evidence/${evidenceId}/download`,
    { ...(params ? { params } : {}) }
  );
  return data.download_url;
}

export async function createRemediationRun(
  actionId: string,
  mode: 'pr_only' | 'direct_fix',
  tenantId?: string,
  strategyId?: RemediationStrategyId,
  strategyInputs?: Record<string, unknown>,
  riskAcknowledged = false,
  bucketCreationAcknowledged = false,
  prBundleVariant?: LegacyPRBundleVariant,
  repoTarget?: RepoTargetInput
): Promise<RemediationRunCreated> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  const body: Record<string, unknown> = { action_id: actionId, mode };
  if (strategyId) body.strategy_id = strategyId;
  if (strategyInputs) body.strategy_inputs = strategyInputs;
  if (riskAcknowledged) body.risk_acknowledged = true;
  if (bucketCreationAcknowledged) body.bucket_creation_acknowledged = true;
  if (prBundleVariant) body.pr_bundle_variant = prBundleVariant;
  if (repoTarget) body.repo_target = repoTarget;
  return request<RemediationRunCreated>('/api/remediation-runs', {
    method: 'POST',
    body: JSON.stringify(body),
    ...(params ? { params } : {}),
  });
}

export async function createGroupPrBundleRun(
  body: CreateGroupPrBundleRunRequest,
  tenantId?: string
): Promise<RemediationRunCreated> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  return request<RemediationRunCreated>('/api/remediation-runs/group-pr-bundle', {
    method: 'POST',
    body: JSON.stringify(body),
    ...(params ? { params } : {}),
  });
}

export async function listRemediationRuns(
  params: ListRemediationRunsParams = {},
  tenantId?: string
): Promise<RemediationRunsListResponse> {
  const hasSession = hasCookieSession();
  const query: Record<string, string | number | boolean | undefined> = {
    ...(hasSession ? {} : tenantId ? { tenant_id: tenantId } : {}),
    ...(params.action_id ? { action_id: params.action_id } : {}),
    ...(params.include_group_related !== undefined
      ? { include_group_related: params.include_group_related }
      : {}),
    ...(params.control_id ? { control_id: params.control_id } : {}),
    ...(params.resource_id ? { resource_id: params.resource_id } : {}),
    ...(params.approved_by_user_id ? { approved_by_user_id: params.approved_by_user_id } : {}),
    ...(params.status ? { status: params.status } : {}),
    ...(params.mode ? { mode: params.mode } : {}),
    limit: params.limit ?? 20,
    offset: params.offset ?? 0,
  };
  return request<RemediationRunsListResponse>('/api/remediation-runs', {
    params: Object.fromEntries(
      Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ),
  });
}

export async function getRemediationRun(
  runId: string,
  tenantId?: string
): Promise<RemediationRunDetail> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  return request<RemediationRunDetail>(`/api/remediation-runs/${runId}`, {
    ...(params ? { params } : {}),
  });
}

export async function getRemediationRunExecution(
  runId: string
): Promise<RemediationRunExecutionDetail> {
  return request<RemediationRunExecutionDetail>(`/api/remediation-runs/${runId}/execution`);
}

export async function cancelRemediationRun(
  runId: string,
  tenantId?: string
): Promise<RemediationRunDetail> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  return request<RemediationRunDetail>(`/api/remediation-runs/${runId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status: 'cancelled' }),
    ...(params ? { params } : {}),
  });
}

export interface ResendRemediationRunResponse {
  message: string;
}

export async function resendRemediationRun(
  runId: string,
  tenantId?: string
): Promise<ResendRemediationRunResponse> {
  const hasSession = hasCookieSession();
  const params = !hasSession && tenantId ? { tenant_id: tenantId } : undefined;
  return request<ResendRemediationRunResponse>(`/api/remediation-runs/${runId}/resend`, {
    method: 'POST',
    ...(params ? { params } : {}),
  });
}

// ============================================
// Root-key remediation orchestration API
// ============================================

const ROOT_KEY_CONTRACT_VERSION = '2026-03-02';

export interface RootKeyRunSnapshot {
  id: string;
  account_id: string;
  region: string | null;
  control_id: string;
  action_id: string;
  finding_id: string | null;
  state:
    | 'discovery'
    | 'migration'
    | 'validation'
    | 'disable_window'
    | 'delete_window'
    | 'needs_attention'
    | 'completed'
    | 'rolled_back'
    | 'failed';
  status: 'queued' | 'running' | 'waiting_for_user' | 'completed' | 'failed';
  strategy_id: string;
  mode: 'auto' | 'manual';
  run_correlation_id: string;
  retry_count: number;
  lock_version: number;
  rollback_reason: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RootKeyExternalTaskSnapshot {
  id: string;
  run_id: string;
  task_type: string;
  status: 'open' | 'completed' | 'failed' | 'cancelled';
  due_at: string | null;
  completed_at: string | null;
  assigned_to_user_id: string | null;
  retry_count: number;
  rollback_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface RootKeyDependencySnapshot {
  id: string;
  run_id: string;
  fingerprint_type: string;
  fingerprint_hash: string;
  status: string;
  unknown_dependency: boolean;
  unknown_reason: string | null;
  fingerprint_payload: Record<string, unknown> | Array<unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface RootKeyEventSnapshot {
  id: string;
  run_id: string;
  event_type: string;
  state: string;
  status: string;
  rollback_reason: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface RootKeyArtifactSnapshot {
  id: string;
  run_id: string;
  artifact_type: string;
  state: string;
  status: string;
  artifact_ref: string | null;
  artifact_sha256: string | null;
  redaction_applied: boolean;
  created_at: string;
  completed_at: string | null;
}

export interface RootKeyRunResponse {
  correlation_id: string;
  contract_version: string;
  idempotency_replayed: boolean;
  run: RootKeyRunSnapshot;
}

export interface RootKeyRunDetailResponse {
  correlation_id: string;
  contract_version: string;
  run: RootKeyRunSnapshot;
  external_tasks: RootKeyExternalTaskSnapshot[];
  dependencies: RootKeyDependencySnapshot[];
  events: RootKeyEventSnapshot[];
  artifacts: RootKeyArtifactSnapshot[];
  event_count: number;
  dependency_count: number;
  artifact_count: number;
}

export interface RootKeyExternalTaskCompleteResponse {
  correlation_id: string;
  contract_version: string;
  idempotency_replayed: boolean;
  run: RootKeyRunSnapshot;
  task: RootKeyExternalTaskSnapshot;
}

export interface RootKeyCreateRunRequest {
  action_id: string;
  finding_id?: string | null;
  strategy_id?: 'iam_root_key_disable' | 'iam_root_key_delete';
  mode?: 'auto' | 'manual';
  actor_metadata?: Record<string, unknown>;
}

interface RootKeyMutationOptions {
  tenantId?: string;
  idempotencyKey?: string;
  correlationId?: string;
}

interface RootKeyReadOptions {
  tenantId?: string;
  correlationId?: string;
}

function createIdempotencyKey(prefix: string): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}:${crypto.randomUUID()}`;
  }
  return `${prefix}:${Date.now()}:${Math.random().toString(16).slice(2)}`;
}

function rootKeyHeaders(
  options: { idempotencyKey?: string; correlationId?: string } = {}
): Record<string, string> {
  const headers: Record<string, string> = {
    'X-Root-Key-Contract-Version': ROOT_KEY_CONTRACT_VERSION,
  };
  if (options.idempotencyKey) {
    headers['Idempotency-Key'] = options.idempotencyKey;
  }
  if (options.correlationId) {
    headers['X-Correlation-Id'] = options.correlationId;
  }
  return headers;
}

function tenantScopedParams(tenantId?: string): Record<string, string> | undefined {
  const hasSession = hasCookieSession();
  if (hasSession || !tenantId) {
    return undefined;
  }
  return { tenant_id: tenantId };
}

export async function createRootKeyRemediationRun(
  body: RootKeyCreateRunRequest,
  options: RootKeyMutationOptions = {}
): Promise<RootKeyRunResponse> {
  return request<RootKeyRunResponse>('/api/root-key-remediation-runs', {
    method: 'POST',
    headers: rootKeyHeaders({
      idempotencyKey: options.idempotencyKey ?? createIdempotencyKey('root-key-create'),
      correlationId: options.correlationId,
    }),
    params: tenantScopedParams(options.tenantId),
    body: JSON.stringify({
      action_id: body.action_id,
      finding_id: body.finding_id ?? null,
      strategy_id: body.strategy_id ?? 'iam_root_key_disable',
      mode: body.mode ?? 'manual',
      ...(body.actor_metadata ? { actor_metadata: body.actor_metadata } : {}),
    }),
  });
}

export async function getRootKeyRemediationRun(
  runId: string,
  options: RootKeyReadOptions = {}
): Promise<RootKeyRunDetailResponse> {
  return request<RootKeyRunDetailResponse>(`/api/root-key-remediation-runs/${runId}`, {
    headers: rootKeyHeaders({ correlationId: options.correlationId }),
    params: tenantScopedParams(options.tenantId),
  });
}

async function mutateRootKeyRun(
  runId: string,
  transition: 'validate' | 'disable' | 'rollback' | 'delete',
  options: RootKeyMutationOptions = {},
  body?: Record<string, unknown>
): Promise<RootKeyRunResponse> {
  return request<RootKeyRunResponse>(`/api/root-key-remediation-runs/${runId}/${transition}`, {
    method: 'POST',
    headers: rootKeyHeaders({
      idempotencyKey: options.idempotencyKey ?? createIdempotencyKey(`root-key-${transition}`),
      correlationId: options.correlationId,
    }),
    params: tenantScopedParams(options.tenantId),
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
}

export async function validateRootKeyRemediationRun(
  runId: string,
  options: RootKeyMutationOptions = {}
): Promise<RootKeyRunResponse> {
  return mutateRootKeyRun(runId, 'validate', options);
}

export async function disableRootKeyRemediationRun(
  runId: string,
  options: RootKeyMutationOptions = {}
): Promise<RootKeyRunResponse> {
  return mutateRootKeyRun(runId, 'disable', options);
}

export async function rollbackRootKeyRemediationRun(
  runId: string,
  body: { reason?: string; actor_metadata?: Record<string, unknown> } = {},
  options: RootKeyMutationOptions = {}
): Promise<RootKeyRunResponse> {
  return mutateRootKeyRun(
    runId,
    'rollback',
    options,
    {
      ...(body.reason ? { reason: body.reason } : {}),
      ...(body.actor_metadata ? { actor_metadata: body.actor_metadata } : {}),
    },
  );
}

export async function deleteRootKeyRemediationRun(
  runId: string,
  options: RootKeyMutationOptions = {}
): Promise<RootKeyRunResponse> {
  return mutateRootKeyRun(runId, 'delete', options);
}

export async function completeRootKeyExternalTask(
  runId: string,
  taskId: string,
  body: { result?: Record<string, unknown> | Array<unknown>; actor_metadata?: Record<string, unknown> } = {},
  options: RootKeyMutationOptions = {}
): Promise<RootKeyExternalTaskCompleteResponse> {
  return request<RootKeyExternalTaskCompleteResponse>(
    `/api/root-key-remediation-runs/${runId}/external-tasks/${taskId}/complete`,
    {
      method: 'POST',
      headers: rootKeyHeaders({
        idempotencyKey: options.idempotencyKey ?? createIdempotencyKey('root-key-task-complete'),
        correlationId: options.correlationId,
      }),
      params: tenantScopedParams(options.tenantId),
      body: JSON.stringify({
        ...(body.result ? { result: body.result } : {}),
        ...(body.actor_metadata ? { actor_metadata: body.actor_metadata } : {}),
      }),
    }
  );
}

// ============================================
// Evidence exports API (Step 10.6)
// ============================================

export interface ExportCreatedResponse {
  id: string;
  status: string;
  created_at: string;
  message: string;
}

export interface ExportDetailResponse {
  id: string;
  status: string;
  pack_type?: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  download_url?: string | null;
  file_size_bytes?: number | null;
}

export interface ExportListItem {
  id: string;
  status: string;
  pack_type?: string;
  created_at: string;
  completed_at: string | null;
}

export type ExportPackType = 'evidence' | 'compliance';

export interface ExportsListResponse {
  items: ExportListItem[];
  total: number;
}

export async function createExport(body?: { pack_type?: ExportPackType }): Promise<ExportCreatedResponse> {
  return request<ExportCreatedResponse>('/api/exports', {
    method: 'POST',
    body: body?.pack_type ? JSON.stringify({ pack_type: body.pack_type }) : undefined,
  });
}

export async function getExport(exportId: string): Promise<ExportDetailResponse> {
  return request<ExportDetailResponse>(`/api/exports/${exportId}`);
}

export async function listExports(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<ExportsListResponse> {
  const query: Record<string, string | number | boolean | undefined> = {
    limit: params?.limit ?? 20,
    offset: params?.offset ?? 0,
    ...(params?.status ? { status: params.status } : {}),
  };
  return request<ExportsListResponse>('/api/exports', {
    params: Object.fromEntries(
      Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ),
  });
}

// ============================================
// Control mappings API (Step 12.3, 12.5)
// ============================================

export interface ControlMapping {
  id: string;
  control_id: string;
  framework_name: string;
  framework_control_code: string;
  control_title: string;
  description: string;
  created_at: string;
}

export interface ControlMappingListResponse {
  items: ControlMapping[];
  total: number;
}

export interface CreateControlMappingRequest {
  control_id: string;
  framework_name: string;
  framework_control_code: string;
  control_title: string;
  description: string;
}

export async function listControlMappings(params?: {
  control_id?: string;
  framework_name?: string;
  limit?: number;
  offset?: number;
}): Promise<ControlMappingListResponse> {
  const query: Record<string, string | number | boolean | undefined> = {
    limit: params?.limit ?? 100,
    offset: params?.offset ?? 0,
    ...(params?.control_id ? { control_id: params.control_id } : {}),
    ...(params?.framework_name ? { framework_name: params.framework_name } : {}),
  };
  return request<ControlMappingListResponse>('/api/control-mappings', {
    params: Object.fromEntries(
      Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ),
  });
}

export async function getControlMapping(id: string): Promise<ControlMapping> {
  return request<ControlMapping>(`/api/control-mappings/${id}`);
}

export async function createControlMapping(body: CreateControlMappingRequest): Promise<ControlMapping> {
  return request<ControlMapping>('/api/control-mappings', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ============================================
// Digest & Slack settings API (Step 11.3, 11.4, 11.5)
// ============================================

export interface DigestSettingsResponse {
  digest_enabled: boolean;
  digest_recipients: string | null;
}

export interface DigestSettingsUpdateRequest {
  digest_enabled?: boolean;
  digest_recipients?: string | null;
}

export interface SlackSettingsResponse {
  slack_webhook_configured: boolean;
  slack_digest_enabled: boolean;
}

export interface SlackSettingsUpdateRequest {
  slack_webhook_url?: string | null;
  slack_digest_enabled?: boolean;
}

export type IntegrationProvider = 'jira' | 'servicenow' | 'slack';

export interface IntegrationHealthResponse {
  status: string;
  credentials_valid?: boolean | null;
  project_valid?: boolean | null;
  issue_type_valid?: boolean | null;
  transition_map_valid?: boolean | null;
  webhook_registered?: boolean | null;
  signed_webhook_enabled?: boolean | null;
  webhook_mode?: string | null;
  last_validated_at?: string | null;
  last_validation_error?: string | null;
  last_inbound_at?: string | null;
  last_outbound_at?: string | null;
  last_provider_error?: string | null;
  last_provider_error_at?: string | null;
  details: Record<string, unknown>;
}

export interface IntegrationSettingsItemResponse {
  provider: IntegrationProvider;
  enabled: boolean;
  outbound_enabled: boolean;
  inbound_enabled: boolean;
  auto_create: boolean;
  reopen_on_regression: boolean;
  config: Record<string, unknown>;
  secret_configured: boolean;
  webhook_configured: boolean;
  health?: IntegrationHealthResponse | null;
}

export interface IntegrationSettingsListResponse {
  items: IntegrationSettingsItemResponse[];
}

export interface IntegrationSettingsUpdateRequest {
  enabled?: boolean;
  outbound_enabled?: boolean;
  inbound_enabled?: boolean;
  auto_create?: boolean;
  reopen_on_regression?: boolean;
  config?: Record<string, unknown>;
  secret_config?: Record<string, unknown>;
  clear_secret_config?: boolean;
}

export interface JiraUtilityResponse {
  provider: IntegrationProvider;
  message: string;
  item: IntegrationSettingsItemResponse;
  task_ids: string[];
  queued: number;
  failed_to_enqueue: number;
}

export interface GovernanceSettingsResponse {
  governance_notifications_enabled: boolean;
  governance_webhook_configured: boolean;
}

export interface GovernanceSettingsUpdateRequest {
  governance_notifications_enabled?: boolean;
  governance_webhook_url?: string | null;
}

export interface NotificationCenterItem {
  id: string;
  kind: string;
  source: string;
  severity: string;
  status: string;
  title: string;
  message: string;
  detail: string | null;
  progress: number | null;
  action_url: string | null;
  target_type: string | null;
  target_id: string | null;
  client_key?: string | null;
  created_at: string;
  updated_at: string | null;
  read_at: string | null;
  archived_at: string | null;
}

export interface NotificationCenterListResponse {
  items: NotificationCenterItem[];
  total: number;
  unread_total: number;
}

export interface NotificationJobUpsertRequest {
  status: string;
  title: string;
  message: string;
  severity?: string | null;
  detail?: string | null;
  progress?: number | null;
  action_url?: string | null;
  target_type?: string | null;
  target_id?: string | null;
}

export interface NotificationStateUpdateRequest {
  action: 'read' | 'unread' | 'archive' | 'mark_all_read';
  notification_ids?: string[];
}

export type SGAccessPathPreference =
  | 'close_public'
  | 'restrict_to_detected_public_ip'
  | 'restrict_to_approved_admin_cidr'
  | 'bastion_sg_reference'
  | 'ssm_only';

export type ConfigDeliveryMode = 'account_local_delivery' | 'centralized_delivery';
export type S3EncryptionMode = 'aws_managed' | 'customer_managed';

export interface RemediationCloudTrailSettingsResponse {
  default_bucket_name: string | null;
  default_kms_key_arn: string | null;
}

export interface RemediationConfigSettingsResponse {
  delivery_mode: ConfigDeliveryMode | null;
  default_bucket_name: string | null;
  default_kms_key_arn: string | null;
}

export interface RemediationS3AccessLogsSettingsResponse {
  default_target_bucket_name: string | null;
}

export interface RemediationS3EncryptionSettingsResponse {
  mode: S3EncryptionMode | null;
  kms_key_arn: string | null;
}

export interface RemediationSettingsResponse {
  sg_access_path_preference: SGAccessPathPreference | null;
  approved_admin_cidrs: string[];
  approved_bastion_security_group_ids: string[];
  cloudtrail: RemediationCloudTrailSettingsResponse;
  config: RemediationConfigSettingsResponse;
  s3_access_logs: RemediationS3AccessLogsSettingsResponse;
  s3_encryption: RemediationS3EncryptionSettingsResponse;
}

export interface RemediationSettingsUpdateRequest {
  sg_access_path_preference?: SGAccessPathPreference | null;
  approved_admin_cidrs?: string[];
  approved_bastion_security_group_ids?: string[];
  cloudtrail?: Partial<RemediationCloudTrailSettingsResponse> | null;
  config?: Partial<RemediationConfigSettingsResponse> | null;
  s3_access_logs?: Partial<RemediationS3AccessLogsSettingsResponse> | null;
  s3_encryption?: Partial<RemediationS3EncryptionSettingsResponse> | null;
}

export async function getDigestSettings(): Promise<DigestSettingsResponse> {
  return request<DigestSettingsResponse>('/api/users/me/digest-settings');
}

export async function patchDigestSettings(
  body: DigestSettingsUpdateRequest
): Promise<DigestSettingsResponse> {
  return request<DigestSettingsResponse>('/api/users/me/digest-settings', {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function getSlackSettings(): Promise<SlackSettingsResponse> {
  return request<SlackSettingsResponse>('/api/users/me/slack-settings');
}

export async function patchSlackSettings(
  body: SlackSettingsUpdateRequest
): Promise<SlackSettingsResponse> {
  return request<SlackSettingsResponse>('/api/users/me/slack-settings', {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function listIntegrationSettings(): Promise<IntegrationSettingsListResponse> {
  return request<IntegrationSettingsListResponse>('/api/integrations/settings');
}

export async function patchIntegrationSettings(
  provider: IntegrationProvider,
  body: IntegrationSettingsUpdateRequest,
): Promise<IntegrationSettingsItemResponse> {
  return request<IntegrationSettingsItemResponse>(`/api/integrations/settings/${provider}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function validateJiraIntegrationSettings(): Promise<JiraUtilityResponse> {
  return request<JiraUtilityResponse>('/api/integrations/settings/jira/validate', {
    method: 'POST',
  });
}

export async function syncJiraIntegrationWebhook(
  body: { rotate_secret?: boolean } = {},
): Promise<JiraUtilityResponse> {
  return request<JiraUtilityResponse>('/api/integrations/settings/jira/webhook/sync', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function runJiraCanarySync(
  body: { action_id?: string } = {},
): Promise<JiraUtilityResponse> {
  return request<JiraUtilityResponse>('/api/integrations/settings/jira/canary-sync', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getGovernanceSettings(): Promise<GovernanceSettingsResponse> {
  return request<GovernanceSettingsResponse>('/api/users/me/governance-settings');
}

export async function patchGovernanceSettings(
  body: GovernanceSettingsUpdateRequest,
): Promise<GovernanceSettingsResponse> {
  return request<GovernanceSettingsResponse>('/api/users/me/governance-settings', {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function getNotifications(
  params: { limit?: number; offset?: number; include_archived?: boolean } = {},
  signal?: AbortSignal,
): Promise<NotificationCenterListResponse> {
  return request<NotificationCenterListResponse>('/api/notifications', {
    params,
    signal,
  });
}

export async function upsertJobNotification(
  clientKey: string,
  body: NotificationJobUpsertRequest,
  signal?: AbortSignal,
): Promise<NotificationCenterItem> {
  return request<NotificationCenterItem>(`/api/notifications/jobs/${encodeURIComponent(clientKey)}`, {
    method: 'PUT',
    body: JSON.stringify(body),
    signal,
  });
}

export async function patchNotificationState(
  body: NotificationStateUpdateRequest,
): Promise<{ updated: number }> {
  return request<{ updated: number }>('/api/notifications/state', {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function getRemediationSettings(): Promise<RemediationSettingsResponse> {
  return request<RemediationSettingsResponse>('/api/users/me/remediation-settings');
}

export async function patchRemediationSettings(
  body: RemediationSettingsUpdateRequest,
): Promise<RemediationSettingsResponse> {
  return request<RemediationSettingsResponse>('/api/users/me/remediation-settings', {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

// ============================================
// Baseline report API (Step 13.3, 13.4)
// ============================================

export interface BaselineReportCreatedResponse {
  id: string;
  status: string;
  requested_at: string;
  message: string;
}

export interface BaselineReportDetailResponse {
  id: string;
  status: string;
  requested_at: string;
  completed_at: string | null;
  file_size_bytes: number | null;
  download_url: string | null;
  outcome: string | null;
}

export interface BaselineReportListItem {
  id: string;
  status: string;
  requested_at: string;
  completed_at: string | null;
}

export interface BaselineReportListResponse {
  items: BaselineReportListItem[];
  total: number;
}

export async function createBaselineReport(body?: {
  account_ids?: string[];
}): Promise<BaselineReportCreatedResponse> {
  const options: RequestOptions = { method: 'POST' };
  if (body?.account_ids?.length) {
    options.body = JSON.stringify({ account_ids: body.account_ids });
  }
  return request<BaselineReportCreatedResponse>('/api/baseline-report', options);
}

export async function getBaselineReport(reportId: string): Promise<BaselineReportDetailResponse> {
  return request<BaselineReportDetailResponse>(`/api/baseline-report/${reportId}`);
}

export async function listBaselineReports(params?: {
  limit?: number;
  offset?: number;
}): Promise<BaselineReportListResponse> {
  const query: Record<string, string | number | boolean | undefined> = {
    limit: params?.limit ?? 20,
    offset: params?.offset ?? 0,
  };
  return request<BaselineReportListResponse>('/api/baseline-report', {
    params: Object.fromEntries(
      Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ),
  });
}

// ============================================
// Baseline report view data (in-app viewer — Option B)
// ============================================

export interface BaselineReportSummary {
  total_finding_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  informational_count: number;
  open_count: number;
  resolved_count: number;
  narrative: string;
  report_date: string;
  generated_at: string;
  account_count: number | null;
  region_count: number | null;
  soc2_impacted_cc_ids?: string[] | null;
  soc2_impacted_finding_count?: number | null;
}

export interface BaselineTopRiskItem {
  title: string;
  severity: string;
  account_id: string;
  status: string;
  resource_id: string | null;
  control_id: string | null;
  region: string | null;
  recommendation_text: string | null;
  business_impact?: string | null;
  action_id?: string | null;
  action_status?: string | null;
  action_type?: string | null;
  recommended_mode?: 'direct_fix' | 'pr_only' | null;
  remediation_readiness?: string | null;
  why_now?: string | null;
  soc2_cc_ids?: string[] | null;
  link_to_app: string | null;
}

export interface BaselineRecommendationItem {
  text: string;
  control_id: string | null;
  soc2_cc_ids?: string[] | null;
}

export interface BaselineNextActionItem {
  action_id: string | null;
  title: string;
  control_id: string | null;
  severity: string;
  account_id: string | null;
  region: string | null;
  action_status: string | null;
  why_now: string;
  recommended_mode: 'direct_fix' | 'pr_only';
  blast_radius: string;
  fix_path: string;
  owner: string | null;
  due_by: string | null;
  readiness: string;
  cta_label: string;
  cta_href: string | null;
}

export interface BaselineChangeDelta {
  compared_to_report_at: string | null;
  new_open_count: number;
  regressed_count: number;
  stale_open_count: number;
  closed_count: number;
  summary: string;
}

export interface BaselineConfidenceGapItem {
  category: 'access_denied' | 'partial_data' | 'api_error' | 'telemetry_gap';
  count: number;
  detail: string;
  affected_control_ids: string[] | null;
}

export interface BaselineClosureProofItem {
  finding_id: string;
  title: string;
  control_id: string | null;
  account_id: string | null;
  region: string | null;
  resolved_at: string | null;
  action_id: string | null;
  remediation_run_id: string | null;
  evidence_note: string;
}

export interface BaselineReportViewData {
  summary: BaselineReportSummary;
  top_risks: BaselineTopRiskItem[];
  recommendations: BaselineRecommendationItem[];
  next_actions: BaselineNextActionItem[];
  change_delta: BaselineChangeDelta | null;
  confidence_gaps: BaselineConfidenceGapItem[];
  closure_proof: BaselineClosureProofItem[];
  tenant_name: string | null;
  appendix_findings?: BaselineTopRiskItem[] | null;
}

export async function getBaselineReportData(reportId: string): Promise<BaselineReportViewData> {
  return request<BaselineReportViewData>(`/api/baseline-report/${reportId}/data`);
}

// ============================================
// SaaS admin dashboard API
// ============================================

export interface SaasSystemHealth {
  window_hours: number;
  queue_configured: boolean;
  export_bucket_configured: boolean;
  support_bucket_configured: boolean;
  failing_remediation_runs_24h: number;
  failing_baseline_reports_24h: number;
  failing_exports_24h: number;
  remediation_failure_rate_24h: number;
  baseline_report_failure_rate_24h: number;
  export_failure_rate_24h: number;
  worker_failure_rate_24h: number;
  p95_queue_lag_ms_24h: number | null;
  control_plane_drop_rate_24h: number;
}

export interface SaasTenantListItem {
  tenant_id: string;
  tenant_name: string;
  created_at: string;
  users_count: number;
  aws_accounts_count: number;
  open_findings_count: number;
  open_actions_count: number;
  last_activity_at: string | null;
  has_connected_accounts: boolean;
  ingestion_stale: boolean;
  digest_enabled: boolean;
  slack_configured: boolean;
}

export interface SaasTenantOverview {
  tenant_id: string;
  tenant_name: string;
  created_at: string;
  users_count: number;
  accounts_by_status: Record<string, number>;
  actions_by_status: Record<string, number>;
  findings_by_severity: Record<string, number>;
  findings_trend: Record<string, number>;
  digest_enabled: boolean;
  slack_configured: boolean;
}

export interface SaasTenantUser {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at: string;
  onboarding_completed_at: string | null;
}

export interface SaasTenantAccount {
  id: string;
  account_id: string;
  regions: string[];
  status: string;
  last_validated_at: string | null;
  created_at: string;
  ai_live_lookup_enabled: boolean;
  ai_live_lookup_scope: string | null;
  ai_live_lookup_enabled_at: string | null;
  ai_live_lookup_enabled_by_user_id: string | null;
  ai_live_lookup_notes: string | null;
}

export interface HelpAssistantLiveLookupCandidateAccount {
  account_id: string;
  label: string;
}

export interface HelpAssistantLiveLookupObservation {
  title: string;
  summary: string;
  details: string[];
}

export interface HelpAssistantLiveLookup {
  status: string;
  account_id: string | null;
  scope: string | null;
  message: string | null;
  confirmation_required: boolean;
  candidate_accounts: HelpAssistantLiveLookupCandidateAccount[];
  observations: HelpAssistantLiveLookupObservation[];
  observed_at: string | null;
}

export interface SaasFindingItem {
  id: string;
  finding_id: string;
  account_id: string;
  region: string;
  source: string;
  severity_label: string;
  status: string;
  title: string;
  description: string | null;
  resource_id: string | null;
  resource_type: string | null;
  control_id: string | null;
  standard_name: string | null;
  first_observed_at: string | null;
  last_observed_at: string | null;
  updated_at: string | null;
  created_at: string;
}

export interface SaasActionItem {
  id: string;
  action_type: string;
  target_id: string;
  account_id: string;
  region: string | null;
  priority: number;
  status: string;
  title: string;
  description: string | null;
  control_id: string | null;
  resource_id: string | null;
  updated_at: string | null;
  created_at: string | null;
}

export interface SaasRemediationRunItem {
  id: string;
  action_id: string;
  mode: string;
  status: string;
  outcome: string | null;
  artifacts: Record<string, unknown> | null;
  approved_by_email: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface SaasExportItem {
  id: string;
  status: string;
  pack_type: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  file_size_bytes: number | null;
}

export interface SaasBaselineReportItem {
  id: string;
  status: string;
  requested_at: string;
  completed_at: string | null;
  outcome: string | null;
  file_size_bytes: number | null;
}

export interface SupportNote {
  id: string;
  tenant_id: string;
  created_by_user_id: string | null;
  created_by_email: string | null;
  body: string;
  created_at: string;
}

export interface SupportFile {
  id: string;
  tenant_id?: string;
  filename: string;
  content_type: string | null;
  size_bytes: number | null;
  status?: string;
  visible_to_tenant?: boolean;
  message: string | null;
  created_at: string;
  uploaded_at: string | null;
}

export interface InitiateSupportFileResponse {
  id: string;
  upload_url: string;
  method: 'PUT';
  required_headers: Record<string, string>;
}

export interface HelpArticle {
  id: string;
  slug: string;
  title: string;
  summary: string;
  body: string;
  audience: string;
  published: boolean;
  sort_order: number;
  tags: string[];
  related_routes: string[];
  created_at: string;
  updated_at: string | null;
}

export interface HelpSearchResult extends HelpArticle {
  score: number;
  snippet: string;
}

export interface HelpCaseAttachment {
  id: string;
  message_id: string;
  filename: string;
  content_type: string | null;
  size_bytes: number | null;
  internal_only: boolean;
  created_at: string;
  uploaded_at: string | null;
}

export interface HelpCaseMessage {
  id: string;
  role: string;
  body: string;
  internal_only: boolean;
  created_by_user_id: string | null;
  created_by_email: string | null;
  created_at: string;
  attachments: HelpCaseAttachment[];
}

export interface HelpCase {
  id: string;
  tenant_id: string;
  requester_user_id: string;
  requester_email: string | null;
  assigned_saas_admin_user_id: string | null;
  assigned_saas_admin_email: string | null;
  subject: string;
  category: string;
  priority: string;
  status: string;
  source: string;
  current_path: string | null;
  referenced_entities: Array<{ type: string; id: string; label: string }>;
  first_response_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  last_message_at: string | null;
  created_at: string;
  updated_at: string | null;
  sla_state: string;
  messages: HelpCaseMessage[];
}

export interface HelpAssistantResponse {
  thread_id: string;
  interaction_id: string;
  answer: string;
  confidence: string;
  suggested_case: boolean;
  citations: Array<{ slug: string; title: string; summary: string }>;
  follow_up_questions: string[];
  context_gaps: string[];
  escalated_case_id: string | null;
  live_lookup: HelpAssistantLiveLookup | null;
}

export interface HelpAssistantTurn {
  interaction_id: string;
  question: string;
  answer: string;
  confidence: string;
  suggested_case: boolean;
  citations: Array<{ slug: string; title: string; summary: string }>;
  follow_up_questions: string[];
  context_gaps: string[];
  helpful: boolean | null;
  feedback_text: string | null;
  created_at: string;
  escalated_case_id: string | null;
  live_lookup: HelpAssistantLiveLookup | null;
}

export interface HelpAssistantThread {
  thread_id: string;
  current_path: string | null;
  turns: HelpAssistantTurn[];
}

export interface ControlPlaneSloResponse {
  window_hours: number;
  tenant_id: string | null;
  total_events: number;
  success_events: number;
  dropped_events: number;
  duplicate_hits: number;
  p95_end_to_end_lag_ms: number | null;
  p99_end_to_end_lag_ms: number | null;
  p95_resolution_freshness_ms: number | null;
  p95_cloudtrail_delivery_lag_ms: number | null;
  p95_queue_lag_ms: number | null;
  p95_handler_latency_ms: number | null;
  drop_rate: number;
  duplicate_rate: number;
}

export interface ControlPlaneShadowSummaryResponse {
  tenant_id: string;
  total_rows: number;
  open_count: number;
  resolved_count: number;
  soft_resolved_count: number;
  controls: Record<string, number>;
}

export interface ControlPlaneReconcileJob {
  id: string;
  tenant_id: string;
  job_type: string;
  status: string;
  payload_summary: Record<string, unknown> | null;
  submitted_at: string;
  submitted_by: string | null;
  error_message: string | null;
}

export interface ControlPlaneReconcileJobsResponse {
  items: ControlPlaneReconcileJob[];
  total: number;
}

export interface ReconcileEnqueueResponse {
  enqueued: number;
  job_ids: string[];
  status: string;
}

export async function getSaasSystemHealth(): Promise<SaasSystemHealth> {
  return request<SaasSystemHealth>('/api/saas/system-health');
}

export async function getSaasTenants(params?: {
  query?: string;
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<SaasTenantListItem>> {
  return request<PaginatedResponse<SaasTenantListItem>>('/api/saas/tenants', {
    params: {
      query: params?.query,
      limit: params?.limit ?? 20,
      offset: params?.offset ?? 0,
    },
  });
}

export async function getSaasTenantOverview(tenantId: string): Promise<SaasTenantOverview> {
  return request<SaasTenantOverview>(`/api/saas/tenants/${tenantId}`);
}

export async function getSaasTenantUsers(tenantId: string): Promise<SaasTenantUser[]> {
  return request<SaasTenantUser[]>(`/api/saas/tenants/${tenantId}/users`);
}

export async function getSaasTenantAccounts(tenantId: string): Promise<SaasTenantAccount[]> {
  return request<SaasTenantAccount[]>(`/api/saas/tenants/${tenantId}/aws-accounts`);
}

export async function getSaasTenantFindings(
  tenantId: string,
  filters: FindingsFilters = {}
): Promise<PaginatedResponse<SaasFindingItem>> {
  return request<PaginatedResponse<SaasFindingItem>>(`/api/saas/tenants/${tenantId}/findings`, {
    params: {
      account_id: filters.account_id,
      region: filters.region,
      severity: filters.severity,
      status: filters.status,
      source: filters.source,
      limit: filters.limit ?? 50,
      offset: filters.offset ?? 0,
    },
  });
}

export async function getSaasTenantActions(
  tenantId: string,
  filters: ActionsFilters = {}
): Promise<PaginatedResponse<SaasActionItem>> {
  return request<PaginatedResponse<SaasActionItem>>(`/api/saas/tenants/${tenantId}/actions`, {
    params: {
      account_id: filters.account_id,
      region: filters.region,
      status: filters.status,
      limit: filters.limit ?? 50,
      offset: filters.offset ?? 0,
    },
  });
}

export async function getSaasTenantRemediationRuns(
  tenantId: string,
  params?: { limit?: number; offset?: number }
): Promise<PaginatedResponse<SaasRemediationRunItem>> {
  return request<PaginatedResponse<SaasRemediationRunItem>>(`/api/saas/tenants/${tenantId}/remediation-runs`, {
    params: {
      limit: params?.limit ?? 50,
      offset: params?.offset ?? 0,
    },
  });
}

export async function getSaasTenantExports(tenantId: string): Promise<SaasExportItem[]> {
  return request<SaasExportItem[]>(`/api/saas/tenants/${tenantId}/exports`);
}

export async function getSaasTenantBaselineReports(tenantId: string): Promise<SaasBaselineReportItem[]> {
  return request<SaasBaselineReportItem[]>(`/api/saas/tenants/${tenantId}/baseline-reports`);
}

export async function getControlPlaneSlo(params: {
  tenant_id?: string;
  hours?: number;
}): Promise<ControlPlaneSloResponse> {
  return request<ControlPlaneSloResponse>('/api/saas/control-plane/slo', {
    params: {
      tenant_id: params.tenant_id,
      hours: params.hours ?? 24,
    },
  });
}

export async function getControlPlaneShadowSummary(params: {
  tenant_id: string;
}): Promise<ControlPlaneShadowSummaryResponse> {
  return request<ControlPlaneShadowSummaryResponse>('/api/saas/control-plane/shadow-summary', {
    params: { tenant_id: params.tenant_id },
  });
}

export interface ControlPlaneCanonicalFindingRef {
  id: string;
  source: string;
  status_raw: string;
  status_normalized: string;
  severity_label?: string | null;
  title?: string | null;
  updated_at?: string | null;
}

export interface ControlPlaneShadowCompareItem {
  fingerprint: string;
  account_id: string;
  region: string;
  resource_id?: string | null;
  resource_type?: string | null;
  control_id?: string | null;
  shadow_status: string;
  shadow_status_normalized: string;
  status_reason?: string | null;
  evidence_ref?: Record<string, unknown> | null;
  last_observed_event_time?: string | null;
  last_evaluated_at?: string | null;
  canonical?: ControlPlaneCanonicalFindingRef | null;
  is_mismatch: boolean;
}

export interface ControlPlaneShadowCompareResponse {
  tenant_id: string;
  total: number;
  items: ControlPlaneShadowCompareItem[];
}

export interface ControlPlaneShadowRef {
  fingerprint: string;
  status_raw: string;
  status_normalized: string;
  status_reason?: string | null;
  evidence_ref?: Record<string, unknown> | null;
  last_observed_event_time?: string | null;
  last_evaluated_at?: string | null;
}

export interface ControlPlaneCompareItem {
  comparison_key: string;
  account_id: string;
  region: string;
  resource_id?: string | null;
  resource_type?: string | null;
  control_id?: string | null;
  shadow?: ControlPlaneShadowRef | null;
  live?: ControlPlaneCanonicalFindingRef | null;
  is_mismatch: boolean;
}

export interface ControlPlaneCompareResponse {
  tenant_id: string;
  basis: 'live' | 'shadow';
  total: number;
  items: ControlPlaneCompareItem[];
}

export async function getControlPlaneShadowCompare(params: {
  tenant_id: string;
  control_id?: string;
  limit?: number;
  offset?: number;
}): Promise<ControlPlaneShadowCompareResponse> {
  return request<ControlPlaneShadowCompareResponse>('/api/saas/control-plane/shadow-compare', {
    params: {
      tenant_id: params.tenant_id,
      control_id: params.control_id ?? undefined,
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
    },
  });
}

export async function getControlPlaneCompare(params: {
  tenant_id: string;
  basis?: 'live' | 'shadow';
  only_with_shadow?: boolean;
  only_mismatches?: boolean;
  limit?: number;
  offset?: number;
}): Promise<ControlPlaneCompareResponse> {
  return request<ControlPlaneCompareResponse>('/api/saas/control-plane/compare', {
    params: {
      tenant_id: params.tenant_id,
      basis: params.basis ?? 'live',
      only_with_shadow: params.only_with_shadow ?? undefined,
      only_mismatches: params.only_mismatches ?? undefined,
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
    },
  });
}

export async function getControlPlaneReconcileJobs(params: {
  tenant_id: string;
  limit?: number;
}): Promise<ControlPlaneReconcileJobsResponse> {
  return request<ControlPlaneReconcileJobsResponse>('/api/saas/control-plane/reconcile-jobs', {
    params: {
      tenant_id: params.tenant_id,
      limit: params.limit ?? 50,
    },
  });
}

export async function enqueueReconcileRecentlyTouched(body: {
  tenant_id: string;
  lookback_minutes?: number;
  services?: string[];
  max_resources?: number;
}): Promise<ReconcileEnqueueResponse> {
  return request<ReconcileEnqueueResponse>('/api/saas/control-plane/reconcile/recently-touched', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function enqueueReconcileInventoryGlobal(body: {
  tenant_id: string;
  account_ids?: string[];
  regions?: string[];
  services?: string[];
  max_resources?: number;
}): Promise<ReconcileEnqueueResponse> {
  return request<ReconcileEnqueueResponse>('/api/saas/control-plane/reconcile/global', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function enqueueReconcileInventoryShard(body: {
  shards: Array<{
    tenant_id: string;
    account_id: string;
    region: string;
    service: string;
    resource_ids?: string[];
    sweep_mode?: 'targeted' | 'global';
    max_resources?: number;
  }>;
}): Promise<ReconcileEnqueueResponse> {
  return request<ReconcileEnqueueResponse>('/api/saas/control-plane/reconcile/shard', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getSupportNotes(
  tenantId: string,
  params?: { limit?: number; offset?: number }
): Promise<SupportNote[]> {
  return request<SupportNote[]>(`/api/saas/tenants/${tenantId}/notes`, {
    params: {
      limit: params?.limit ?? 50,
      offset: params?.offset ?? 0,
    },
  });
}

export async function createSupportNote(
  tenantId: string,
  body: { body: string }
): Promise<SupportNote> {
  return request<SupportNote>(`/api/saas/tenants/${tenantId}/notes`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getSaasSupportFiles(
  tenantId: string,
  params?: { limit?: number; offset?: number }
): Promise<SupportFile[]> {
  return request<SupportFile[]>(`/api/saas/tenants/${tenantId}/files`, {
    params: {
      limit: params?.limit ?? 100,
      offset: params?.offset ?? 0,
    },
  });
}

export async function initiateSupportFileUpload(
  tenantId: string,
  body: {
    filename: string;
    content_type?: string | null;
    message?: string | null;
    visible_to_tenant?: boolean;
  }
): Promise<InitiateSupportFileResponse> {
  return request<InitiateSupportFileResponse>(`/api/saas/tenants/${tenantId}/files/initiate`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function finalizeSupportFileUpload(
  tenantId: string,
  fileId: string,
  body?: { size_bytes?: number | null }
): Promise<SupportFile> {
  return request<SupportFile>(`/api/saas/tenants/${tenantId}/files/${fileId}/finalize`, {
    method: 'POST',
    body: JSON.stringify(body ?? {}),
  });
}

export async function uploadSupportFileDirect(
  tenantId: string,
  file: File,
  message?: string,
  visibleToTenant: boolean = true
): Promise<SupportFile> {
  const form = new FormData();
  form.append('file', file);
  if (message) form.append('message', message);
  form.append('visible_to_tenant', String(visibleToTenant));

  const headers = new Headers();
  applyCsrfHeader(headers, 'POST');

  const response = await fetch(getApiUrl(`/api/saas/tenants/${tenantId}/files/upload`), {
    method: 'POST',
    headers,
    credentials: 'include',
    body: form,
  });

  if (!response.ok) {
    if (response.status === 401 && typeof window !== 'undefined') {
      window.location.href = SESSION_EXPIRED_PATH;
    }
    let errorData: ApiError;
    try {
      const json = await response.json();
      errorData = {
        error: typeof json.error === 'string' ? json.error : 'Request failed',
        detail: json.detail,
        status: response.status,
      };
    } catch {
      errorData = {
        error: response.statusText || 'Request failed',
        status: response.status,
      };
    }
    throw errorData;
  }

  return response.json();
}

export async function getTenantSupportFiles(): Promise<SupportFile[]> {
  return request<SupportFile[]>('/api/support-files');
}

export async function getSupportFileDownloadUrl(fileId: string): Promise<{ download_url: string }> {
  return request<{ download_url: string }>(`/api/support-files/${fileId}/download`);
}

export async function listHelpArticles(): Promise<{ items: HelpArticle[]; total: number }> {
  return request<{ items: HelpArticle[]; total: number }>('/api/help/articles');
}

export async function getHelpArticle(slug: string): Promise<HelpArticle> {
  return request<HelpArticle>(`/api/help/articles/${slug}`);
}

export async function searchHelpArticles(params: {
  q: string;
  current_path?: string;
}): Promise<{ items: HelpSearchResult[]; total: number }> {
  return request<{ items: HelpSearchResult[]; total: number }>('/api/help/search', {
    params: {
      q: params.q,
      current_path: params.current_path,
    },
  });
}

export async function queryHelpAssistant(body: {
  question: string;
  thread_id?: string | null;
  current_path?: string | null;
  account_id?: string | null;
  action_id?: string | null;
  finding_id?: string | null;
  request_human?: boolean;
  confirm_live_lookup?: boolean;
}): Promise<HelpAssistantResponse> {
  return request<HelpAssistantResponse>('/api/help/assistant/query', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function updateSaasTenantAccountAiLiveLookup(
  tenantId: string,
  accountId: string,
  body: { enabled: boolean; notes?: string | null },
): Promise<SaasTenantAccount> {
  return request<SaasTenantAccount>(`/api/saas/tenants/${tenantId}/aws-accounts/${accountId}/ai-live-lookup`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function sendHelpAssistantFeedback(
  interactionId: string,
  body: { helpful?: boolean | null; feedback_text?: string | null },
): Promise<HelpAssistantResponse> {
  return request<HelpAssistantResponse>(`/api/help/assistant/${interactionId}/feedback`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function approveHelpAssistantCase(interactionId: string): Promise<HelpAssistantResponse> {
  return request<HelpAssistantResponse>(`/api/help/assistant/${interactionId}/approve-case`, {
    method: 'POST',
  });
}

export async function getHelpAssistantThread(threadId: string): Promise<HelpAssistantThread> {
  return request<HelpAssistantThread>(`/api/help/assistant/threads/${threadId}`);
}

export async function listHelpCases(): Promise<{ items: HelpCase[]; total: number }> {
  return request<{ items: HelpCase[]; total: number }>('/api/help/cases');
}

export async function createHelpCase(body: {
  subject: string;
  category: string;
  priority?: string;
  body: string;
  source?: string;
  current_path?: string | null;
  account_id?: string | null;
  action_id?: string | null;
  finding_id?: string | null;
}): Promise<HelpCase> {
  return request<HelpCase>('/api/help/cases', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getHelpCase(caseId: string): Promise<HelpCase> {
  return request<HelpCase>(`/api/help/cases/${caseId}`);
}

export async function replyToHelpCase(caseId: string, body: { body: string }): Promise<HelpCase> {
  return request<HelpCase>(`/api/help/cases/${caseId}/messages`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function uploadHelpCaseAttachmentDirect(
  caseId: string,
  messageId: string,
  file: File,
): Promise<HelpCaseAttachment> {
  const form = new FormData();
  form.append('message_id', messageId);
  form.append('file', file);
  const headers = new Headers();
  applyCsrfHeader(headers, 'POST');
  const response = await fetch(getApiUrl(`/api/help/cases/${caseId}/attachments/upload`), {
    method: 'POST',
    headers,
    credentials: 'include',
    body: form,
  });
  if (!response.ok) {
    throw await buildApiError(response);
  }
  return response.json();
}

export async function getHelpCaseAttachmentDownloadUrl(
  caseId: string,
  attachmentId: string,
): Promise<{ download_url: string }> {
  return request<{ download_url: string }>(`/api/help/cases/${caseId}/attachments/${attachmentId}/download`);
}

export async function listAdminHelpCases(params?: {
  status?: string;
  priority?: string;
  tenant_id?: string;
  assigned_saas_admin_user_id?: string;
  sla_state?: string;
}): Promise<{ items: HelpCase[]; total: number }> {
  return request<{ items: HelpCase[]; total: number }>('/api/saas/help/cases', {
    params: params ?? {},
  });
}

export async function getAdminHelpCase(caseId: string): Promise<HelpCase> {
  return request<HelpCase>(`/api/saas/help/cases/${caseId}`);
}

export async function updateAdminHelpCase(
  caseId: string,
  body: { status?: string; priority?: string; assigned_saas_admin_user_id?: string | null },
): Promise<HelpCase> {
  return request<HelpCase>(`/api/saas/help/cases/${caseId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function replyToAdminHelpCase(
  caseId: string,
  body: { body: string },
  internalOnly: boolean = false,
): Promise<HelpCase> {
  return request<HelpCase>(`/api/saas/help/cases/${caseId}/messages`, {
    method: 'POST',
    params: { internal_only: internalOnly },
    body: JSON.stringify(body),
  });
}

export async function uploadAdminHelpCaseAttachmentDirect(
  caseId: string,
  messageId: string,
  file: File,
  internalOnly: boolean = false,
): Promise<HelpCaseAttachment> {
  const form = new FormData();
  form.append('message_id', messageId);
  form.append('file', file);
  form.append('internal_only', String(internalOnly));
  const headers = new Headers();
  applyCsrfHeader(headers, 'POST');
  const response = await fetch(getApiUrl(`/api/saas/help/cases/${caseId}/attachments/upload`), {
    method: 'POST',
    headers,
    credentials: 'include',
    body: form,
  });
  if (!response.ok) {
    throw await buildApiError(response);
  }
  return response.json();
}

export async function getAdminHelpCaseAttachmentDownloadUrl(
  caseId: string,
  attachmentId: string,
): Promise<{ download_url: string }> {
  return request<{ download_url: string }>(`/api/saas/help/cases/${caseId}/attachments/${attachmentId}/download`);
}

// ============================================
// Utility functions
// ============================================

export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'error' in error &&
    'status' in error
  );
}

/** Normalize API error detail/error to a displayable string (never return object) */
function errorValueToString(value: unknown): string {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) {
    const messages = value
      .map((item) => (item && typeof item === 'object' && 'msg' in item ? String(item.msg) : null))
      .filter(Boolean);
    return messages.length ? messages.join('; ') : JSON.stringify(value);
  }
  if (typeof value === 'object' && value !== null) {
    const obj = value as Record<string, unknown>;
    if (typeof obj.detail === 'string' && obj.detail) return obj.detail;
    if (typeof obj.error === 'string' && obj.error) return obj.error;
    if (typeof obj.message === 'string' && obj.message) return obj.message;
    if ('msg' in obj) return String(obj.msg);
    return JSON.stringify(value);
  }
  return String(value);
}

export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    const msg = errorValueToString(error.detail) || errorValueToString(error.error);
    return msg || 'Request failed';
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
}

async function buildApiError(response: Response): Promise<ApiError> {
  if (response.status === 401 && typeof window !== 'undefined') {
    window.location.href = SESSION_EXPIRED_PATH;
  }
  try {
    const json = await response.json();
    return {
      error: typeof json.error === 'string' ? json.error : response.statusText || 'Request failed',
      detail: json.detail,
      status: response.status,
    };
  } catch {
    return {
      error: response.statusText || 'Request failed',
      status: response.status,
    };
  }
}

// ============================================
// Account Management API (Profile, Password, Verification)
// ============================================

export interface UpdateMeRequest {
  name?: string;
  phone_number?: string;
}

export interface UpdateMeResponse {
  user: {
    id: string;
    email: string;
    name: string;
    role: string;
    phone_number: string | null;
    phone_verified: boolean;
    email_verified: boolean;
    mfa_enabled?: boolean;
    mfa_method?: 'email' | 'phone' | null;
  };
}

export async function updateMe(body: UpdateMeRequest): Promise<UpdateMeResponse> {
  return request<UpdateMeResponse>('/api/users/me', {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteMe(): Promise<void> {
  return request<void>('/api/users/me', {
    method: 'DELETE',
  });
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

export async function changePassword(body: ChangePasswordRequest): Promise<void> {
  return request<void>('/api/auth/password', {
    method: 'PUT',
    body: JSON.stringify(body),
  });
}

export interface SendVerificationRequest {
  verification_type: 'email' | 'phone';
}

export interface SendVerificationResponse {
  message: string;
  debug_code?: string | null;
}

export async function sendVerification(body: SendVerificationRequest): Promise<SendVerificationResponse> {
  return request<SendVerificationResponse>('/api/auth/verify/send', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export interface ConfirmVerificationRequest {
  verification_type: 'email' | 'phone';
  code: string;
}

export async function confirmVerification(body: ConfirmVerificationRequest): Promise<void> {
  return request<void>('/api/auth/verify/confirm', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export interface ResendEmailVerificationRequest {
  resend_ticket: string;
}

export interface FirebaseVerificationDelivery {
  custom_token: string;
  continue_url: string;
}

export interface ResendEmailVerificationResponse {
  message: string;
  resend_ticket: string;
  firebase_delivery: FirebaseVerificationDelivery;
}

export async function resendEmailVerification(
  body: ResendEmailVerificationRequest
): Promise<ResendEmailVerificationResponse> {
  return request<ResendEmailVerificationResponse>('/api/auth/verify/resend', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export interface FirebaseSyncVerificationRequest {
  email?: string;
  sync_token: string;
}

export interface FirebaseSyncVerificationResponse {
  verified: boolean;
}

export async function firebaseSyncEmailVerification(
  body: FirebaseSyncVerificationRequest
): Promise<FirebaseSyncVerificationResponse> {
  return request<FirebaseSyncVerificationResponse>('/api/auth/verify/firebase-sync', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export interface MfaSettingsResponse {
  mfa_enabled: boolean;
  mfa_method: 'email' | 'phone' | null;
  email_verified: boolean;
  phone_verified: boolean;
  phone_number: string | null;
}

export interface UpdateMfaSettingsRequest {
  mfa_enabled: boolean;
  mfa_method?: 'email' | 'phone' | null;
}

export async function getMfaSettings(): Promise<MfaSettingsResponse> {
  return request<MfaSettingsResponse>('/api/auth/mfa/settings');
}

export async function patchMfaSettings(body: UpdateMfaSettingsRequest): Promise<MfaSettingsResponse> {
  return request<MfaSettingsResponse>('/api/auth/mfa/settings', {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function forgotPassword(body: ForgotPasswordRequest): Promise<{ message: string }> {
  return request<{ message: string }>('/api/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function resetPassword(body: ResetPasswordRequest): Promise<{ message: string }> {
  return request<{ message: string }>('/api/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
