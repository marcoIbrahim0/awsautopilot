# Wave 0 Legacy Compatibility Baseline

> Scope date: 2026-03-14
>
> ⚠️ Status: Historical runtime baseline captured from shipped code paths on 2026-03-14. This is the Wave 0 compatibility lock for later remediation-profile-resolution work, not the live 2026-03-19 contract.
>
> Current contract note (2026-03-19): current `master` rejects `direct_fix`, does not expose customer `WriteRole`, and keeps these references only as compatibility-history context.

This document records the current legacy behavior that still matters for remediation run artifacts, duplicate detection, resend behavior, and grouped-run identity. It is intentionally descriptive, not prescriptive.

Related docs:

- [Remediation Profile Resolution](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/README.md)
- [Remediation Safety Model](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-safety-model.md)
- [Repo-Aware PR Automation](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/repo-aware-pr-automation.md)

## Legacy mirror fields

### `selected_strategy`

Current writers:

- `POST /api/remediation-runs` writes `artifacts["selected_strategy"]` before the run is committed and also mirrors the value into the SQS payload (`backend/routers/remediation_runs.py:1334-1418`).
- `POST /api/remediation-runs/group-pr-bundle` writes the same artifact key and mirrors it into the grouped SQS payload (`backend/routers/remediation_runs.py:1783-1842`).
- `POST /api/action-groups/{group_id}/bundle-run` writes the same artifact key and mirrors it into the grouped SQS payload (`backend/routers/action_groups.py:370-423`).
- The remediation worker re-persists `selected_strategy` onto the run after PR bundle generation, even when it recovered the value from the queue payload or from existing artifacts (`backend/workers/jobs/remediation_run.py:1227-1238`, `backend/workers/jobs/remediation_run.py:1349-1362`).

Current readers:

- Duplicate detection for single-action runs compares `run.artifacts["selected_strategy"]` to the incoming request signature (`backend/routers/remediation_runs.py:140-171`).
- Resend reconstructs the queued remediation job from `run.artifacts["selected_strategy"]` (`backend/routers/remediation_runs.py:2996-3028`).
- The remediation worker falls back from `job["strategy_id"]` to `run.artifacts["selected_strategy"]` when generating a PR bundle (`backend/workers/jobs/remediation_run.py:1144-1163`).
- The SaaS executor uses `artifacts["selected_strategy"]` when it rebuilds the manual high-risk marker for root-credential-gated runs (`backend/workers/jobs/remediation_run_execution.py:354-365`).

Verification: verified.

### `strategy_inputs`

Current writers:

- `POST /api/remediation-runs` writes `artifacts["strategy_inputs"]` after validation and mirrors the same object into the SQS payload (`backend/routers/remediation_runs.py:1334-1418`).
- `POST /api/remediation-runs/group-pr-bundle` writes the same artifact key and mirrors it into the grouped SQS payload (`backend/routers/remediation_runs.py:1783-1842`).
- `POST /api/action-groups/{group_id}/bundle-run` writes the same artifact key and mirrors it into the grouped SQS payload (`backend/routers/action_groups.py:370-423`).
- The remediation worker re-persists `strategy_inputs` onto the run after generation (`backend/workers/jobs/remediation_run.py:1227-1238`, `backend/workers/jobs/remediation_run.py:1349-1362`).

Current readers:

- Duplicate detection for single-action runs compares `run.artifacts["strategy_inputs"]` to the incoming request signature (`backend/routers/remediation_runs.py:140-171`).
- Resend reconstructs the queued remediation job from `run.artifacts["strategy_inputs"]` (`backend/routers/remediation_runs.py:2996-3028`).
- The remediation worker falls back from `job["strategy_inputs"]` to `run.artifacts["strategy_inputs"]` when generating a PR bundle (`backend/workers/jobs/remediation_run.py:1157-1163`).
- The SaaS executor derives `change_summary.changes[]` from `run.artifacts["strategy_inputs"]` during apply completion (`backend/workers/jobs/remediation_run_execution.py:306-351`). The current regression coverage for that behavior is `tests/test_remediation_run_execution.py:200-230`.

Verification: verified.

### `pr_bundle_variant`

Current writers:

