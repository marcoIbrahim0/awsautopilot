# Important To Do

This checklist tracks the top follow-up actions after enforcing explicit PR-bundle generation errors and removing placeholder-only outputs.

## Priority Actions

### 3) Monitor unsupported-action error volume after rollout
- **Severity:** Medium-Low
- **Why this is important:** Requests that previously appeared to succeed with placeholder output now fail explicitly. This improves correctness, but can temporarily increase visible failure counts.
- **What to do now:**
  1. Monitor remediation worker/API logs for `pr_bundle_error.code` spikes (especially `unsupported_action_type`, `pr_only_action_type_unsupported`, and `exception_strategy_requires_exception_workflow`).
  2. Review weekly trend by action type and tenant.
  3. Add/adjust UI copy in remediation flows where repeat error patterns appear.
- **References:**
  - [`backend/services/pr_bundle.py`](../../backend/services/pr_bundle.py)
  - [`backend/workers/jobs/remediation_run.py`](../../backend/workers/jobs/remediation_run.py)
  - [`docs/prod-readiness/README.md`](README.md)

### 4) Run full regression suite before release cut
- **Severity:** Medium
- **Why this is important:** Focused tests passed for changed modules, but release confidence requires full-suite validation.
- **What to do now:**
  1. Run full backend pytest suite in CI-equivalent environment.
  2. Confirm no failures in remediation run API/worker integration flows.
  3. Record test run metadata (date, command, pass/fail summary) in release notes.
- **References:**
  - [`docs/local-dev/tests.md`](../local-dev/tests.md)
  - [`tests/test_step7_components.py`](../../tests/test_step7_components.py)
  - [`tests/test_remediation_run_worker.py`](../../tests/test_remediation_run_worker.py)

### 5) Clarify mode-only vs executable action semantics (`pr_only`, `direct_fix`, `pr_bundle`)
- **Severity:** Medium
- **Why this is important:** These IDs appear in extracted inventories as execution-mode markers, but not as concrete action implementations. Ambiguity can cause incorrect remediation expectations.
- **What to do now:**
  1. Define and document whether each value is a mode flag, an action ID, or both.
  2. Align API response documentation with runtime behavior for each value.
  3. Add a validation check so unsupported values fail with explicit, stable error text.
- **References:**
  - [`docs/prod-readiness/06-control-action-inventory.md`](06-control-action-inventory.md)
  - [`backend/services/action_engine.py`](../../backend/services/action_engine.py)
  - [`backend/routers/actions.py`](../../backend/routers/actions.py)

### 6) Replace `iam_root_access_key_absent` placeholder-style PR output with concrete change logic
- **Severity:** Medium
- **Why this is important:** Current extracted PR-bundle path indicates Terraform `null_resource` only, which is insufficiently explicit for reliable automation and review.
- **What to do now:**
  1. Specify the concrete remediation operation(s) expected for this action.
  2. Update PR-bundle generation to emit explicit, reviewable resource changes.
  3. Add tests that assert non-placeholder output and expected action metadata.
- **References:**
  - [`docs/prod-readiness/06-control-action-inventory.md`](06-control-action-inventory.md)
  - [`backend/services/pr_bundle.py`](../../backend/services/pr_bundle.py)
  - [`backend/workers/services/direct_fix.py`](../../backend/workers/services/direct_fix.py)

### 7) Prevent control-ID casing drift across extracted sources
- **Severity:** Low
- **Why this is important:** Case inconsistencies (`SECURITYHUB.1` vs `SecurityHub.1`, etc.) were normalized in inventory, but drift can reappear and break matching or reporting consistency.
- **What to do now:**
  1. Add canonicalization rules for control IDs at extraction/mapping boundaries.
  2. Add tests to enforce canonical registry casing for mapped controls.
  3. Fail fast when non-canonical IDs are introduced in mapping tables.
- **References:**
  - [`docs/prod-readiness/06-control-action-inventory.md`](06-control-action-inventory.md)
  - [`docs/prod-readiness/06-task4-raw-id-registries.md`](06-task4-raw-id-registries.md)

