# Wave 0 API Contract Baseline

> Scope date: 2026-03-14
>
> This source baseline captures the current shipped remediation API surface that later remediation-profile-resolution waves must preserve.
>
> Note: the local `codex/rem-profile-w0-*` refs did not contain committed baseline markdown files at integration time. This baseline was reconstructed from the current code paths during Wave 0 integration.

Consolidated in:

- [Wave 0 contract lock](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/wave-0-contract-lock.md)

Code sources reviewed:

- [backend/routers/actions.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/routers/actions.py)
- [backend/routers/remediation_runs.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/routers/remediation_runs.py)
- [backend/routers/action_groups.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/routers/action_groups.py)

## Current Generic Remediation Surface

### `GET /api/actions/{id}/remediation-options`

- Request surface:
  - path `action_id`
  - optional query `tenant_id` for non-auth access paths
- Response surface:
  - top level: `action_id`, `action_type`, `mode_options`, `strategies[]`, `recommendation`, `manual_high_risk`, `pre_execution_notice`, `runbook_url`
  - each `strategies[]` item currently exposes:
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
- Locked current behavior:
  - response is still `strategy`-centric; there is no `profile_id`, `profiles[]`, `recommended_profile_id`, `missing_defaults`, `blocked_reasons`, or `decision_rationale`
  - `manual_high_risk`, `pre_execution_notice`, and `runbook_url` are the current root-credentials warning surface for generic remediation options

### `GET /api/actions/{id}/remediation-preview`

- Request surface:
  - path `action_id`
  - query `mode` with current values `direct_fix | pr_only` and default `direct_fix`
  - optional query `strategy_id`
  - optional query `strategy_inputs`, encoded as a JSON object string
  - optional query `tenant_id`
- Response surface:
  - `compliant`
  - `message`
  - `will_apply`
  - `impact_summary`
  - `before_state`
  - `after_state`
  - `diff_lines`
- Locked current behavior:
  - `pr_only` preview is informational only and does not simulate a bundle decision object
  - direct-fix preview requires a currently supported direct-fix action type plus configured `WriteRole`
  - invalid `strategy_inputs` currently surfaces as a preview `message`, not as a dedicated additive validation envelope
  - there is no `resolution` object today

### `POST /api/remediation-runs`

- Request surface:
  - `action_id`
  - `mode`
  - optional `strategy_id`
  - optional `strategy_inputs`
  - `risk_acknowledged`
  - optional deprecated `pr_bundle_variant`
  - optional `repo_target`
- Response surface:
  - `id`
  - `action_id`
  - `mode`
  - `status`
  - `created_at`
  - `updated_at`
  - `manual_high_risk`
  - `pre_execution_notice`
  - `runbook_url`
- Locked current behavior:
  - `strategy_id` remains the compatibility key when a strategy catalog applies
  - deprecated `pr_bundle_variant` is still accepted and mapped to `strategy_id` when a legacy mapping exists
  - `repo_target` already exists on the generic single-run route
  - no `profile_id` is accepted yet
  - no `artifacts.resolution` payload is created yet

### `POST /api/remediation-runs/group-pr-bundle`

- Request surface:
  - group selector fields: `action_type`, `account_id`, `status`, `region | region_is_null`
  - optional `strategy_id`
  - optional `strategy_inputs`
  - `risk_acknowledged`
  - optional deprecated `pr_bundle_variant`
  - optional `repo_target`
- Response surface:
  - same `RemediationRunCreatedResponse` shape as the single-run route
- Locked current behavior:
  - this route creates one grouped `RemediationRun` anchored to one representative action
  - one top-level strategy selection applies to the whole grouped run
  - there is no grouped `action_overrides[]` surface yet
  - no per-action resolved decision payload exists yet

### `POST /api/action-groups/{group_id}/bundle-run`

- Request surface:
  - optional `strategy_id`
  - optional `strategy_inputs`
  - `risk_acknowledged`
  - optional deprecated `pr_bundle_variant`
- Response surface:
  - `group_run_id`
  - `remediation_run_id`
  - `reporting_token`
  - `reporting_callback_url`
  - `status`
- Locked current behavior:
  - this route seeds `ActionGroupRun` reporting metadata plus grouped `RemediationRun` artifacts
  - this route does not currently accept `repo_target`
  - this route is not yet aligned to the richer validation and compatibility surface of `POST /api/remediation-runs/group-pr-bundle`

### `GET /api/remediation-runs/{id}`

- Response surface:
  - `id`, `action_id`, `mode`, `status`, `outcome`, `logs`, `artifacts`
  - `approved_by_user_id`
  - `started_at`, `completed_at`, `created_at`, `updated_at`
  - `action`
  - `artifact_metadata`
- Locked current behavior:
  - run detail returns raw stored `artifacts`
  - there is no additive run-detail hydration for `selected_profile`, `support_tier`, `finding_coverage`, or `decision_rationale`
  - existing runs therefore expose legacy mirror fields directly to current clients

## Explicit Non-Presence Lock

Later waves must treat the following as additive work, not as current behavior:

- no `profile_id` request field on generic create routes
- no `profiles[]` or `recommended_profile_id` on remediation options
- no `resolution` object on preview or run detail
- no grouped `action_overrides[]`
- no `repo_target` support on `POST /api/action-groups/{group_id}/bundle-run`