- `POST /api/remediation-runs` writes `artifacts["pr_bundle_variant"]` and mirrors it into the SQS payload when the request provided a legacy variant (`backend/routers/remediation_runs.py:1334-1418`).
- `POST /api/remediation-runs/group-pr-bundle` writes the same artifact key and mirrors it into the grouped SQS payload (`backend/routers/remediation_runs.py:1783-1842`).
- `POST /api/action-groups/{group_id}/bundle-run` writes the same artifact key and mirrors it into the grouped SQS payload (`backend/routers/action_groups.py:370-423`).
- The remediation worker re-persists `pr_bundle_variant` onto the run after generation (`backend/workers/jobs/remediation_run.py:1227-1238`, `backend/workers/jobs/remediation_run.py:1349-1362`).

Current readers:

- Duplicate detection for single-action runs compares `run.artifacts["pr_bundle_variant"]` to the incoming request signature (`backend/routers/remediation_runs.py:140-171`).
- Resend reconstructs the queued remediation job from `run.artifacts["pr_bundle_variant"]` (`backend/routers/remediation_runs.py:2996-3028`).
- The remediation worker falls back from `job["pr_bundle_variant"]` to `run.artifacts["pr_bundle_variant"]` when selecting the effective bundle variant (`backend/workers/jobs/remediation_run.py:1144-1150`).

Additional request-side compatibility behavior:

- `POST /api/remediation-runs` and `POST /api/remediation-runs/group-pr-bundle` still map legacy `pr_bundle_variant` values into `strategy_id` through `map_legacy_variant_to_strategy()` (`backend/routers/remediation_runs.py:934-976`, `backend/routers/remediation_runs.py:1545-1586`, `backend/services/remediation_strategy.py:1758-1768`).
- `POST /api/action-groups/{group_id}/bundle-run` does not perform that mapping or validation. It stores and forwards the raw `pr_bundle_variant` directly (`backend/routers/action_groups.py:387-423`).

Verification: verified.

All three legacy mirror fields above are traced to at least one current writer and one current reader.

## Current consumers

- Single-action duplicate detection reads legacy mirror fields directly from `remediation_runs.artifacts`; the signature check currently depends on `selected_strategy`, `strategy_inputs`, `pr_bundle_variant`, and `repo_target` remaining at their existing top-level artifact keys (`backend/routers/remediation_runs.py:140-171`).
- Resend reconstructs queue payloads from stored artifacts instead of recalculating them from live resolver state. It currently reads `selected_strategy`, `strategy_inputs`, `pr_bundle_variant`, `risk_acknowledged`, and grouped `action_ids` from the stored run row (`backend/routers/remediation_runs.py:2996-3028`).
- The remediation worker treats queue payload fields as advisory and falls back to stored artifact mirrors when the job omits them. That fallback is active for `selected_strategy`, `strategy_inputs`, `pr_bundle_variant`, `risk_acknowledged`, grouped `action_ids`, grouped reporting callback metadata, and `repo_target` (`backend/workers/jobs/remediation_run.py:1144-1193`, `backend/workers/jobs/remediation_run.py:1227-1284`).
- Grouped bundle execution prefers `group_bundle.resolved_action_ids` when present, falls back to `group_bundle.action_ids` otherwise, and uses `group_bundle.group_run_id` when reconnecting execution results to `ActionGroupRun` rows (`backend/workers/jobs/remediation_run_execution.py:368-470`).
- Additional grouped-run consumers outside generation still parse `group_bundle.action_ids` directly:
  - resend (`backend/routers/remediation_runs.py:777-790`, `backend/routers/remediation_runs.py:3013-3015`)
  - legacy group-run backfill (`backend/workers/jobs/backfill_action_groups.py:62-84`)
  - post-apply reconcile targeting (`backend/workers/services/post_apply_reconcile.py:57-78`)
- `backend/services/remediation_handoff.py` does not read the legacy mirror fields directly. Its current repo-aware consumer path reads `pr_payload.repo_target` from generated PR automation artifacts instead (`backend/services/remediation_handoff.py:133-160`).

## Duplicate-detection behavior

### Single-run requests: `POST /api/remediation-runs`

- Candidate scan scope is `tenant_id + action_id`, filtered to runs that are either:
  - in an active status (`pending`, `running`, `awaiting_approval`), or
  - recent enough for the relevant window (`backend/routers/remediation_runs.py:1193-1215`)
- Any active run for the same action causes an immediate `409 duplicate_active_run`, regardless of strategy, inputs, variant, or repo target (`backend/routers/remediation_runs.py:1216-1239`).
- `pr_only` runs use a 20-minute window with two `429` rate limits:
  - total queued PR bundles for the action: `6`
  - identical PR bundle signatures for the action: `3`
- The current identical `pr_only` signature is:
  - `mode`
  - `selected_strategy`
  - `strategy_inputs`
  - `pr_bundle_variant`
  - `repo_target`
