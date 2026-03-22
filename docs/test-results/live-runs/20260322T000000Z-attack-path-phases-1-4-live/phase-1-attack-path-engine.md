# Phase 1 - Attack Path Engine

- Phase: `1`
- Goal: verify the graph-native path engine and bounded fail-closed behavior on production SaaS
- Status: `PASS`
- Severity: `none`

## Outcome

The representative available action/path pair is now consistent across:

- `GET /api/actions/84a23bb8-d6f7-4c1b-87ff-87f9cc7c469c`
- `GET /api/actions/attack-paths?limit=10`
- `GET /api/actions/attack-paths/path:d9fe1bdfe359b424fa61`
- `https://ocypheris.com/attack-paths`

The action-detail negative path remains explicit on the retained partial action example, while a safe shared-path `unavailable/context_incomplete` live case remains `BLOCKED` by data availability rather than product failure.

## Checks executed

1. Revalidated the available action detail and confirmed `path_id=path:d9fe1bdfe359b424fa61`.
2. Revalidated the production shared-path list and confirmed it returned `200` within the bounded list window.
3. Revalidated the representative shared-path detail and confirmed it returned `200`.
4. Revalidated the browser `/attack-paths` route and confirmed it rendered the ranked list plus shared detail pane.
5. Preserved the live-data guard: no synthetic unavailable/context-incomplete shared path was created.

## Key evidence

- API summary:
  - [20260322T141822Z-phase-rerun-api-summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/api/20260322T141822Z-phase-rerun-api-summary.json)
- Ranked list render:
  - [20260322T141822Z-attack-paths-list-loaded.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/screenshots/20260322T141822Z-attack-paths-list-loaded.png)
- Shared detail render:
  - [20260322T141822Z-attack-path-detail-root-path.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/screenshots/20260322T141822Z-attack-path-detail-root-path.png)

## Notes

- `BLOCKED`: a safe production shared-path example for `unavailable` or `context_incomplete` still was not present in the retained tenant/account pair.
- Non-blocking risk: the shared-path detail request remained slow in production (`~22s` on the representative root-path detail).