### 8) Prevent scenario-to-implementation drift across architecture tasks
- **Severity:** Medium
- **Why this is important:** Architecture scenario files are narrative-first; when resource mapping and misconfiguration assignment begin, controls can drift, overlap, or become inconsistent with the approved split.
- **What to do now:**
  1. Create a single control-assignment checklist before resource-level design starts, and enforce one-time assignment for each control ID.
  2. Validate Architecture 1 and Architecture 2 control lists against `06-control-action-inventory.md` before drafting any resource tables.
  3. Add a pre-handoff review step that explicitly checks for coverage gaps, duplicate control ownership, and narrative-to-resource consistency.
- **References:**
  - [`docs/prod-readiness/06-control-action-inventory.md`](06-control-action-inventory.md)
  - [`docs/prod-readiness/07-task2-arch1-scenario.md`](07-task2-arch1-scenario.md)
  - [`docs/prod-readiness/07-task3-arch2-scenario.md`](07-task3-arch2-scenario.md)

### 9) Reduce interpretation drift in blast-radius remediation wording
- **Severity:** Low
- **Why this is important:** Even when resource specs are explicit, remediation wording can be interpreted differently across teams and later implementation tasks.
- **What to do now:**
  1. Add acceptance criteria for each A-series `Correct remediation` field with concrete expected decision points.
  2. Validate wording against the source task specification before architecture embedding work starts.
  3. Record any clarification decisions in the related task doc instead of relying on implicit interpretation.
- **References:**
  - [`docs/prod-readiness/07-task4-a-series-resources.md`](07-task4-a-series-resources.md)
  - [`docs/prod-readiness/07-task1-input-validation.md`](07-task1-input-validation.md)

### 10) Enforce task-scope change boundaries during doc updates
- **Severity:** Medium
- **Why this is important:** Updating files outside the explicitly requested scope can create process churn and review ambiguity, even when technical risk is low.
- **What to do now:**
  1. Add a pre-merge checklist item that distinguishes required bookkeeping updates from optional cross-link/index edits.
  2. Require explicit confirmation before applying non-essential documentation changes outside the target deliverable.
  3. Capture scope-expansion rationale in task logs when extra edits are necessary for governance compliance.
- **References:**
  - [`docs/prod-readiness/important-to-do.md`](important-to-do.md)
  - [`.cursor/notes/task_log.md`](../../.cursor/notes/task_log.md)
  - [`.cursor/notes/task_index.md`](../../.cursor/notes/task_index.md)

### 11) Verify Architecture 2 business-domain distinctness before resource design
- **Severity:** Low-Medium
- **Why this is important:** Architecture 2 must remain clearly distinct from Architecture 1 by industry context and team type; if domains converge, scenario realism and control-coverage narrative quality degrade.
- **What to do now:**
  1. Re-check Architecture 1 and Architecture 2 narratives for industry and ownership-team overlap before assigning concrete resources.
  2. If overlap is material, update Architecture 2 narrative first, then re-validate control coverage alignment.
  3. Record explicit domain-difference rationale in the architecture task notes before moving to resource-level design.
- **References:**
  - [`docs/prod-readiness/07-task2-arch1-scenario.md`](07-task2-arch1-scenario.md)
  - [`docs/prod-readiness/07-task3-arch2-scenario.md`](07-task3-arch2-scenario.md)
  - [`docs/prod-readiness/07-task3-control-coverage-validation.md`](07-task3-control-coverage-validation.md)

### 12) Lock Terraform plan expectations to semantic outcomes (not literal diff text)
- **Severity:** Low
- **Why this is important:** Terraform plan output wording can vary by provider version and state drift, so tests/reviews tied to exact plan text can become noisy or brittle.
- **What to do now:**
  1. Validate B-series plan behavior using semantic checks (what must change vs what must be preserved), not exact plan line text matching.
  2. Capture provider version and environment context in any execution evidence to explain expected output differences.
  3. Keep scenario acceptance criteria focused on preserve-vs-remediate outcomes for B1/B2/B3.
- **References:**
  - [`docs/prod-readiness/07-task5-b-series-resources.md`](07-task5-b-series-resources.md)
  - [`docs/prod-readiness/07-task1-input-validation.md`](07-task1-input-validation.md)