- Historical baseline only: `direct_fix` runs used a 30-second recent-identical window. A matching signature returned `409 duplicate_recent_request` (`backend/routers/remediation_runs.py:1241-1332`).
- The race-path integrity check after insert only re-checks for another active run, not for another recent identical completed request (`backend/routers/remediation_runs.py:1372-1403`).

### Grouped requests: `POST /api/remediation-runs/group-pr-bundle`

- Group identity is currently the derived filter key `action_type|account_id|region-or-global|status`, for example `s3_bucket_block_public_access|123456789012|eu-north-1|open`.

- The duplicate check scans pending `pr_only` runs for the tenant and only blocks when both values match:
  - `run.artifacts.group_bundle.group_key`
  - `run.artifacts.repo_target`
- The grouped duplicate check does not compare:
  - `selected_strategy`
  - `strategy_inputs`
  - `pr_bundle_variant`
  - `risk_acknowledged`
  - concrete `action_ids`
- There is no separate recent-window grouped rate limit in this route today (`backend/routers/remediation_runs.py:1744-1779`).

### Grouped requests: `POST /api/action-groups/{group_id}/bundle-run`

- This route does not run the `remediation_runs` duplicate logic and does not implement its own duplicate or rate-limit check before enqueue (`backend/routers/action_groups.py:300-423`).
- The route request model has no `repo_target` field, so `repo_target` does not participate in identity on this path (`backend/routers/action_groups.py:113-117`).
- The route writes `strategy_id`, `strategy_inputs`, `risk_acknowledged`, and `pr_bundle_variant` directly into artifacts and the queue payload without the `validate_strategy()`, `validate_strategy_inputs()`, or legacy-variant mapping path used by `backend/routers/remediation_runs.py` (`backend/routers/action_groups.py:387-423`).
- Identity is effectively the persisted `ActionGroup` row plus the membership snapshot loaded at request time:
  - `group.id`
  - `group.group_key`
  - the ordered member `action_ids`

## Resend/requeue behavior

- The only explicit remediation-run requeue path in the inspected code is `POST /api/remediation-runs/{run_id}/resend` (`backend/routers/remediation_runs.py:2892-3055`).
- Resend is allowed only while the run is still `pending`.
- Resend rate limit:
  - tracked in `artifacts.queue_resend_attempts`
  - maximum `3` resend attempts in `20` minutes for the same run
- Resend reconstructs the queue payload from the persisted run row, not from the original HTTP request. It currently copies:
  - `run.id`
  - `run.tenant_id`
  - `run.action_id`
  - `run.mode`
  - `artifacts.pr_bundle_variant`
  - `artifacts.selected_strategy`
  - `artifacts.strategy_inputs`
  - `artifacts.risk_acknowledged`
  - `artifacts.group_bundle.action_ids`
- Resend does not include `repo_target` in the reconstructed queue payload, even though the builder supports it (`backend/routers/remediation_runs.py:3017-3028`, `backend/utils/sqs.py:335-373`).
- Current compatibility is preserved because the worker reconstructs missing fields from stored artifacts:
  - `repo_target` falls back from `job["repo_target"]` to `run.artifacts["repo_target"]` (`backend/workers/jobs/remediation_run.py:205-211`, `backend/workers/jobs/remediation_run.py:1172`)
  - grouped `action_ids` fall back from `job["group_action_ids"]` to `run.artifacts.group_bundle.action_ids` (`backend/workers/jobs/remediation_run.py:1178-1193`)
  - action-group callback state falls back from `run.artifacts.group_bundle.reporting` (`backend/workers/jobs/remediation_run.py:1181-1192`)

## Grouped-run identity and artifacts

### `group_bundle` seeded by `POST /api/remediation-runs/group-pr-bundle`

The execution-group route currently seeds these keys (`backend/routers/remediation_runs.py:1783-1792`):

| Key | Current value |
| --- | --- |
| `group_key` | Filter-derived string such as `s3_bucket_block_public_access|123456789012|eu-north-1|open` |
| `action_type` | Request `action_type` |
| `account_id` | Request `account_id` |
| `region` | Request `region`, or `null` when `region_is_null=true` |
| `status` | Lowercased request `status` |
| `action_count` | Number of matched actions |
| `action_ids` | Ordered matched action IDs |

Notes:

- `repo_target` is not nested under `group_bundle`; it remains a separate top-level artifact key (`backend/routers/remediation_runs.py:1806-1807`).
- On this path, grouped identity for duplicate detection is `group_bundle.group_key + artifacts.repo_target` (`backend/routers/remediation_runs.py:1744-1779`).

