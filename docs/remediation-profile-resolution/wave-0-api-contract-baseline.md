# Wave 0 API Contract Baseline

> Scope date: 2026-03-14
>
> Status: Current state - code-derived baseline
>
> This file documents the currently shipped remediation API surface only. It is intentionally descriptive, not aspirational. Planned remediation-profile work lives in [the remediation-profile-resolution spec](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/README.md) and [the implementation plan](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/implementation-plan.md); those planned changes are not treated here as active contract.

Related docs:

- [Remediation safety model](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-safety-model.md)
- [Root-key safe remediation technical spec](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/root-key-safe-remediation-spec.md)

## Shared current-state notes

- For `GET /api/actions/*` read surfaces, tenant resolution goes through `resolve_tenant_id(...)`: authenticated callers use `current_user.tenant_id`; unauthenticated callers only get `tenant_id` query fallback when `settings.is_local` is true. This is current compatibility behavior, not a generic production auth contract.
- `POST /api/remediation-runs` and `POST /api/remediation-runs/group-pr-bundle` do not accept `tenant_id`; they are always scoped to `current_user.tenant_id`.
- `POST /api/action-groups/{group_id}/bundle-run` is also auth-only and tenant-scoped from the authenticated user.
- `/api/root-key-remediation-runs` does not use `resolve_tenant_id`; every route in that family requires authentication and feature flags, and mutating routes require `Idempotency-Key`.
- Source code is authoritative. The docs above explain intent and safety goals, but the shipped contract is defined by the router and helper files linked below.

## 1. `GET /api/actions/{id}/remediation-options`

**Purpose**

List the currently available remediation modes and strategy rows for one action, including dependency checks, warning text, recommendation metadata, and root-key warning fields.

**Auth / tenant expectations**

- Uses `get_optional_user`.
- Tenant comes from bearer auth when present.
- `tenant_id` query fallback is only available in local/dev through `resolve_tenant_id(...)`.
- `400` for invalid `action_id`.
- `404` when the action is not found in tenant scope.

**Required request fields**

- Path: `action_id`

**Additive optional fields already supported**

- Query: `tenant_id`

**Important response fields**

- Top-level:
  - `action_id`
  - `action_type`
  - `mode_options`
  - `strategies[]`
  - `recommendation`
  - `manual_high_risk`
  - `pre_execution_notice`
  - `runbook_url`
- `strategies[]` rows currently expose:
  - `strategy_id`
  - `label`
  - `mode`
  - `risk_level`
  - `recommended`
  - `requires_inputs`
  - `input_schema`
  - `dependency_checks[]`
  - `warnings[]`
  - `supports_exception_flow`
  - `exception_only`
  - `impact_text`
  - `rollback_command`
  - `estimated_resolution_time`
  - `supports_immediate_reeval`
  - `blast_radius`
  - `context`
- `recommendation` is additive and includes:
  - `mode`
  - `default_mode`
  - `advisory`
  - `enforced_by_policy`
  - `rationale`
  - `matrix_position`
  - `evidence`

**Known compatibility constraints visible in code**

- `mode_options` comes from the strategy registry when strategies exist. If no strategies exist, current fallback is `["pr_only"]` plus `direct_fix` only when the runtime says that action type supports direct-fix.
- `strategy_id` is still the public compatibility key. Strategy-mapped actions still expose `strategies[]` even though some create routes may reject missing `strategy_id`.
- Current "strategy optional" compatibility is intentionally limited to `enable_security_hub` and `enable_guardduty`.
- Dependency checks in this endpoint are computed with empty `strategy_inputs` (`{}`). Input-dependent validation can still change later at run creation time once real `strategy_inputs` are supplied.
- Runtime `context` is only populated for hardcoded strategy IDs:
  - `s3_bucket_block_public_access_standard`
  - `s3_migrate_cloudfront_oac_private`
  - `iam_root_key_delete`
  - `s3_bucket_encryption_kms`
  - `config_enable_account_local_delivery`
  - `config_enable_centralized_delivery`
  - `cloudtrail_enable_guided`
