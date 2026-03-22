# Remediation Safety Model

This document defines the active safety controls used by remediation option selection, remediation preview, and remediation run creation.

## Current Scope

> ⚠️ Status: Current execution scope is PR-only. Customer `WriteRole` and `direct_fix` execution are out of scope.

- Active remediation surfaces expose `pr_only` strategies only.
- `direct_fix` requests are rejected at API entry points.
- Account onboarding and validation use `ReadRole`; `role_write_arn` is retained only for backward compatibility and does not activate remediation.
- Customer-run PR bundles remain the supported execution path.

## Goals

- Force explicit remediation strategy selection for high-impact controls.
- Surface dependency impact before a run is created.
- Block unsupported or unsafe execution paths by default.
- Preserve immutable risk evidence on every run.

## Strategy Model

Strategies are registered per `action_type` in `backend/services/remediation_strategy.py`.

Each active strategy defines:

- `strategy_id`
- `mode` (`pr_only`)
- `risk_level` (`low|medium|high`)
- optional `input_schema`
- `supports_exception_flow`
- static warning text

Clients retrieve available strategies through:

- `GET /api/actions/{action_id}/remediation-options`

Historical `direct_fix` registry entries may remain on disk for future recovery, but active discovery filters them out so current UI and API surfaces stay PR-only.

## Dependency Checks

Dependency impact is evaluated in `backend/services/remediation_risk.py`.

Each check returns:

- `code`
- `status`: `pass | warn | unknown | fail`
- `message`

Enforcement:

- `fail`: run creation is rejected.
- `warn` or `unknown`: run creation requires `risk_acknowledged=true`.
- `pass`: no additional acknowledgement required.

## API Enforcement

Run creation endpoints enforce the current safety model:

- `POST /api/remediation-runs`
- `POST /api/remediation-runs/group-pr-bundle`

Validation includes:

- strategy required for strategy-mapped action types
- mode/strategy compatibility
- strategy input schema validation
- risk acknowledgement requirement for `warn|unknown`
- explicit rejection of `direct_fix`

Legacy clients can still send `pr_bundle_variant`; server-side mapping converts compatible variants to `strategy_id` when possible.

## Immutable Run Evidence

Run-time safety evidence is stored in `remediation_runs.artifacts`:

- `selected_strategy`
- `strategy_inputs`
- `risk_snapshot`
- `risk_acknowledged`
- `legacy_variant_mapped_from` (when applicable)

Historical runs may still contain older `direct_fix_approval` metadata. New supported runs should not generate it.

## Audit Expectations

- Every remediation run records strategy and risk context.
- No unsupported execution mode is silently downgraded into mutation.
- Exception-style strategies remain explicit user choices, not silent fallbacks.
- Customer execution stays outside the SaaS write boundary through reviewed PR bundles.

## Monitoring And Alerts

The remediation API and worker emit structured log events for metric filters and alerting.

### Metric-style events

`event=remediation_metric` with `value=1`:

- `metric=strategy_selected_count`
- `metric=risk_ack_required_count`
- `metric=risk_ack_missing_rejection_count`
- `metric=dependency_check_fail_count`

Dimensions are included in the payload:

- `action_type`
- `strategy_id`
- `mode`

### Validation rejection events

`event=remediation_validation_failure` with:

- `reason` (for example `strategy_mode_mismatch`, `risk_ack_missing`, `dependency_check_failed`, `direct_fix_out_of_scope`)
- `action_type`
- `strategy_id`
- `mode`

Use this event to alert on spikes in remediation run validation failures and unsupported-mode requests.

### Worker dispatch/error events

`event=remediation_worker_dispatch_error` with:

- `phase` (for example `payload_invalid_uuid`, `pr_bundle_generation_exception`, `run_failed`)
- `run_id`
- `action_type`
- `strategy_id`
- `mode`

Use this event to alert on spikes in worker dispatch or PR-bundle generation failures.

### Recommended CloudWatch alarms

- Validation failure rate spike (`event=remediation_validation_failure`).
- Strategy mismatch spike (`reason=strategy_mode_mismatch` or `reason=strategy_conflict`).
- Unsupported direct-fix request spike (`reason=direct_fix_out_of_scope`).
- Worker dispatch error spike (`event=remediation_worker_dispatch_error`).
