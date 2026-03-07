# Interactive Remediation Experience — Tasks

**Plan reference:** `docs/phase-2/interactive-remediation-plan.md`
**Date created:** 2026-03-04
**Status:** In progress

---

## Part A — Guided Choice Inputs

### Task 1 — Extend input schema types
- [x] Add new field types to `StrategyInputSchemaField`: `select`, `boolean`, `cidr`, `number`
- [x] Add optional properties: `placeholder`, `help_text`, `default_value`, `options`, `visible_when`, `impact_text`, `group`, `min`, `max`
- [x] Ensure backward compatibility — existing `string`/`string_array` fields unchanged
- **File:** `backend/services/remediation_strategy.py`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_runs_api.py -k "strategy_input or (invalid and strategy)"`

### Task 2 — EC2.53 guided choice schema
- [x] Add `access_mode` select field: close_public / close_and_revoke / restrict_to_ip / restrict_to_cidr
- [x] Add conditional `allowed_cidr` (type: cidr) visible when access_mode is restrict_to_ip or restrict_to_cidr
- [x] Add conditional `allowed_cidr_ipv6` visible when IPv6 requested
- [x] Add impact_text per option
- [x] Wire into `_generate_for_sg_restrict_public_ports()` in `pr_bundle.py`
- **File:** `backend/services/remediation_strategy.py`, `backend/services/pr_bundle.py`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_step7_components.py -k "ec2_53 or sg_restrict"`

### Task 3 — IAM.4 guided choice schema
- [x] Add `action_mode` select field: disable_key (recommended) / delete_key
- [x] Add impact_text per option
- [x] Wire into IAM.4 strategy builder
- **File:** `backend/services/remediation_strategy.py`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_runs_api.py -k "iam_root or strategy"`

### Task 4 — Config.1 guided choice schema
- [x] Add `recording_scope` select: all_resources / keep_existing
- [x] Add `delivery_bucket_mode` select: create_new / use_existing
- [x] Add conditional `existing_bucket_name` string (visible when use_existing)
- [x] Add `encrypt_with_kms` boolean toggle
- [x] Add conditional `kms_key_arn` string (visible when encrypt = true)
- [x] Wire into Config.1 bundle generator
- **File:** `backend/services/remediation_strategy.py`, `backend/services/pr_bundle.py`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_step7_components.py -k "aws_config_enabled"`

### Task 5 — CloudTrail.1 guided choice schema
- [x] Add `trail_name` string with default "security-autopilot-trail"
- [x] Add `create_bucket_policy` boolean (default true)
- [x] Add `multi_region` boolean (default true)
- [x] Wire into CloudTrail.1 bundle generator
- **File:** `backend/services/remediation_strategy.py`, `backend/services/pr_bundle.py`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_step7_components.py -k "cloudtrail"`

### Task 6 — S3 controls guided choice schemas
- [x] S3.5: `preserve_existing_policy` boolean, impact_text
- [x] S3.9: `log_bucket_name` string (required), impact_text
- [x] S3.11: `abort_days` number (default 7, min 1, max 365), impact_text
- [x] S3.15: `kms_key_mode` select (aws_managed / custom) + conditional `kms_key_arn`
- [x] S3.1, S3.2, S3.4: impact_text only (no new inputs)
- **File:** `backend/services/remediation_strategy.py`, `backend/services/pr_bundle.py`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_step7_components.py -k "s3"`