- For root-key actions, `manual_high_risk`, `pre_execution_notice`, and `runbook_url` are keyed only from `action.action_type == "iam_root_access_key_absent"`.
- The additive `recommendation` payload does not grant execution permission by itself. The create endpoints still enforce mode support, strategy validation, risk checks, and root/manual guards independently.

**Exact source files that currently define behavior**

- [backend/routers/actions.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/routers/actions.py)
- [backend/services/remediation_strategy.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_strategy.py)
- [backend/services/remediation_risk.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_risk.py)
- [backend/services/remediation_runtime_checks.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_runtime_checks.py)
- [backend/services/action_recommendation.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/action_recommendation.py)
- [backend/services/root_credentials_workflow.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/root_credentials_workflow.py)
- [tests/test_remediation_runs_api.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_remediation_runs_api.py)
- [tests/test_phase3_p1_8_recommendation_mode.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_phase3_p1_8_recommendation_mode.py)

## 2. `GET /api/actions/{id}/remediation-preview`

**Purpose**

Return a preview object for one action. In current code this serves two distinct roles:

- direct-fix pre-check and preview bridge
- informational state simulation for selected `pr_only` strategies

**Auth / tenant expectations**

- Uses `get_optional_user`.
- Tenant resolution is the same `resolve_tenant_id(...)` path as `remediation-options`.
- `400` for invalid `action_id`.
- `404` when the action is not found in tenant scope.

**Required request fields**

- Path: `action_id`

**Additive optional fields already supported**

- Query: `mode`
  - defaults to `direct_fix`
  - accepted values are `direct_fix` and `pr_only`
- Query: `strategy_id`
- Query: `strategy_inputs`
  - current contract is a JSON object string, not repeated query keys
- Query: `tenant_id`

**Important response fields**

- `compliant`
- `message`
- `will_apply`
- `impact_summary`
- `before_state`
- `after_state`
- `diff_lines[]`

**Known compatibility constraints visible in code**

- This route returns `200` for many non-happy-path cases instead of raising a structured `4xx`:
  - action type does not support direct-fix
  - direct-fix runtime module is not packaged in this API deployment
  - AWS account row is missing
  - WriteRole is missing
  - STS assume-role fails
  - preview bridge raises an unexpected exception
  - `strategy_inputs` is invalid for `mode=direct_fix`
- `mode=pr_only` is explicitly accepted today and returns an informational preview rather than an error.
- `strategy_inputs` JSON parse failures are ignored for `mode=pr_only`, but surfaced as a message for `mode=direct_fix`.
- State simulation is only implemented for these strategy IDs:
  - `sg_restrict_public_ports_guided`
  - `s3_enforce_ssl_strict_deny`
  - `s3_enforce_ssl_with_principal_exemptions`
  - `config_enable_centralized_delivery`
  - `config_enable_account_local_delivery`
- If no state simulation exists, the current baseline response falls back to `{}` / `[]` unless the direct-fix preview bridge returns richer before/after data.
- The route description says direct-fix preview "requires WriteRole", but current code does not require WriteRole for the `pr_only` informational path.

**Exact source files that currently define behavior**

- [backend/routers/actions.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/routers/actions.py)
- [backend/services/remediation_strategy.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_strategy.py)
- [backend/services/direct_fix_bridge.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/direct_fix_bridge.py)
- [backend/workers/services/direct_fix.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/services/direct_fix.py)
- [tests/test_remediation_runs_api.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_remediation_runs_api.py)

## 3. `POST /api/remediation-runs`

**Purpose**

Create one remediation run row for one action and enqueue the generic remediation worker for either `pr_only` or `direct_fix`.

**Auth / tenant expectations**

- Uses `get_current_user`.
- Tenant is always `current_user.tenant_id`.
- There is no `tenant_id` request override.
- `401` when not authenticated.

**Required request fields**

- Body:
  - `action_id`
  - `mode`

**Additive optional fields already supported**

