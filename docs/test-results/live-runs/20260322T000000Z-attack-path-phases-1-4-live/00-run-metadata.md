# Live Attack Path Phases 1-4 Run Metadata

- Run ID: `20260322T000000Z-attack-path-phases-1-4-live`
- Created at (UTC): `2026-03-22T13:17:49Z`
- Retest completed at (UTC): `2026-03-22T14:18:22Z`
- Frontend URL: `https://ocypheris.com`
- Backend URL: `https://api.ocypheris.com`

## Authenticated identity

- Primary test user: `marco.ibrahim@ocypheris.com`
- Tenant id: `9f7616d8-af04-43ca-99cd-713625357b70`
- Tenant label: `Valens`

## Preferred live dataset

- Preferred account id: `696505809372`
- Preferred region: `eu-north-1`
- Representative available action id: `84a23bb8-d6f7-4c1b-87ff-87f9cc7c469c`
- Representative available path id: `path:d9fe1bdfe359b424fa61`
- Representative partial action id: `0abc603d-b75a-4b49-9a5f-431a0aa82a4e`
- Representative partial path id: `path:96bdb7a6b4e43c63343c`
- Representative unavailable/context-incomplete action id: `BLOCKED`
- Representative unavailable/context-incomplete path id: `BLOCKED`

> ❓ Needs verification: production still lacks a safe `unavailable` or `context_incomplete` shared-path example for the retained tenant/account pair. Keep that proof point `BLOCKED` rather than synthesizing data.

## Current run verdict

- Overall result: `PASS`
- Release recommendation: `GO`
- Residual risk: shared-path list and detail latency remain high in production (`~9s` list, `~22s` detail for the representative root-path record).

## Phase status tracker

| Phase | Status | Notes |
|---|---|---|
| 1 | `PASS` | available action/path pair is now consistent across action detail, shared list/detail, and browser rendering; the explicit unavailable/context-incomplete shared-path proof remains `BLOCKED` by live data availability |
| 2 | `PASS` | `path_id` resolves through shared detail; ranking, freshness, evidence, and linked actions render; multi-action shared-path proof remains `BLOCKED` by live data availability |
| 3 | `PASS` | `/attack-paths` renders the ranked list, filters, preset views, and detail pane without console/runtime errors |
| 4 | `PASS` | bounded runtime, code-to-cloud, closure, workflow, exception, evidence-export, and access-scope projections render on the shared detail surface |

## Retained rerun evidence

- Compact API summary:
  - [20260322T141822Z-phase-rerun-api-summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/api/20260322T141822Z-phase-rerun-api-summary.json)
- Ranked list UI:
  - [20260322T141822Z-attack-paths-list-loaded.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/screenshots/20260322T141822Z-attack-paths-list-loaded.png)
  - [20260322T141822Z-attack-paths-list-loaded.console.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/ui/20260322T141822Z-attack-paths-list-loaded.console.log)
  - [20260322T141822Z-attack-paths-list-loaded.network.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/api/20260322T141822Z-attack-paths-list-loaded.network.log)
- Representative shared detail UI:
  - [20260322T141822Z-attack-path-detail-root-path.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/screenshots/20260322T141822Z-attack-path-detail-root-path.png)
  - [20260322T141822Z-attack-path-detail-root-path.console.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/ui/20260322T141822Z-attack-path-detail-root-path.console.log)
  - [20260322T141822Z-attack-path-detail-root-path.network.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/api/20260322T141822Z-attack-path-detail-root-path.network.log)
