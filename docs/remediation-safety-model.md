# Remediation Safety Model

This document defines the safety controls used by remediation run creation and execution.

## Goals

- Force explicit remediation strategy selection for high-impact controls.
- Surface dependency impact before a run is created.
- Block unsafe execution paths by default.
- Preserve immutable risk evidence on every run.

## Strategy Model

Strategies are registered per `action_type` in `backend/services/remediation_strategy.py`.

Each strategy defines:

- `strategy_id`
- `mode` (`pr_only` or `direct_fix`)
- `risk_level` (`low|medium|high`)
- optional `input_schema`
- `supports_exception_flow`
- static warning text

Clients retrieve available strategies through:

- `GET /api/actions/{action_id}/remediation-options`

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

Run creation endpoints enforce the safety model:

- `POST /api/remediation-runs`
- `POST /api/remediation-runs/group-pr-bundle`

Validation includes:

- strategy required for strategy-mapped action types
- mode/strategy compatibility
- strategy input schema validation
- risk acknowledgement requirement for `warn|unknown`
- direct-fix WriteRole requirement

Legacy clients can still send `pr_bundle_variant`; server-side mapping converts compatible variants to `strategy_id`.

## Immutable Run Evidence

Run-time safety evidence is stored in `remediation_runs.artifacts`:

- `selected_strategy`
- `strategy_inputs`
- `risk_snapshot`
- `risk_acknowledged`
- `legacy_variant_mapped_from` (when applicable)

This evidence is carried through queue payloads and worker processing.

## Direct-Fix Scope

Direct-fix is intentionally narrow:

- supported for low-risk enablement actions plus `ebs_default_encryption`
- risky controls remain strategy-gated PR flows
- worker logs pre-check/apply/post-check phases for auditability

## Audit Expectations

- Every remediation run records strategy and risk context.
- No strategy path is treated as implicitly safe.
- Exception-style strategies remain explicit user choices, not silent fallbacks.

## Monitoring and Alerts

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

- `reason` (for example `strategy_mode_mismatch`, `risk_ack_missing`, `dependency_check_failed`)
- `action_type`
- `strategy_id`
- `mode`

Use this event to alert on spikes in remediation run validation failures and strategy mismatch errors.

### Worker dispatch/error events

`event=remediation_worker_dispatch_error` with:

- `phase` (for example `payload_invalid_uuid`, `pr_bundle_generation_exception`, `run_failed`)
- `run_id`
- `action_type`
- `strategy_id`
- `mode`

Use this event to alert on spikes in worker dispatch/execution failures.

### Recommended CloudWatch alarms

- Validation failure rate spike (`event=remediation_validation_failure`).
- Strategy mismatch spike (`reason=strategy_mode_mismatch` or `reason=strategy_conflict`).
- Worker dispatch error spike (`event=remediation_worker_dispatch_error`).
