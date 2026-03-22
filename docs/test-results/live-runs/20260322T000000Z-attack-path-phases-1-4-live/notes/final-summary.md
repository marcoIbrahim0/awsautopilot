# Final Summary - Attack Path Phases 1-4 Live Run

- Run ID: `20260322T000000Z-attack-path-phases-1-4-live`
- Environment: `production SaaS`
- Frontend: `https://ocypheris.com`
- Backend: `https://api.ocypheris.com`
- Overall result: `PASS`
- Release recommendation: `GO`

## Phase results

| Phase | Title | Status | Notes |
|---|---|---|---|
| 1 | Graph-native path engine | `PASS` | representative available action/path pair is now consistent across action detail, shared list/detail, and browser rendering |
| 2 | Ranking and linking | `PASS` | `path_id` resolves through shared detail with explainable ranking, evidence, provenance, and linked-action projection |
| 3 | Product surface | `PASS` | `/attack-paths` now renders the ranked list, filters, preset views, and detail pane in production |
| 4 | Bounded enterprise projections | `PASS` | runtime truth, exposure validation, code-to-cloud fallback, closure, workflow, exception, evidence-export, and access-scope projections all render on the shared detail surface |

## Proven live dataset

- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70 / Valens`
- Account: `696505809372`
- Region: `eu-north-1`
- Available action/path pair: `84a23bb8-d6f7-4c1b-87ff-87f9cc7c469c` / `path:d9fe1bdfe359b424fa61`
- Partial action/path pair: `0abc603d-b75a-4b49-9a5f-431a0aa82a4e` / `path:96bdb7a6b4e43c63343c`
- Unavailable or context-incomplete pair: `BLOCKED` / `BLOCKED`

## Key findings

- `F1`: the original production rollout failures are fixed. `/attack-paths` is live, `GET /api/actions/attack-paths` returns `200`, and `GET /api/actions/attack-paths/{id}` returns `200`.
- `F2`: the bounded `/attack-paths` surface now renders a real ranked triage list with preset bounded views and shared detail.
- `F3`: the Phase 4 bounded projection slice is live on the shared detail surface, including explicit fallback text when repo-aware linkage is absent.
- `F4`: residual latency is still noticeable in production. The retained rerun observed roughly `~9s-11s` list load and `~22s` representative shared-detail load.

## Non-blocking risks

- Shared-path latency remains high enough that the product feels slow even though it now passes functional acceptance.
- A safe live `unavailable/context_incomplete` shared-path example still was not available for proof, so that one assertion remains `BLOCKED`.
- A safe live multi-action shared-path example still was not available for proof, so that one assertion remains `BLOCKED`.

## Retained evidence

- API summary:
  - [20260322T141822Z-phase-rerun-api-summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/api/20260322T141822Z-phase-rerun-api-summary.json)
- Ranked list render:
  - [20260322T141822Z-attack-paths-list-loaded.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/screenshots/20260322T141822Z-attack-paths-list-loaded.png)
- Representative shared detail render:
  - [20260322T141822Z-attack-path-detail-root-path.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/evidence/screenshots/20260322T141822Z-attack-path-detail-root-path.png)

## Interpretation guard

- This run proves only the shipped bounded Phase 4 projection slice.
- This run does not prove a separate runtime collector, stricter RBAC masking, or broader graph-taxonomy expansion beyond the fields observed in the shared detail payload.