### Task 7 — Simple controls impact text
- [x] SecurityHub.1, GuardDuty.1, SSM.7, EC2.182, EC2.7: add `impact_text` to each strategy
- [x] Ensure remediation-options response includes strategy-level `impact_text` metadata
- **Files:** `backend/services/remediation_strategy.py`, `backend/routers/actions.py`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_runs_api.py -k "remediation_options"`

### Task 8 — Frontend: extend StrategyInputSchemaField type
- [x] Add new optional fields to `StrategyInputSchemaField` in `api.ts`: `placeholder`, `help_text`, `default_value`, `options`, `visible_when`, `impact_text`, `group`, `min`, `max`
- [x] Add new types to `type` union: `'select' | 'boolean' | 'cidr' | 'number'`
- **File:** `frontend/src/lib/api.ts`
- **Validation:** `npx tsc --noEmit`

### Task 9 — Frontend: render new field types in RemediationModal
- [x] Render `select` fields as `<select>` dropdowns with label + description per option
- [x] Render `boolean` fields as toggle switches
- [x] Render `cidr` fields as text inputs with CIDR format validation (x.x.x.x/y)
- [x] Render `number` fields as number inputs with min/max
- [x] Implement conditional visibility (`visible_when` logic)
- [x] Implement field grouping (`group` headings)
- [x] Implement help popovers (`help_text` → info icon + tooltip)
- [x] Render impact_text preview box below field groups
- **File:** `frontend/src/components/RemediationModal.tsx`
- **Validation:** `cd frontend && npx tsc --noEmit`; `cd frontend && npm run test:ui -- src/components/RemediationModal.test.tsx`

### Task 10 — Backend: impact summary in preview
- [x] Add `get_impact_summary(strategy_id, strategy_inputs) -> str` method
- [x] Return composed human-readable summary based on selected choices
- [x] Wire into `remediation-preview` API response
- **File:** `backend/services/remediation_strategy.py`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_runs_api.py -k "remediation_preview"`

---

**Dependency order:** Task 1 → Tasks 2–7 (parallel) → Task 8 → Task 9 → Task 10

**Live Test A:** After Tasks 1–10, open modal for EC2.53, Config.1, S3.9 and verify interactive choices render correctly.

---

## Part B — UX Enhancements

### Task 11 — Before/after resource state simulator
- [x] Add `before_state`, `after_state`, `diff_lines` to `RemediationPreview` response
- [x] Implement per-control state capture in runtime checks (current state → before_state)
- [x] Implement per-control predicted state computation (after_state)
- [x] Frontend: render two-column Before/After diff card in modal
- **Files:** `backend/routers/actions.py`, `backend/services/remediation_runtime_checks.py`, `backend/services/remediation_strategy.py`, `backend/workers/services/direct_fix.py`, `frontend/src/lib/api.ts`, `frontend/src/components/RemediationModal.tsx`, `tests/test_remediation_runs_api.py`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_runs_api.py -k "remediation_preview"` (`7 passed`); `cd frontend && npx tsc --noEmit` (pass)

### Task 12 — Smart defaults from AWS context
- [x] Frontend: auto-detect user IP via `api.ipify.org` for EC2.53 CIDR pre-fill
- [x] Backend: add KMS key list probe for S3.15 (`kms:ListAliases`)
- [x] Backend: return key list as `context.kms_key_options` in options response
- [x] Pre-fill Config.1 recording scope from existing recorder evidence
- [x] Pre-fill Config.1 and CloudTrail.1 bucket names with account-specific defaults
- **Files:** `backend/services/remediation_runtime_checks.py`, `backend/routers/actions.py`, `frontend/src/lib/api.ts`, `frontend/src/components/RemediationModal.tsx`, `frontend/src/components/RemediationModal.test.tsx`, `tests/test_remediation_runtime_checks.py`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_runtime_checks.py` (`6 passed`); `cd frontend && npm run test:ui -- src/components/RemediationModal.test.tsx` (`7 passed`); `cd frontend && npx tsc --noEmit` (pass)

