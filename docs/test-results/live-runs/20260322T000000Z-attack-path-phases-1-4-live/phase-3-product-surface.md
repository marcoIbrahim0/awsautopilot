# Phase 3 - Product Surface

- Phase: `3`
- Goal: verify the bounded `/attack-paths` workflow as a daily operator surface on production SaaS
- Status: `PASS`
- Severity: `none`

## Outcome

`/attack-paths` now renders in production as the bounded triage surface:

- ranked list
- filters
- preset bounded views
- shared detail pane
- linked-action remediation rollup

Preset selection was verified by changing the route to `view=actively_exploited` and observing the bounded route/query-state update without console/runtime failures.

## Checks executed

1. Loaded `https://ocypheris.com/attack-paths` in an authenticated session and confirmed the ranked list rendered.
2. Confirmed the list returned `10` bounded rows on the retained dataset.
3. Confirmed the detail pane rendered for the selected shared path.
4. Clicked the `Actively exploited` preset and confirmed the route changed to include `view=actively_exploited`.
5. Confirmed console output remained clean for the rerun capture set.

## Key evidence

- List render:
  - [20260322T141822Z-attack-paths-list-loaded.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/screenshots/20260322T141822Z-attack-paths-list-loaded.png)
- List console:
  - [20260322T141822Z-attack-paths-list-loaded.console.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/ui/20260322T141822Z-attack-paths-list-loaded.console.log)
- API + preset summary:
  - [20260322T141822Z-phase-rerun-api-summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/api/20260322T141822Z-phase-rerun-api-summary.json)

## Notes

- Non-blocking risk: the initial ranked-list load remains noticeably slow in production (`~9s-11s` in the retained rerun).