- Body: `strategy_id`
- Body: `strategy_inputs`
- Body: `risk_acknowledged`
- Body: `pr_bundle_variant`
  - deprecated but still accepted for compatibility
- Body: `repo_target`
  - `provider`
  - `repository`
  - `base_branch`
  - `head_branch`
  - `root_path`

**Important response fields**

- `id`
- `action_id`
- `mode`
- `status`
- `created_at`
- `updated_at`
- `manual_high_risk`
- `pre_execution_notice`
- `runbook_url`

**Known compatibility constraints visible in code**

- Create-time validation is stricter than `remediation-options` for strategy-backed actions:
  - `strategy_id` is required for strategy-mapped actions except the current compatibility exceptions `enable_security_hub` and `enable_guardduty`
  - selected strategy must exist for the action type and match the requested `mode`
  - `strategy_inputs` must pass schema validation
- Legacy `pr_bundle_variant` is still supported and mapped server-side to `strategy_id` when possible. If both are supplied and conflict, the request is rejected.
- Exception-only strategies are rejected with `400` and an `exception_flow` payload derived from `strategy_inputs`.
- Risk enforcement matches the remediation safety model:
  - failing dependency checks reject the request
  - `warn` / `unknown` checks require `risk_acknowledged=true`
  - rejection payloads currently include `risk_snapshot`
- Direct-fix creation adds additional gates:
  - direct-fix runtime module must be available in this API deployment
  - action type must be in the runtime-supported direct-fix set
  - tenant account row must exist
  - `role_write_arn` must exist
  - permission probe must not return a hard failure
- Creating the run is the approval act:
  - `approved_by_user_id` is stamped for both `direct_fix` and `pr_only`
  - direct-fix creation also stamps `artifacts.direct_fix_approval`
- Duplicate and rate-limit behavior is already part of the contract:
  - active `pending|running|awaiting_approval` runs block duplicates with `409`
  - non-PR identical requests are blocked for 30 seconds
  - PR-only requests are capped at 6 total and 3 identical submissions per 20-minute window
  - the request signature currently includes `mode`, `selected_strategy`, normalized `strategy_inputs`, `pr_bundle_variant`, and `repo_target`
- Root-key generic runs still go through this route today for bundle generation and persistence:
  - current code adds `manual_high_risk` marker evidence and notice fields
  - later SaaS executor endpoints separately reject those runs from automated SaaS execution
- Current enqueue ordering matters:
  - the `RemediationRun` row is committed before SQS enqueue
  - if `send_message` fails, the API returns `503`
  - the current route does not mark the run failed on enqueue failure, so a persisted pending row can remain behind

**Exact source files that currently define behavior**

- [backend/routers/remediation_runs.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/routers/remediation_runs.py)
- [backend/services/remediation_strategy.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_strategy.py)
- [backend/services/remediation_risk.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_risk.py)
- [backend/services/remediation_runtime_checks.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_runtime_checks.py)
- [backend/services/direct_fix_bridge.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/direct_fix_bridge.py)
- [backend/services/direct_fix_approval.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/direct_fix_approval.py)
- [backend/services/root_credentials_workflow.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/root_credentials_workflow.py)
- [backend/utils/sqs.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/utils/sqs.py)
- [docs/remediation-safety-model.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-safety-model.md)
- [tests/test_remediation_runs_api.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_remediation_runs_api.py)

## 4. `POST /api/remediation-runs/group-pr-bundle`

**Purpose**

Create one `pr_only` remediation run for the current execution-group filter and enqueue a combined grouped PR bundle.

**Auth / tenant expectations**

- Uses `get_current_user`.
- Tenant is always `current_user.tenant_id`.
- There is no `tenant_id` request override.
- `401` when not authenticated.

**Required request fields**

- Body:
  - `action_type`
  - `account_id`
  - `status`
  - either `region`, or `region_is_null=true`

**Additive optional fields already supported**