### Task 13 — Rollback recipe shown upfront
- [x] Add `rollback_command: str` to `RemediationOption` in backend
- [x] Populate rollback command for all 16 controls (see plan for exact commands)
- [x] Add `rollback_command?` to frontend `RemediationOption` type
- [x] Render collapsed "How to undo this" section with copy button in modal
- **Files:** `remediation_strategy.py`, `api.ts`, `RemediationModal.tsx`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_runs_api.py -k "remediation_options"`; `cd frontend && npm run test:ui -- src/components/RemediationModal.test.tsx`; `cd frontend && npx tsc --noEmit`

### Task 14 — Estimated time to Security Hub PASSED
- [x] Add `estimated_resolution_time: str` and `supports_immediate_reeval: bool` to strategy
- [x] Populate per-control estimates (12–24h for most, 1–6h for Config/CloudTrail, ~1h for Hub/GuardDuty)
- [x] Backend: new endpoint `POST /api/actions/{id}/trigger-reeval`
- [x] Frontend: show estimate text below Apply; add "Trigger re-evaluation after apply" checkbox
- **Files:** `remediation_strategy.py`, routes file, `api.ts`, `RemediationModal.tsx`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_runs_api.py -k "remediation_options or trigger_reeval"`; `cd frontend && npm run test:ui -- src/components/RemediationModal.test.tsx`; `cd frontend && npx tsc --noEmit`

### Task 15 — Blast radius indicator
- [x] Add `blast_radius: "account" | "resource" | "access_changing"` to strategy
- [x] Assign blast radius to all 16 controls (🟢/🟡/🔴)
- [x] Frontend: render colored pill badge in modal header with tooltip
- **Files:** `remediation_strategy.py`, `api.ts`, `RemediationModal.tsx`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_runs_api.py -k "remediation_options and blast_radius"`; `cd frontend && npm run test:ui -- src/components/RemediationModal.test.tsx`; `cd frontend && npx tsc --noEmit`

### Task 16 — "I don't know" escape hatches
- [x] Define escape hatch defaults for: S3.15 KMS, EC2.53 CIDR, Config.1 bucket, S3.9 log bucket, CloudTrail.1 bucket
- [x] Frontend: render inline "Not sure? [Use safe default →]" link below applicable fields
- [x] On click: auto-fill the field with the safe default value
- **Files:** `remediation_strategy.py` (defaults), `RemediationModal.tsx` (render)
- **Validation:** `cd frontend && npm run test:ui -- src/components/RemediationModal.test.tsx`; `cd frontend && npx tsc --noEmit`

### Task 17 — Post-apply "what changed" summary card
- [x] Backend: after successful apply, write `change_summary` artifact (JSON) to run artifacts
- [x] Schema: `applied_at`, `applied_by`, `changes[]` (field, before, after), `run_id`
- [x] Frontend: on action detail page, detect `change_summary` artifact and render card
- [x] Card format: ✅ Fixed on [date] by [user] — [change list] · [View run →]
- **Files:** `pr_bundle_executor_worker.py`, `ActionDetailDrawer.tsx`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_run_execution.py`; `cd frontend && npm run test:ui -- src/components/ActionDetailDrawer.test.tsx`; `cd frontend && npx tsc --noEmit`

### Task 18 — Exception as a first-class choice
- [x] Frontend: add "I need an exception" option at bottom of strategy list in modal
- [x] Show duration picker (7/14/30/90 days) and reason field inline when selected
- [x] Backend: accept exception duration and reason as `strategy_inputs` on exception strategy
- [x] Connect to existing `onChooseException` path in `RemediationModal.tsx`
- **Files:** `backend/services/remediation_strategy.py`, `backend/routers/remediation_runs.py`, `frontend/src/components/RemediationModal.tsx`, `frontend/src/components/ActionDetailDrawer.tsx`, `frontend/src/components/CreateExceptionModal.tsx`, `tests/test_remediation_runs_api.py`, `frontend/src/components/RemediationModal.test.tsx`
- **Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_runs_api.py`; `cd frontend && npm run test:ui -- src/components/RemediationModal.test.tsx`; `cd frontend && npx tsc --noEmit`

---

**Dependency order for Part B:** Tasks 11–18 are independent of each other (can be done in any order), but all depend on Part A being complete (Tasks 1–10).

---

## Summary

| Part | Tasks | Scope |
|---|---|---|
| **A** — Guided Inputs | Tasks 1–10 | Schema types, per-control choices, frontend rendering, impact text |
| **B** — UX Enhancements | Tasks 11–18 | Before/after, smart defaults, rollback, timing, blast radius, escape hatches, post-apply card, exceptions |
| **Total** | 18 tasks | Full interactive remediation experience |
