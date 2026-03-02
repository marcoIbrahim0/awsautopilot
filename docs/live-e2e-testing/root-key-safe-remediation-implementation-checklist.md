# Root-Key Safe Remediation Implementation Checklist (Serial)

> ⚠️ Status: In progress — Slice 2, Slice 3 (API contracts), Slice 3.5 (discovery/classification persistence path), Slice 4 closure orchestration with runtime wiring, Slice 5 guardrails (executor-worker safety path), and Slice 6 rollout/ops controls are implemented behind feature flags.
>
> Source spec: `docs/live-e2e-testing/root-key-safe-remediation-spec.md`
>
> Gate matrix: `docs/live-e2e-testing/root-key-safe-remediation-acceptance-matrix.md`
>
> Rule: keep all new behavior behind feature flags until final rollout gate.

## Slice 0: Baseline Lock and Scope Guard

- [ ] Confirm no behavior change with all root-safe flags disabled.
- [ ] Capture baseline responses for:
  - `GET /api/actions/{id}/remediation-options`
  - `POST /api/remediation-runs`
  - `GET /api/remediation-runs/{id}`
- [ ] Snapshot baseline test status:
  - `tests/test_remediation_runs_api.py`
  - `tests/test_remediation_run_worker.py`

Done when:

- Existing root-key tests pass unchanged with flags off.

## Slice 1: Data Model and Migration

- [ ] Add `root_safe_remediation_states` table and indexes.
- [ ] Add `root_safe_remediation_events` table and indexes.
- [ ] Add ORM models and enum/constants for root-safe states.
- [ ] Add migration with downgrade path.

Done when:

- Migration applies cleanly and model import tests pass.

## Slice 2: State Machine Service Layer

- [x] Add `backend/services/root_key_remediation_state_machine.py`.
- [x] Implement transition guard functions and terminal-state lock.
- [x] Implement event + evidence append helper for every transition.
- [x] Add idempotency handling for duplicate transition requests.
- [x] Enforce tenant-scoped `action_id`/`finding_id` ownership on `create_run` writes.
- [x] Add retry classification (retryable vs terminal) with capped backoff.

Done when:

- New service/store unit tests validate transition matrix, illegal-transition rejection, create/transition auth-scope violations, and retry-idempotency.

## Slice 3: API Read/Write Contracts

- [x] Add `POST /api/root-key-remediation-runs` with tenant-scoped create and idempotency support.
- [x] Add `GET /api/root-key-remediation-runs/{id}` tenant-scoped run detail contract.
- [x] Add state transition endpoints:
  - `POST /api/root-key-remediation-runs/{id}/validate`
  - `POST /api/root-key-remediation-runs/{id}/disable`
  - `POST /api/root-key-remediation-runs/{id}/rollback`
  - `POST /api/root-key-remediation-runs/{id}/delete`
- [x] Add external task completion endpoint:
  - `POST /api/root-key-remediation-runs/{id}/external-tasks/{task_id}/complete`
- [x] Add rollout/ops control endpoints:
  - `POST /api/root-key-remediation-runs/{id}/pause`
  - `POST /api/root-key-remediation-runs/{id}/resume`
  - `GET /api/root-key-remediation-runs/ops/metrics`
- [x] Enforce auth + tenant scope + action-type guard + fail-closed transition/state handling.
- [x] Enforce consistent error envelope + `correlation_id` + contract-version handling.
- [x] Enforce pause-state mutation blocking (`run_paused`) and resume-target replay semantics.

Done when:

- API tests cover no-auth, wrong-tenant, happy path, invalid transition, and idempotent replay contracts for new endpoints.

## Slice 3.5: Root-Key Usage Discovery and Dependency Classification

- [x] Add CloudTrail lookback query path with pagination and transient retry handling.
- [x] Normalize root-key usage fingerprints (`service`, `api_action`, `source_ip`, `user_agent`, `time`) with deterministic ordering.
- [x] Match each fingerprint against managed dependency registry and emit `managed`/`unknown`.
- [x] Persist fingerprint classification rows tenant-scoped to `root_key_dependency_fingerprints`.
- [x] Compute and return overall auto-flow eligibility (`false` on unknown usage or partial CloudTrail data).
- [x] Add tests for no-usage, all-managed, mixed managed/unknown, and transient CloudTrail retry recovery.

Done when:

- Discovery/classification tests pass and persisted fingerprints remain idempotent per run.

## Slice 3.6: Frontend Lifecycle UX for Root-Key Runs

