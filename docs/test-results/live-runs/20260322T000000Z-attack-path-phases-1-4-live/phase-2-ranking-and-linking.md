# Phase 2 - Ranking And Linking

- Phase: `2`
- Goal: verify shared-path identity, explainable ranking, and reusable linking on production SaaS
- Status: `PASS`
- Severity: `none`

## Outcome

The available representative action and shared record now resolve correctly end to end:

- action detail returns `path_id=path:d9fe1bdfe359b424fa61`
- shared-path detail returns `rank`, non-empty `rank_factors`, `linked_actions`, `evidence`, and `provenance`
- `/attack-paths?action_id=84a23bb8-d6f7-4c1b-87ff-87f9cc7c469c&path_id=path:d9fe1bdfe359b424fa61` renders the same shared record

## Checks executed

1. Verified `GET /api/actions/84a23bb8-d6f7-4c1b-87ff-87f9cc7c469c` returned the representative `path_id`.
2. Verified `GET /api/actions/attack-paths/path:d9fe1bdfe359b424fa61` returned `200` with explainable `rank_factors`.
3. Verified the browser detail pane rendered the same rank, summary, linked-action rollup, evidence, and provenance.
4. Preserved the multi-action linkage guard: no safe multi-action shared-path record was proven in this tenant, so that one proof point remains `BLOCKED`.

## Key evidence

- API summary:
  - [20260322T141822Z-phase-rerun-api-summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/api/20260322T141822Z-phase-rerun-api-summary.json)
- Shared detail network trace:
  - [20260322T141822Z-attack-path-detail-root-path.network.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/api/20260322T141822Z-attack-path-detail-root-path.network.log)
- Shared detail render:
  - [20260322T141822Z-attack-path-detail-root-path.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/screenshots/20260322T141822Z-attack-path-detail-root-path.png)

## Notes

- `BLOCKED`: no safe multi-action shared-path record was explicitly proven in the retained live tenant, so the run only proves single-action shared-path reuse.