- Body: `region_is_null`
- Body: `strategy_id`
- Body: `strategy_inputs`
- Body: `risk_acknowledged`
- Body: `pr_bundle_variant`
  - deprecated but still accepted for compatibility
- Body: `repo_target`
  - `provider`
  - `repository`
  - `base_branch`
  - `head_branch`
  - `root_path`

**Important response fields**

- `id`
- `action_id`
  - current response returns the representative action ID, not the full group membership
- `mode`
- `status`
- `created_at`
- `updated_at`
- `manual_high_risk`
- `pre_execution_notice`
- `runbook_url`

**Known compatibility constraints visible in code**

- Current filter contract is exact:
  - `action_type`
  - `account_id`
  - `status`
  - exact `region`, or SQL `region IS NULL` when `region_is_null=true`
- The request model currently allows `status` values `open`, `in_progress`, `resolved`, and `suppressed`. The route does not narrow that list further.
- The route builds the action set by query, then uses the highest-priority row as the representative action and anchor `action_id`.
- Risk evaluation, root-key notice logic, and runtime signals are all computed from that representative action only. Current code does not resolve risk per grouped action.
- Current persistence model is still one `RemediationRun` row with `artifacts.group_bundle`:
  - `group_key`
  - `action_type`
  - `account_id`
  - `region`
  - `status`
  - `action_count`
  - `action_ids`
- `group_action_ids` are forwarded into the SQS payload, but they are not surfaced back in the create response.
- Duplicate protection is narrower than the single-run route:
  - it blocks only when there is already a pending grouped run with the same `group_key` and same normalized `repo_target`
  - it does not apply the single-run 30-second duplicate check or the 20-minute PR bundle rate limits
- The same strategy-required, legacy-variant, exception-only, and risk-ack rules from single-run creation are enforced here.
- Enqueue ordering matches the single-run route:
  - the run row is committed before SQS enqueue
  - if enqueue fails, the API returns `503`
  - the current route leaves the persisted grouped run pending rather than marking it failed

**Exact source files that currently define behavior**

- [backend/routers/remediation_runs.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/routers/remediation_runs.py)
- [backend/services/remediation_strategy.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_strategy.py)
- [backend/services/remediation_risk.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_risk.py)
- [backend/services/remediation_runtime_checks.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_runtime_checks.py)
- [backend/services/root_credentials_workflow.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/root_credentials_workflow.py)
- [backend/utils/sqs.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/utils/sqs.py)
- [tests/test_remediation_runs_api.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_remediation_runs_api.py)

## 5. `POST /api/action-groups/{group_id}/bundle-run`

**Purpose**

Create the legacy grouped bundle path that persists both an `ActionGroupRun` row and a representative `RemediationRun` row, issues a reporting token, and enqueues the same generic remediation worker.

**Auth / tenant expectations**

- Uses `get_current_user`.
- Group lookup is scoped to `current_user.tenant_id`.
- There is no `tenant_id` request override.
- `401` when not authenticated.

**Required request fields**

- Path: `group_id`
- Body: none required

**Additive optional fields already supported**

- Body may be omitted entirely.
- If a body is sent, current fields are:
  - `strategy_id`
  - `strategy_inputs`
  - `risk_acknowledged`
  - `pr_bundle_variant`

**Important response fields**

- `group_run_id`
- `remediation_run_id`
- `reporting_token`
- `reporting_callback_url`
- `status`

**Known compatibility constraints visible in code**

- This route currently diverges materially from `POST /api/remediation-runs/group-pr-bundle`.
- Current code validates only:
  - ingest queue configured
  - `group_id` is a UUID
  - action group exists in tenant scope
  - action group has at least one member
- Current code does not validate:
  - `strategy_id` exists for the group action type
  - strategy/mode compatibility
  - `strategy_inputs` schema
  - exception-only strategy selection
  - dependency check failures
  - `risk_acknowledged` necessity
  - root/manual-high-risk marker or runbook notice behavior
  - `repo_target` support