### 13) Clean and isolate git staging scope before follow-up implementation
- **Severity:** Medium
- **Why this is important:** The repository currently has many unrelated modified/untracked files; without strict staging discipline, follow-up commits can accidentally include unrelated changes.
- **What to do now:**
  1. Use targeted staging (`git add <path>`) and verify with `git status --short` before each commit.
  2. Split unrelated work into separate commits/PRs to preserve traceability.
  3. Add a pre-commit review checkpoint that confirms only task-scoped files are staged.
- **References:**
  - [`docs/prod-readiness/important-to-do.md`](important-to-do.md)
  - [`.cursor/notes/task_log.md`](../../.cursor/notes/task_log.md)

### 14) Add manual-gate handling for root-credential control setup in architecture scripts
- **Severity:** Medium
- **Why this is important:** `IAM.4` maps to an existing root-principal security state, not a normal deployable resource; attempting full automation without a manual gate can produce brittle or unsafe workflows.
- **What to do now:**
  1. Add explicit script preflight that classifies root-principal setup as `manual_required` and exits with operator instructions instead of attempting creation.
  2. Record a deterministic evidence marker for this branch so runs are auditable (`manual_root_credentials_gate=true`).
  3. Link this gate to the root-credentials runbook used by remediation workflows.
- **References:**
  - [`docs/prod-readiness/07-architecture-design.md`](07-architecture-design.md)
  - [`docs/prod-readiness/08-task1-resource-inventory.md`](08-task1-resource-inventory.md)
  - [`docs/prod-readiness/root-credentials-required-iam-root-access-key-absent.md`](root-credentials-required-iam-root-access-key-absent.md)

### 15) Prevent variable/tag drift between architecture source and extracted inventory
- **Severity:** Low
- **Why this is important:** The script-variable block is duplicated across architecture/source inventory docs; small name/tag drift can cause wrong parameter wiring even when resource logic is correct.
- **What to do now:**
  1. Add a single-source check that validates every variable/tag in `08-task1-resource-inventory.md` exists in `07-architecture-design.md`.
  2. Fail CI when resource-name constants diverge between source design and extracted inventory output.
  3. Include a short update checklist in future architecture edits: update source design first, then regenerate extraction output.
- **References:**
  - [`docs/prod-readiness/07-architecture-design.md`](07-architecture-design.md)
  - [`docs/prod-readiness/08-task1-resource-inventory.md`](08-task1-resource-inventory.md)

### 16) Enable live status updates for high-confidence controls
- **Severity:** High
- **Why this is important:** High-confidence controls have clearer signal quality and can support faster status updates with lower false-resolved risk.
- **What to do now:**
  1. Enable SaaS live status updates for high-confidence controls.
  2. Define rollout guardrails (pilot scope, metrics, rollback trigger) before global enablement.
  3. Keep explicit fallback for uncertain reads so findings are not incorrectly marked as solved.
- **References:**
  - [`docs/reconciliation_quality_review.md`](../reconciliation_quality_review.md)
  - [`backend/workers/services/shadow_state.py`](../../backend/workers/services/shadow_state.py)
  - [`docs/control-plane-event-monitoring.md`](../control-plane-event-monitoring.md)

### 17) Expand medium/low-confidence rule-pattern coverage and test scenarios
- **Severity:** High
- **Why this is important:** Medium and low-confidence controls need broader pattern handling and stronger test depth before they can be trusted for live status promotion.
- **What to do now:**
  1. Add more rule-pattern coverage for medium and low-confidence controls (normal and edge-case variants).
  2. Add more test scenarios for these controls in reconciliation/unit/integration test suites.
  3. Gate live-status promotion for medium/low controls on measurable coverage and observed precision targets.
- **References:**
  - [`docs/reconciliation_quality_review.md`](../reconciliation_quality_review.md)
  - [`backend/workers/services/inventory_reconcile.py`](../../backend/workers/services/inventory_reconcile.py)
  - [`tests/test_inventory_reconcile.py`](../../tests/test_inventory_reconcile.py)
