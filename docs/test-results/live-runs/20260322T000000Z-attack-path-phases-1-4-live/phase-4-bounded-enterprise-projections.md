# Phase 4 - Bounded Enterprise Projections

- Phase: `4`
- Goal: verify only the shipped bounded Phase 4 projection slice on production SaaS
- Status: `PASS`
- Severity: `none`

## Outcome

The representative shared-path detail now returns and renders the shipped bounded Phase 4 projection fields:

- `runtime_signals`
- `exposure_validation`
- `code_context`
- `closure_targets`
- `external_workflow_summary`
- `exception_summary`
- `evidence_exports`
- `access_scope`

`linked_repositories` and `implementation_artifacts` were empty for the representative root-path record, and the UI correctly rendered bounded fallback text instead of a broken or empty surface.

## Checks executed

1. Loaded `GET /api/actions/attack-paths/path:d9fe1bdfe359b424fa61` and confirmed all bounded Phase 4 projection sections were present.
2. Confirmed the browser detail pane rendered runtime truth, rank factors, code-to-cloud fallback, closure targets, evidence, and workflow controls.
3. Confirmed the surface stayed projection-only: no path-level mutation controls were presented.
4. Kept the overclaim guard: the run does not claim proof for deeper runtime collection, stricter RBAC masking, or expanded graph taxonomy beyond the shipped bounded fields.

## Key evidence

- API summary:
  - [20260322T141822Z-phase-rerun-api-summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/api/20260322T141822Z-phase-rerun-api-summary.json)
- Shared detail render:
  - [20260322T141822Z-attack-path-detail-root-path.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/screenshots/20260322T141822Z-attack-path-detail-root-path.png)
- Shared detail network trace:
  - [20260322T141822Z-attack-path-detail-root-path.network.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/api/20260322T141822Z-attack-path-detail-root-path.network.log)

## Notes

- Overclaim guard remains in force:
  - do not treat this run as proof of a separate runtime collector
  - do not treat this run as proof of stricter RBAC masking
  - do not treat this run as proof of broader graph-taxonomy expansion beyond the bounded projection slice
