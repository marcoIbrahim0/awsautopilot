# Item 17 Medium/Low-Confidence Control Coverage Plan

Cross-reference:
- [Important To Do - Item 17](important-to-do.md#17-expand-mediumlow-confidence-rule-pattern-coverage-and-test-scenarios)
- [Reconciliation Quality Review](../reconciliation_quality_review.md)
- [Item 16 High-Confidence Rollout](16-high-confidence-live-status-rollout.md)

> ⚠️ Status: In progress (2026-03-02) — Item `17` gating + regression validation are complete for current scope, while matrix-closure checks and low-tier live verification evidence remain required before medium/low rollout expansion.

> ✅ Progress update (2026-03-02): Implemented collector/enrichment edge-case handling in `backend/workers/services/inventory_reconcile.py` and `backend/workers/services/control_plane_events.py` for medium/low-confidence controls (`SecurityHub.1`, `GuardDuty.1`, `S3.2`, `S3.4`, `S3.5`, `S3.9`, `S3.11`, `CloudTrail.1`, `Config.1`, `SSM.7`, `EC2.53`) with explicit branch contracts for normal/access-denied/partial-data/API-error paths. Tests in `tests/test_inventory_reconcile.py` and `tests/test_control_plane_events.py` now assert deterministic `state_confidence`, `status_reason`, and evidence branch markers.
>
> ✅ Progress update (2026-03-02, follow-up): Added worker-level integration coverage in `tests/test_reconcile_inventory_shard_worker.py` for `execute_reconcile_inventory_shard_job` with deterministic assertions across unsupported/targeted-empty skip branches, mixed apply/change success behavior, failed shard tracking, and authoritative `compute_actions` enqueue gating.
>
> ✅ Validation update (2026-03-02 closure): Re-ran Item `16/17` targeted suites (`tests/test_shadow_state.py`, `tests/test_saas_admin_api.py`, `tests/test_inventory_reconcile.py`, `tests/test_control_plane_events.py`, `tests/test_reconcile_inventory_shard_worker.py`) with `131 passed`, and full backend regression (`pytest -q`) with `914 passed`.
>
> Remaining scope focuses on low-tier live verification evidence capture and operator-fed observed quality metrics before medium/low promotion scope expansion.

## Scope

- This matrix is based on the current implementation in [`backend/workers/services/inventory_reconcile.py`](../../backend/workers/services/inventory_reconcile.py) and current tests in [`tests/test_inventory_reconcile.py`](../../tests/test_inventory_reconcile.py).
- The controls below are treated as medium/low-confidence for Item `17` planning based on current rule-branch maturity and test depth.
- Out of scope for this task: promotion logic/config changes in `shadow_state` and `config` (Item `16` behavior remains unchanged).

## Control Matrix

| Control (tier) | Current rule patterns handled | Missing edge cases | Current test coverage gaps | Done criteria (must all pass) |
| --- | --- | --- | --- | --- |
| `SecurityHub.1` (Low) | `describe_hub` drives `RESOLVED`/`OPEN`; `AccessDenied*` drives `SOFT_RESOLVED` (`40`) with explicit reason. | No live-verified shadow join for recurring `SecurityHub.1` finding; no explicit handling test for empty `HubArn` response. | Only happy-path `RESOLVED` identity test exists. | Add tests for `AccessDenied*` soft path, not-enabled path, and unknown-error re-raise; add one integration test asserting attach/join against an account-scoped finding; record one live verification artifact. |
| `GuardDuty.1` (Medium) | Paginates `list_detectors`; evaluates all detector statuses; per-detector `AccessDenied*` downgrades to `SOFT_RESOLVED` (`40`). | `list_detectors` access-denied branch and invalid-input-only branch are not validated by tests; mixed detector outcomes need explicit policy assertion. | No test for `list_detectors` access denied, invalid-input-only detector set, or unknown `ClientError` re-raise. | Add tests for all untested branches (`list` deny, invalid-only, unknown error); assert evidence counters (`detector_access_denied_count`, `detector_invalid_input_count`) for each branch. |
| `S3.2` (Medium) | Per-bucket posture from bucket PAB + policy-public signal; emits both bucket and account-shaped `S3.2` evaluations with shared status/reason/confidence. | Targeted reconcile using account-only resource IDs can skip bucket evaluation; ACL-only exposure patterns are not explicitly represented in evidence. | Only dual-shape emission happy-path is tested. | Add tests for `OPEN` from public policy and from missing bucket PAB flags; add targeted account-id input test with expected behavior; document or implement ACL evidence handling and cover it in tests. |
| `S3.4` (Medium) | Evaluates all default encryption rules; accepts `{AES256, aws:kms}` case-insensitively; missing encryption config => `OPEN`. | DSSE-KMS/alternate algorithm variants are not explicitly classified; access-denied behavior is not covered by soft fallback. | Algorithm matrix is covered; no tests for missing-config path or API-error behavior. | Add tests for missing encryption config, `ClientError` behavior, and approved/unsupported algorithm variants policy decision; keep reason/status deterministic for each branch. |
| `EC2.53` (Medium) | Normalizes SG IDs from raw and ARN inputs; evaluates world-exposed SSH/RDP on `tcp` and `-1`; skips missing groups safely. | Account-scoped `EC2.53` findings still need explicit handling policy; global-sweep edge behaviors are not validated in this test module. | Targeted ID normalization is tested; no collector-level global-sweep behavior test set. | Add tests for global sweep path and representative violation shapes (`22`, `3389`, IPv4/IPv6, protocol `-1`); define and test account-scoped finding handling policy. |
| `CloudTrail.1` (Low) | Uses `includeShadowTrails=True`; evaluates multi-region logging; per-trail `AccessDenied*` downgrades to `SOFT_RESOLVED` (`40`); `TrailNotFoundException` is skipped. | `describe_trails` access-denied and indeterminate-all-trails behavior need explicit confidence policy validation. | Only per-trail access-denied and happy-path include-shadow tests exist. | Add tests for `describe_trails` access denied, `TrailNotFound`-only, zero-trail, and unknown-error branches; add explicit expectation for indeterminate-all-trails outcome. |
| `Config.1` (Medium) | Requires recorder recording + role ARN + resource coverage (`allSupported` or explicit types) + delivery channel presence/configuration; status-read access denied => `SOFT_RESOLVED` (`40`). | Access denial on recorder or delivery-channel reads is not separately classified; multi-recorder name/status mismatch branch is not stress-tested. | Happy path, basic non-compliant, and status-access-denied branches are covered; role/coverage edge branches are not. | Add tests for missing role ARN, missing resource coverage, multi-recorder mismatch, and delivery-channel read errors; assert evidence booleans for each branch. |
| `SSM.7` (Medium) | Interprets setting tokens (`enabled/true/1/on`) as `OPEN`; unsupported/access-denied => `SOFT_RESOLVED` (`40`); throttling re-raised. | Token normalization branches are not fully asserted; malformed/unknown API response shapes are not explicitly tested. | No explicit test for `OPEN` token branch or deterministic `RESOLVED` branch assertions; no unknown-error re-raise test. | Add tests for each supported open token, resolved token branch, malformed response shape, and unknown `ClientError`; keep status reason stable per branch. |
| `S3.5` (Low) | SSL policy checker requires `Deny` + `aws:SecureTransport=false` + action coverage + both bucket/object resource coverage. | Principal-scope validation is still permissive; alternate equivalent policy patterns are not modeled; missing/malformed policy integration branches are not tested. | Helper tests cover action/resource/condition only; no principal-restriction test or missing-policy integration test. | Add principal-scope tests, alternate-policy-form tests (supported vs unsupported), and integration tests for missing/malformed policy JSON paths with deterministic evidence flags. |
| `S3.11` (Low) | Requires at least one enabled lifecycle rule with meaningful action (`Expiration` or non-empty `Transitions`). | Other meaningful lifecycle actions (for example noncurrent/abort forms) are not currently classified. | Helper function tests exist, but collector-level `S3.11` evaluation behavior is not directly asserted. | Define full accepted lifecycle-action set, then add collector-level tests for `OPEN`/`RESOLVED` and helper-level tests for each accepted action form. |

## Item 17 Exit Conditions

1. Every control row above has all done criteria completed.
2. `tests/test_inventory_reconcile.py` includes explicit branch coverage for each control's `OPEN`, `RESOLVED`, and (when applicable) `SOFT_RESOLVED` paths.
3. Item `17` promotion-gate document updates are complete before any medium/low control is added to `CONTROL_PLANE_HIGH_CONFIDENCE_CONTROLS`.
4. Live verification evidence is captured for controls marked low tier in this matrix (`SecurityHub.1`, `CloudTrail.1`, `S3.5`, `S3.11`).

## Item 17 Promotion Quality Gates (Exact Knobs)

Medium/low canonical promotion now stays fail-closed unless all quality gates are satisfied in the same Item `16` promotion decision path (`backend/workers/services/shadow_state.py`).

| Env var | Type | Default | Required for medium/low promotion |
| --- | --- | --- | --- |
| `CONTROL_PLANE_MEDIUM_LOW_CONFIDENCE_CONTROLS` | `str` (CSV control IDs) | `""` | Must explicitly list medium/low controls to even consider for live promotion. Empty means medium/low never promote. |
| `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_MIN_COVERAGE` | `int` (`0`-`100`) | `95` | Minimum coverage gate. |
| `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_OBSERVED_COVERAGE` | `int` (`0`-`100`) | `0` | Must be `>= CONTROL_PLANE_MEDIUM_LOW_PROMOTION_MIN_COVERAGE`. |
| `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_MIN_PRECISION` | `int` (`0`-`100`) | `95` | Minimum precision gate. |
| `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_OBSERVED_PRECISION` | `int` (`0`-`100`) | `0` | Must be `>= CONTROL_PLANE_MEDIUM_LOW_PROMOTION_MIN_PRECISION`. |
| `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_ROLLBACK_TRIGGERED` | `bool` | `false` | Must be `false`; `true` blocks all medium/low promotion immediately. |

Companion Item `16` guardrails still apply:
- `CONTROL_PLANE_SHADOW_MODE=false`
- `CONTROL_PLANE_AUTHORITATIVE_PROMOTION_ENABLED=true`
- `CONTROL_PLANE_PROMOTION_MIN_CONFIDENCE` gate still enforced per evaluation
- `CONTROL_PLANE_PROMOTION_ALLOW_SOFT_RESOLVED` behavior remains enforced

Stable Item `17` medium/low block reason codes:
- `medium_low_coverage_below_threshold`
- `medium_low_precision_below_threshold`
- `medium_low_rollback_triggered`

## Medium/Low Rollout Process

1. Keep `CONTROL_PLANE_MEDIUM_LOW_CONFIDENCE_CONTROLS=""` while matrix row criteria and low-tier live verification evidence are still incomplete.
2. Measure observed quality from SaaS-admin control-plane metrics and set:
   - `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_OBSERVED_COVERAGE`
   - `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_OBSERVED_PRECISION`
3. Set approved gates (`*_MIN_COVERAGE`, `*_MIN_PRECISION`) and explicitly scope medium/low controls in `CONTROL_PLANE_MEDIUM_LOW_CONFIDENCE_CONTROLS` for pilot tenants first.
4. Promote only while all gates pass and `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_ROLLBACK_TRIGGERED=false`.
5. On any rollback trigger condition, set `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_ROLLBACK_TRIGGERED=true` and redeploy API + worker to fail-close medium/low promotion in one cycle.

> ❓ Needs verification: Do live `S3.4` findings in current tenants ever appear as account-scoped resources (`AwsAccount`) instead of bucket-scoped resources (`AwsS3Bucket`)?
>
> ❓ Needs verification: For targeted reconciliations triggered from account-scoped `S3.2` findings, should the worker auto-expand to all buckets in-region or require explicit bucket IDs?
>
> ❓ Needs verification: For `CloudTrail.1`, when every multi-region trail status read is indeterminate (for example repeated access-denied/not-found mix), should status remain `SOFT_RESOLVED` instead of `OPEN`?