### `group_bundle` seeded by `POST /api/action-groups/{group_id}/bundle-run`

The action-group route currently seeds a richer structure (`backend/routers/action_groups.py:370-385`):

| Key | Current value |
| --- | --- |
| `group_id` | Persisted `ActionGroup.id` |
| `group_key` | Persisted `ActionGroup.group_key` |
| `action_type` | Persisted `ActionGroup.action_type` |
| `account_id` | Persisted `ActionGroup.account_id` |
| `region` | Persisted `ActionGroup.region` |
| `action_count` | Number of current group members |
| `action_ids` | Ordered member action IDs |
| `group_run_id` | Newly created `ActionGroupRun.id` |
| `reporting.callback_url` | `API_PUBLIC_URL.rstrip('/') + '/api/internal/group-runs/report'` |
| `reporting.token` | Issued group-run reporting token |
| `reporting.reporting_source` | Literal `bundle_callback` |

Notes:

- This route does not currently support `repo_target` at all (`backend/routers/action_groups.py:113-117`).
- The route also does not seed a `status` field inside `group_bundle`; that field exists only on `/group-pr-bundle`.

### Worker-enriched grouped artifact fields

After grouped PR generation, the remediation worker may add these keys under `group_bundle` (`backend/workers/jobs/remediation_run.py:1239-1283`):

- `resolved_action_ids`
- `resolved_action_count`
- `missing_action_count`
- `runner_template_source`
- `runner_template_version`
- `generated_action_count`
- `skipped_action_count`
- `skipped_actions`
- `diff_fingerprint_sha256`
- `repo_target_configured`
- `repo_repository`
- `repo_base_branch`
- `repo_head_branch`
- `repo_root_path`

Current grouped execution behavior depends on those additions:

- executor planning/apply uses `resolved_action_ids` first and falls back to `action_ids` (`backend/workers/jobs/remediation_run_execution.py:377-398`)
- executor-to-`ActionGroupRun` linking uses `group_run_id` when present (`backend/workers/jobs/remediation_run_execution.py:412-469`)

### Repo-target participation in grouped identity

- `repo_target` participates in grouped identity only on `POST /api/remediation-runs/group-pr-bundle`, and only as a top-level artifact comparison paired with `group_bundle.group_key` (`backend/routers/remediation_runs.py:1759-1764`).
- `repo_target` does not participate in grouped identity on `POST /api/action-groups/{group_id}/bundle-run` because that route has no `repo_target` request field and never writes `artifacts.repo_target` (`backend/routers/action_groups.py:113-117`, `backend/routers/action_groups.py:370-423`).
- During resend and worker replay, grouped repo-aware behavior depends on the worker's fallback to `run.artifacts.repo_target`, not on `group_bundle` (`backend/workers/jobs/remediation_run.py:205-211`).

## Compatibility risks if these fields change too early

- Removing or renaming `selected_strategy`, `strategy_inputs`, or `pr_bundle_variant` before their readers are migrated will break live duplicate detection, resend reconstruction, and worker fallback, because all three behaviors still read those exact top-level artifact keys.
- Changing `strategy_inputs` semantics early also changes apply-time evidence. The current SaaS executor converts `strategy_inputs` directly into `change_summary.changes[]`, so an early format change is not only runtime-sensitive but audit-surface-sensitive (`backend/workers/jobs/remediation_run_execution.py:306-351`).
- Treating `pr_bundle_variant` as a fully deprecated input is unsafe in Wave 0 because the two `remediation-runs` create routes still map it into `strategy_id`, while the `action-groups` bundle route still stores and forwards the raw variant without that mapping.
- Collapsing grouped identity onto only strategy or resolution data too early will not match current behavior. The two grouped routes do not share one identity model today:
  - `/group-pr-bundle` uses a filter-derived `group_key` plus top-level `repo_target`
  - `/action-groups/{group_id}/bundle-run` uses persisted group identity, explicit `group_run_id`, and callback reporting metadata, with no repo-target support and no duplicate guard
- Moving `repo_target` out of its current top-level artifact position too early will break the current grouped duplicate check and the worker replay path. Resend does not reserialize `repo_target`; it survives today only because the worker falls back to `run.artifacts.repo_target`.
- Changing `group_bundle.action_ids`, `group_bundle.resolved_action_ids`, or `group_bundle.group_run_id` too early will affect more than bundle generation. Those keys are already consumed by resend, grouped execution, grouped reporting linkage, backfill repair, and post-apply reconcile targeting.