- Body omission is a real compatibility behavior: the route defaults to an empty body and still creates a run.
- The route anchors the grouped remediation run to the highest-priority group member as the representative action.
- `artifacts.group_bundle` includes extra reporting metadata not present in `/api/remediation-runs/group-pr-bundle`:
  - `group_id`
  - `group_key`
  - `group_run_id`
  - `reporting.callback_url`
  - `reporting.token`
  - `reporting.reporting_source`
- The route also issues and stores a JWT reporting token scoped to `tenant_id`, `group_run_id`, `group_id`, and `allowed_action_ids`.
- Enqueue failure behavior is different from the `/api/remediation-runs*` create routes:
  - rows are created first
  - if enqueue fails, current code marks `ActionGroupRun.status=failed` and `RemediationRun.status=failed`
  - the API still returns `503`

**Exact source files that currently define behavior**

- [backend/routers/action_groups.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/routers/action_groups.py)
- [backend/services/bundle_reporting_tokens.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/bundle_reporting_tokens.py)
- [backend/utils/sqs.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/utils/sqs.py)

## 6. `/api/root-key-remediation-runs`

**Purpose**

This is the dedicated execution-authority family for `IAM.4` root-key remediation (`iam_root_access_key_absent`). It is state-machine-backed and separate from the generic remediation-run create routes.

**Auth / tenant expectations**

- Every route in this family requires authentication in current code.
- There is no `tenant_id` query fallback.
- Whole-family availability is gated by feature flags:
  - API disabled -> `404 feature_disabled`
- Mutating routes also fail closed on kill switch:
  - `409 kill_switch_enabled`
- Current code does not enforce a separate admin-role check on these routes; the hard gate is authentication plus tenant scoping plus state-machine validation.

**Required request fields**

- `POST /api/root-key-remediation-runs`
  - Header: `Idempotency-Key`
  - Body: `action_id`
- `GET /api/root-key-remediation-runs/{id}`
  - Path: `run_id`
- `GET /api/root-key-remediation-runs/ops/metrics`
  - no body
- Mutating transition routes:
  - Header: `Idempotency-Key`
  - Path: `run_id`
- `POST /api/root-key-remediation-runs/{id}/external-tasks/{task_id}/complete`
  - Header: `Idempotency-Key`
  - Path: `run_id`
  - Path: `task_id`

**Additive optional fields already supported**

- All routes:
  - Header: `X-Correlation-Id`
  - Header: `X-Root-Key-Contract-Version`
- All mutating routes:
  - Header: `X-Operator-Override-Reason`
- `POST /api/root-key-remediation-runs`
  - Body: `finding_id`
  - Body: `strategy_id`
    - defaults to `iam_root_key_disable`
  - Body: `mode`
    - defaults to `manual`
    - current accepted values are only `auto` and `manual`
  - Body: `actor_metadata`
- `POST /api/root-key-remediation-runs/{id}/rollback`
  - Body: `reason`
  - Body: `actor_metadata`
- `POST /api/root-key-remediation-runs/{id}/pause`
  - Body: `reason`
  - Body: `actor_metadata`
- `POST /api/root-key-remediation-runs/{id}/resume`
  - Body: `reason`
  - Body: `actor_metadata`
- `POST /api/root-key-remediation-runs/{id}/external-tasks/{task_id}/complete`
  - Body: `result`
  - Body: `actor_metadata`

**Important response fields**

- Success and error envelopes both include:
  - `correlation_id`
  - `contract_version`
    - current constant is `2026-03-02`
- Mutating success payloads include:
  - `idempotency_replayed`
  - `run`
- `run` snapshot currently exposes:
  - `id`
  - `account_id`
  - `region`
  - `control_id`
  - `action_id`
  - `finding_id`
  - `state`
  - `status`
  - `strategy_id`
  - `mode`
  - `run_correlation_id`
  - `retry_count`
  - `lock_version`
  - `rollback_reason`
  - timestamps
- `GET /api/root-key-remediation-runs/{id}` also returns:
  - `external_tasks[]`
  - `dependencies[]`
  - `events[]`
  - `artifacts[]`
  - `event_count`
  - `dependency_count`
  - `artifact_count`
