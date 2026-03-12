# Handoff-Free Closure

This feature makes remediation closure self-serve for engineering by attaching implementation artifacts, closure checklist state, evidence pointers, and provider-agnostic PR automation outputs directly to action detail and remediation-run detail responses.

## Status

Implemented in Phase 3 P0.8 and extended in Phase 3 P1.3.

## Implemented source files

- `backend/services/remediation_handoff.py`
- `backend/routers/actions.py`
- `backend/routers/remediation_runs.py`
- `backend/workers/jobs/remediation_run.py`
- `frontend/src/components/ActionDetailDrawer.tsx`
- `frontend/src/components/RemediationRunProgress.tsx`

## API contract

### Action detail

`GET /api/actions/{action_id}` now includes additive `implementation_artifacts[]`.

Each item represents one linked remediation output that engineering can act on without reconstructing the run payload:

- `run_id`
- `run_status`
- `run_mode`
- `artifact_key`
- `kind`
- `label`
- `description`
- `href`
- `executable`
- `generated_at`
- `closure_status`
- `metadata`

Current normalized action artifacts:

- `pr_bundle` → engineer-executable bundle link (`/remediation-runs/{run_id}#run-generated-files`)
- `pr_payload` → provider-agnostic PR draft metadata (`/remediation-runs/{run_id}#run-generated-files`)
- `change_summary` → applied-change record (`/remediation-runs/{run_id}#run-activity`)
- `direct_fix` → direct-fix execution record (`/remediation-runs/{run_id}#run-activity`)

### Remediation run detail

`GET /api/remediation-runs/{run_id}` now includes additive `artifact_metadata`.

`artifact_metadata` contains:

- `implementation_artifacts[]`
- `evidence_pointers[]`
- `closure_checklist[]`

The raw `artifacts` payload remains unchanged for backward compatibility.

## Normalization rules

`backend/services/remediation_handoff.py` converts sparse worker artifacts into stable UX-facing metadata:

- `pr_bundle.files[]` becomes a bundle artifact with file-count and format metadata.
- `pr_payload` becomes a non-executable implementation artifact with repository, branch, file-count, and fingerprint metadata.
- `change_summary.changes[]` becomes an applied-change artifact with `applied_at` and `applied_by`.
- `direct_fix` becomes a direct-fix record with `recorded_at`, `post_check_passed`, and log metadata.
- `risk_snapshot`, `pr_bundle_error`, `diff_summary`, `rollback_notes`, `control_mapping_context`, and the run activity log become evidence pointers.
- Terminal runs receive a closure checklist for:
  - implementation artifact recorded
  - evidence pointers attached
  - action closure verified

## UI wiring

The frontend now renders the normalized contract directly:

- `ActionDetailDrawer` shows an `Implementation artifacts` section sourced from `action.implementation_artifacts`.
- `RemediationRunProgress` shows:
  - closure checklist
  - evidence pointers
  - activity logs on the dedicated run page as well as embedded views
- The dedicated remediation-run page intentionally hides the duplicate `Implementation artifacts` card and keeps engineer-facing navigation in the checklist/evidence sections.

Stable anchors are now part of the run-detail page contract:

- `#run-activity`
- `#run-generated-files` when a successful `pr_only` run actually has bundle files to show
- `#run-closure`
- `#run-evidence-{pointer.key}` as the fallback target for evidence cards when no deeper section exists

## Backward compatibility

The contract stays additive and fail-open for existing runs:

- legacy runs with `artifacts = null` return empty normalized lists instead of failing
- pending/running runs do not emit closure checklist items yet
- existing consumers can continue reading the raw `artifacts` object
- checklist/evidence navigation now suppresses dead section links instead of sending users to unrelated pages

## Data flow

```mermaid
flowchart TD
    A["Worker writes raw remediation artifacts"] --> B["build_run_artifact_metadata(...)"]
    B --> C["implementation_artifacts[]"]
    B --> D["evidence_pointers[]"]
    B --> E["closure_checklist[]"]
    C --> F["GET /api/remediation-runs/{id}"]
    D --> F
    E --> F
    C --> G["build_action_implementation_artifacts(...)"]
    G --> H["GET /api/actions/{id}"]
    H --> I["ActionDetailDrawer"]
    F --> J["RemediationRunProgress"]
```

## Related docs

- [Shared Security + Engineering execution guidance](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/shared-execution-guidance.md)
- [Repo-aware PR automation](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/repo-aware-pr-automation.md)
- [Remediation safety model](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-safety-model.md)
- [Backend local-dev notes](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/backend.md)
- [Docs index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/README.md)
