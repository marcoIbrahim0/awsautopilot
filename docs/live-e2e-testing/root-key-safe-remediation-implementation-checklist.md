# Root-Key Safe Remediation Implementation Checklist (Serial)

> ⚠️ Status: In progress — Slice 2, Slice 3 (API contracts), Slice 3.5 (discovery/classification persistence path), and Slice 5 guardrails (executor-worker safety path) are implemented behind feature flags; worker-side verification/closure slices remain pending.
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
- [x] Enforce auth + tenant scope + action-type guard + fail-closed transition/state handling.
- [x] Enforce consistent error envelope + `correlation_id` + contract-version handling.

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

- [ ] Add verification enqueue path after `root-safe-report result=success`.
- [ ] Reuse existing `ingest`, `compute`, and `reconcile` trigger flow.
- [ ] Add polling job or task that writes `resolved` or `unresolved_after_verification`.
- [ ] Persist verification timestamps and final snapshot fields.

Done when:

- Worker/integration tests prove both converged and timeout terminal states.

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

## Slice 6: Feature Flags and Config Wiring

- [x] Add config flags for executor-worker path:
  - `ROOT_KEY_SAFE_REMEDIATION_EXECUTOR_ENABLED`
  - `ROOT_KEY_SAFE_REMEDIATION_MONITOR_LOOKBACK_MINUTES`
- [x] Wire defaults to behavior-preserving values and document runtime behavior.

Done when:

- Startup config tests pass and flagged code paths are fully dark by default.

## Slice 7: Acceptance and Live Validation

- [ ] Add/extend automated tests:
  - `tests/test_root_safe_state_machine.py`
  - `tests/test_remediation_runs_api.py`
  - `tests/test_remediation_run_worker.py`
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