- `GET /api/root-key-remediation-runs/ops/metrics` returns:
  - `auto_success_rate`
  - `rollback_rate`
  - `needs_attention_rate`
  - `closure_pass_rate`
  - `mean_time_to_detect_unknown_dependency_seconds`
  - `unknown_dependency_sample_size`

**Known compatibility constraints visible in code**

- This family is the only current execution authority for root-key lifecycle transitions. The generic remediation-run APIs still exist for bundle-generation-style root flows, but state-machine execution authority lives here.
- `X-Root-Key-Contract-Version` is optional today. When supplied and mismatched, the request is rejected with `400 unsupported_contract_version`.
- Every mutating route requires `Idempotency-Key`, capped at 128 characters.
- Create-route validation is currently:
  - action must exist in tenant scope
  - action type must be exactly `iam_root_access_key_absent`
  - `strategy_id` must be one of `iam_root_key_disable` or `iam_root_key_delete`
  - `mode` must be `auto` or `manual`
  - optional `finding_id` is checked only for tenant/account scope, not for explicit linkage back to the chosen action
- Auto mode can still be blocked by flags or rollout:
  - `auto_mode_disabled`
  - canary gating with optional operator override
- When discovery is enabled, create can auto-transition immediately:
  - safe discovery -> `migration`
  - unknown dependency, partial data, or discovery failure -> `needs_attention`
- `disable` behavior is conditional:
  - when executor/closure runtime is enabled, it runs through `RootKeyRemediationExecutorWorker`
  - otherwise it falls back to direct state-machine transition
- `delete` behavior is stricter:
  - if executor runtime is disabled, current code fails closed with `503 executor_unavailable`
- Pause/resume is an active contract:
  - while paused, other transition routes and external-task completion fail with `409 run_paused`
  - resume fails with `409 run_not_paused` or `409 pause_context_missing` when the prior active state cannot be reconstructed
- External-task completion appends an idempotent event and redacts secret-like keys from `result` and actor metadata before persistence.

**Exact source files that currently define behavior**

- [backend/routers/root_key_remediation_runs.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/routers/root_key_remediation_runs.py)
- [backend/services/root_key_remediation_state_machine.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/root_key_remediation_state_machine.py)
- [backend/services/root_key_remediation_executor_worker.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/root_key_remediation_executor_worker.py)
- [backend/services/root_key_usage_discovery.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/root_key_usage_discovery.py)
- [backend/services/root_key_rollout_controls.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/root_key_rollout_controls.py)
- [backend/services/root_key_remediation_store.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/root_key_remediation_store.py)
- [tests/test_root_key_remediation_runs_api.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_root_key_remediation_runs_api.py)

## Current-state ambiguities to preserve deliberately

- The two grouped PR-bundle entry points are not equivalent today:
  - `/api/remediation-runs/group-pr-bundle` enforces strategy and risk safety
  - `/api/action-groups/{group_id}/bundle-run` currently does not
- Queue failure handling already differs across create routes:
  - `/api/remediation-runs` and `/api/remediation-runs/group-pr-bundle` can leave committed pending runs behind on `503`
  - `/api/action-groups/{group_id}/bundle-run` marks the persisted rows failed before returning `503`
- `GET /api/actions/{id}/remediation-preview` mixes "preview" and "informational simulation" semantics and returns `200` for many operational failures. Any migration that wants stricter status codes is a contract change, not a refactor.
- Root-key create accepts an optional `finding_id`, but the current validation only proves tenant/account scope, not action-to-finding linkage.

## Coverage check

This baseline covers every requested current surface:

- `GET /api/actions/{id}/remediation-options`
- `GET /api/actions/{id}/remediation-preview`
- `POST /api/remediation-runs`
- `POST /api/remediation-runs/group-pr-bundle`
- `POST /api/action-groups/{group_id}/bundle-run`
- `/api/root-key-remediation-runs`
