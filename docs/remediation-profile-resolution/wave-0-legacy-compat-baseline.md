# Wave 0 Legacy Compatibility Baseline

> Scope date: 2026-03-14
>
> This source baseline captures the current legacy artifact mirrors, duplicate detection rules, and resend behavior that later remediation-profile-resolution waves must preserve.
>
> Note: the local `codex/rem-profile-w0-*` refs did not contain committed baseline markdown files at integration time. This baseline was reconstructed from the current code paths during Wave 0 integration.

Consolidated in:

- [Wave 0 contract lock](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/wave-0-contract-lock.md)

Code sources reviewed:

- [backend/routers/remediation_runs.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/routers/remediation_runs.py)
- [backend/routers/action_groups.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/routers/action_groups.py)
- [backend/workers/jobs/remediation_run.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/jobs/remediation_run.py)
- [backend/workers/jobs/remediation_run_execution.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/jobs/remediation_run_execution.py)

## Legacy Artifact Mirrors and Consumers

| Mirror field | Current writers | Current consumers | Lock to preserve |
| --- | --- | --- | --- |
| `selected_strategy` | `POST /api/remediation-runs`, `POST /api/remediation-runs/group-pr-bundle`, `POST /api/action-groups/{group_id}/bundle-run`, remediation worker write-back after generation | single-run duplicate detection, resend payload reconstruction, remediation worker fallback when job omits `strategy_id`, execution/manual-high-risk helpers, raw run-detail artifacts | `strategy_id` remains the current generic compatibility key until a later wave adds a canonical resolution payload and keeps this mirror readable during rollout |
| `strategy_inputs` | same generic create routes, action-groups bundle route, remediation worker write-back after generation | duplicate detection, resend payload reconstruction, remediation worker fallback, execution change-summary generation, raw run-detail artifacts | later waves cannot remove this mirror until duplicate detection, resend, worker execution, and run-detail readers all move to the new canonical payload |
| `pr_bundle_variant` | generic create routes when legacy client field is supplied, action-groups bundle route, remediation worker write-back after generation | duplicate detection, resend payload reconstruction, worker bundle-generation variant fallback, legacy create-time mapping to `strategy_id` | the legacy variant field still participates in compatibility for older callers and must stay mirrored until those callers are retired |

## Current Duplicate-Detection Baseline

### Single-run `POST /api/remediation-runs`

- Active run block:
  - any existing run for the same `action_id` in `pending`, `running`, or `awaiting_approval` returns `409 duplicate_active_run`
- Request-signature match fields:
  - `mode`
  - `selected_strategy`
  - `strategy_inputs`
  - `pr_bundle_variant`
  - `repo_target`
- `pr_only` rate limits:
  - window: `20 minutes`
  - total queued runs for the action in window: `6`
  - identical request-signature runs in window: `3`
- `direct_fix` recent duplicate block:
  - identical signature within `30 seconds` returns `409 duplicate_recent_request`
- Explicitly not part of the current duplicate signature:
  - `risk_acknowledged`
  - any future `profile_id`

### Grouped `POST /api/remediation-runs/group-pr-bundle`

- Current duplicate guard is narrower than the single-run route
- Duplicate block criteria:
  - existing grouped run must already be `pending`
  - `artifacts.group_bundle.group_key` must match
  - `repo_target` must match
- Current `group_key` shape:
  - `{action_type}|{account_id}|{region-or-global}|{status}`
- There is no current total-window or identical-window rate limit on this grouped route

### Grouped `POST /api/action-groups/{group_id}/bundle-run`

- Current route creates an `ActionGroupRun` plus one grouped `RemediationRun`
- Current route does not implement the richer duplicate or rate-limit policy from `POST /api/remediation-runs/group-pr-bundle`
- Current route also does not accept `repo_target`

## Current Resend Baseline

### `POST /api/remediation-runs/{id}/resend`

- Only `pending` runs can be resent
- Resend rate limit:
  - maximum `3` resend attempts per run
  - rolling window `20 minutes`
  - tracked in `artifacts.queue_resend_attempts`
- Resend reconstructs or forwards:
  - `pr_bundle_variant`
  - `selected_strategy`
  - `strategy_inputs`
  - `risk_acknowledged`
  - grouped `action_ids` from `artifacts.group_bundle.action_ids`
- `repo_target` is not explicitly rebuilt into the resend queue payload today
- Current compatibility still works because the remediation worker falls back to `artifacts.repo_target` when the job payload omits it
- Later waves must preserve either:
  - that artifact fallback, or
  - an explicit resend payload field for `repo_target`

## Run-Detail Compatibility Baseline

- `GET /api/remediation-runs/{id}` returns raw stored `artifacts`
- Current clients therefore see the legacy mirror fields directly
- There is no canonical `artifacts.resolution` reader or normalization layer yet
- Later waves must preserve old run readability during rollout and rollback

## Current Compatibility Gap That Is Locked As Current State

- `POST /api/action-groups/{group_id}/bundle-run` still diverges from `POST /api/remediation-runs/group-pr-bundle`
- That divergence is current state, not already-fixed behavior:
  - no `repo_target`
  - no equivalent duplicate/rate-limit rules
  - route-specific `group_bundle.reporting` metadata and reporting-token issuance
