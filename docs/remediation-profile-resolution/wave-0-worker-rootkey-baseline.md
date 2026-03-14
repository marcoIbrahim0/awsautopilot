# Wave 0 Worker and Root-Key Baseline

> Scope date: 2026-03-14
>
> This source baseline captures the current remediation worker contract floor, schema-version fail-closed behavior, and root-key execution-authority boundary that later remediation-profile-resolution waves must preserve.
>
> Note: the local `codex/rem-profile-w0-*` refs did not contain committed baseline markdown files at integration time. This baseline was reconstructed from the current code paths during Wave 0 integration.

Consolidated in:

- [Wave 0 contract lock](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/wave-0-contract-lock.md)

Code sources reviewed:

- [backend/utils/sqs.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/utils/sqs.py)
- [backend/workers/main.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/main.py)
- [backend/workers/lambda_handler.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/lambda_handler.py)
- [backend/workers/jobs/remediation_run.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/jobs/remediation_run.py)
- [backend/workers/jobs/remediation_run_execution.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/jobs/remediation_run_execution.py)
- [backend/routers/root_key_remediation_runs.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/routers/root_key_remediation_runs.py)

## Worker Queue Schema-Version Baseline

- Current emitted queue payload version:
  - `backend/utils/sqs.py` writes `QUEUE_PAYLOAD_SCHEMA_VERSION = 1`
- Current accepted worker versions:
  - `backend/workers/main.py` supports only schema version `1` for all current job types, including `remediation_run`
  - `backend/workers/lambda_handler.py` uses the same support table and guard
- Fail-closed guard:
  - invalid `schema_version` values are quarantined with reason code `unsupported_schema_version`
  - unknown future versions are also quarantined with reason code `unsupported_schema_version`
  - missing `schema_version` currently defaults to legacy version `1`
- Rollout floor to preserve:
  - version `1` payloads must remain runnable until a later migration explicitly retires them
  - any future version `2` rollout must update both worker entrypoints before emission

## Current Remediation Worker Assumptions

- Generic remediation worker still consumes one top-level selection per run:
  - one `selected_strategy`
  - one `strategy_inputs`
  - optional one `pr_bundle_variant`
- Job-to-artifact fallback order:
  - worker reads the job payload first
  - if the job omits strategy fields, worker falls back to `run.artifacts`
- Grouped run assumptions that remain locked today:
  - one grouped `RemediationRun` row anchors the whole group
  - one top-level strategy/input set currently applies to every grouped action
  - grouped generation writes results back under `artifacts.group_bundle`
  - grouped execution resolves action ids from `group_bundle.resolved_action_ids` or falls back to `group_bundle.action_ids`
- Current grouped worker persistence still expects legacy shapes:
  - `artifacts.pr_bundle`
  - `artifacts.group_bundle`
  - mirror fields such as `selected_strategy`, `strategy_inputs`, and `pr_bundle_variant`
- There are no current consumers for:
  - `artifacts.resolution`
  - `artifacts.group_bundle.action_resolutions`

## Root-Key Execution-Authority Boundary

- Dedicated execution authority stays under:
  - `/api/root-key-remediation-runs`
- Current root-key contract version:
  - `2026-03-02`
- Current root-key strategy boundary:
  - only `iam_root_key_disable`
  - only `iam_root_key_delete`
- Current create-run eligibility:
  - action must be `iam_root_access_key_absent`
  - mutating routes require `Idempotency-Key`
  - optional `X-Root-Key-Contract-Version` must match when supplied
- Current create-time gates that later waves must not bypass:
  - feature flags
  - canary selection
  - optional discovery gating into `migration` or `needs_attention`
- Current lifecycle operations that remain dedicated to the root-key state machine:
  - create
  - get detail
  - validate
  - disable
  - rollback
  - delete
  - pause
  - resume
  - external task completion

## Root-Key Fail-Closed and Validation Baseline

- Delete currently fails closed when the executor worker path is unavailable:
  - endpoint returns `503 executor_unavailable`
  - generic fallback deletion is intentionally blocked
- Pause currently blocks later mutating operations until resume
- Idempotent replay is part of the current contract:
  - create returns `201` on first mutation and `200` with `idempotency_replayed=true` on replay
  - transition endpoints return `RootKeyRunResponse` with replay metadata
- Later generic profile-resolution waves may add metadata around IAM.4 decisions, but they must not:
  - replace `/api/root-key-remediation-runs` as execution authority
  - make root-key state transitions depend on a generic profile layer
  - weaken current canary, discovery, pause, delete, or rollback guards

## Validation Floor Already Backing This Baseline

- [tests/test_worker_main_contract_quarantine.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_worker_main_contract_quarantine.py)
- [tests/test_remediation_run_worker.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_remediation_run_worker.py)
- [tests/test_root_key_remediation_runs_api.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_root_key_remediation_runs_api.py)