- [x] Add feature-flagged root-key lifecycle route (`/root-key-remediation-runs/{id}`) with default-off behavior.
- [x] Render run timeline with state + timestamp + evidence links from run-detail API.
- [x] Render dependency table with managed/unknown classification.
- [x] Add action-required wizard for unknown dependencies with fail-closed transitions.
- [x] Add external-task completion flow for migration/manual steps.
- [x] Add rollback guidance and terminal completion summary panels.
- [x] Enforce role-based action controls (admin mutates; members read-only).
- [x] Add frontend tests for timeline states, wizard flow, and API error rendering.

Done when:

- Feature-flagged UI renders required lifecycle surfaces and targeted frontend tests pass.

## Slice 4: Verification Orchestration

- [x] Add closure orchestration service:
  - `backend/services/root_key_remediation_closure.py`
- [x] Reuse `ingest`, `compute`, and `reconcile` trigger flow through injectable idempotent trigger callables.
- [x] Add closure polling path with explicit terminal outcomes (`completed`, `needs_attention`, `failed`).
- [x] Persist closure-cycle summary artifact with dispatch + polling + final snapshot metadata.
- [x] Wire closure service into API/worker runtime path behind `ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED`.

Done when:

- Integration/e2e tests prove converged, policy-fail, timeout, auth-scope, and retry-safe terminal paths.

## Slice 5: Root Delete Safety Guard

- [x] Harden root-delete executor path to avoid self-invalidating credential context (self-cutoff guard + ordered mutation handling).
- [x] Add fail-closed reason mapping for guard/deletion gate failures (`delete_validation_not_passed`, `delete_disable_window_not_clean`, `delete_window_disabled`, `delete_unknown_dependencies`, `self_cutoff_guard_not_guaranteed`).
- [ ] Ensure error mapping lands in `blocked_operator_error` with clear operator next action.
- [x] Add executor-worker regression tests:
  - self-cutoff guard regression
  - disable clean-window success
  - rollback on breakage signal
  - delete gate fail-closed paths
  - auth-scope fail-closed path
  - replay-safe disable retry

Done when:

- Regression tests prevent uncontrolled self-cutoff behavior and unsafe delete progression.

## Slice 6: Feature Flags, Rollout, and Ops Wiring

- [x] Add config flags for executor-worker path:
  - `ROOT_KEY_SAFE_REMEDIATION_EXECUTOR_ENABLED`
  - `ROOT_KEY_SAFE_REMEDIATION_MONITOR_LOOKBACK_MINUTES`
- [x] Add rollout flags:
  - `ROOT_KEY_SAFE_REMEDIATION_CANARY_ENABLED`
  - `ROOT_KEY_SAFE_REMEDIATION_CANARY_PERCENT`
  - `ROOT_KEY_SAFE_REMEDIATION_CANARY_TENANT_ALLOWLIST`
  - `ROOT_KEY_SAFE_REMEDIATION_CANARY_ACCOUNT_ALLOWLIST`
- [x] Add ops control flags:
  - `ROOT_KEY_SAFE_REMEDIATION_KILL_SWITCH_ENABLED`
  - `ROOT_KEY_SAFE_REMEDIATION_OPS_METRICS_ENABLED`
- [x] Wire defaults to behavior-preserving values and document runtime behavior.
- [x] Add immutable operator override reason logging on create/transition/task-complete operations.
- [x] Add tenant-scoped ops metrics calculations:
  - auto success rate
  - rollback rate
  - needs_attention rate
  - closure pass rate
  - mean time to detect unknown dependency

Done when:

- Startup config tests pass, flagged code paths are fully dark by default, and rollout controls can be enabled incrementally without cross-tenant leakage.

## Slice 7: Acceptance and Live Validation

- [x] Add deterministic integration/e2e matrix tests:
  - `tests/test_root_key_remediation_plan_e2e.py`
  - fixture: `tests/fixtures/root_key_safe_remediation_plan_scenarios.json`
  - expected matrix artifact: `tests/fixtures/root_key_safe_remediation_plan_expected_matrix.json`
- [ ] Re-run Wave 7 Test 25 and Test 28 with evidence capture.
- [ ] Update tracker rows:
  - `docs/live-e2e-testing/00-BASE-ISSUE-TRACKER.md` Section 3 #15, Section 4 #22, Section 6 #8

Done when:

- Root-safe flow ends in explicit terminal state (`resolved`, `unresolved_after_verification`, or `blocked_operator_error`) with no ambiguous closure outcome.

## Slice 8: Documentation and Handover

- [ ] Update runbook docs if endpoint or operator flow changes:
  - `docs/prod-readiness/root-credentials-required-iam-root-access-key-absent.md`
  - `docs/remediation-safety-model.md`
- [ ] Update `docs/live-e2e-testing/README.md` and `docs/README.md` links if structure changes.
- [ ] Update `.cursor/notes/task_log.md` and `.cursor/notes/task_index.md`.

Done when:

- Documentation matches shipped behavior and references current API/state terms.
