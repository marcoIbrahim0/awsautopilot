# Remediation-profile Wave 4 Summary

- Wave: `RPW4`
- Date (UTC): `2026-03-14T20:20:00Z`
- Branch tested: `master`
- Environment used: `local on master`
- Frontend URL: `http://localhost:3000`
- Backend URL: `http://127.0.0.1:18002`
- Queue isolation: dedicated ingest/quarantine SQS queues from `evidence/queue/isolated-queue-setup.json`

## Outcome Counts

- Pass: `11`
- Fail: `0`
- Partial: `0`
- Blocked: `1`

## Highest Severity Findings

| Test | Severity | Issue | Tracker Section/Row |
|---|---|---|---|
| `RPW4-06` | `🟢 CLOSED` | Original grouped duplicate blocker is closed on the rerun backend at `7d3cd53a`: identical grouped request still returns `409`, the override-different request creates distinct run `9c16746d-099c-4191-9661-26a4fc1b99ea`, and the `repo_target` variant now returns explicit non-`500` `grouped_active_run_conflict` once both grouped anchors are occupied. | `Scoped remediation-profile Wave 4 matrix / RPW4-06 rerun` |

## Core Contract Status

| Test | Status | Contract | Queue/worker proof |
|---|---|---|---|
| `RPW4-01` | `PASS` | Single-run create emits remediation-run schema `v2` with canonical `resolution`. | `Direct` queue capture in `evidence/queue/rpw4-01-receive-message.json` plus worker/result evidence in `evidence/worker/master-worker.log` and `evidence/api/rpw4-01-post-worker-detail.json`. |
| `RPW4-02` | `PASS` | Single-run resend reconstructs schema `v2` payload with canonical `resolution`. | `Direct` queue capture in `evidence/queue/rpw4-02-receive-message.json`. |
| `RPW4-03` | `BLOCKED` | Duplicate guard should distinguish different `profile_id` values. | No testable same-strategy multi-profile case exists in this local seeded runtime; see `evidence/api/rpw4-03-remediation-options.json`. |
| `RPW4-04` | `PASS` | Shared grouped route emits schema `v2` with per-action `action_resolutions`. | Original proof remains in `evidence/queue/rpw4-04-receive-message.json`; rerun proof is `evidence/queue/rpw4-04-rerun-receive-message.json` plus fail-closed worker/result evidence in `evidence/api/rpw4-04-rerun-post-worker-detail.json`. |
| `RPW4-05` | `PASS` | `POST /api/action-groups/{group_id}/bundle-run` preserves grouped-route parity, linkage, and `repo_target`. | Original proof remains in `evidence/queue/rpw4-05-receive-message.json`; rerun proof is `evidence/queue/rpw4-05-rerun-receive-message.json` plus successful worker/result evidence in `evidence/api/rpw4-05-rerun-post-worker-detail.json` and lifecycle proof in `evidence/api/rpw4-05-rerun-group-runs-post-worker-response.json`. |
| `RPW4-06` | `PASS` | Grouped duplicate guard now distinguishes override-map and `repo_target` changes without surfacing internal `500`s. | Rerun API proof in `evidence/api/rpw4-06-rerun-*`: identical request stayed `409`, override-different created distinct run `9c16746d-099c-4191-9661-26a4fc1b99ea`, and repo-target-different returned explicit `409 grouped_active_run_conflict` with conflicting action/run ids. |
| `RPW4-07` | `PASS` | Grouped resend reconstructs `schema_version=2` payload with `action_resolutions`, `group_action_ids`, and `repo_target`. | `Direct` queue capture in `evidence/queue/rpw4-07-receive-message.json`. |
| `RPW4-08` | `PASS` | Legacy schema `v1` remediation runs remain runnable. | `Direct` queue capture in `evidence/queue/rpw4-08-receive-message.json` plus successful worker/result evidence in `evidence/api/rpw4-08-post-worker-detail.json`. |
| `RPW4-09` | `PASS` | Unsupported future schema versions still fail closed. | `Direct` quarantine capture in `evidence/queue/rpw4-09-quarantine-message.json` plus worker log evidence in `evidence/worker/master-worker.log`. |
| `RPW4-10` | `PASS` | `direct_fix` remains unchanged and stays on schema `v1`. | `Direct` queue capture in `evidence/queue/rpw4-10-receive-message.json`. |
| `RPW4-11` | `PASS` | `/actions/[id]` still renders remediation options and PR-bundle preview on current master. | `Direct` UI artifacts in `evidence/screenshots/` and `evidence/ui/`; console showed `0` errors in `evidence/ui/rpw4-11-preview-console.log`. |
| `RPW4-12` | `PASS` | Resend safeguards, rate limits, and tenant/auth boundaries remain intact. | `Direct` API responses in `evidence/api/rpw4-12-*`. |

## Exact Contracts Proven

- Single-run `pr_only` create and resend both emit remediation-run schema `v2` with canonical `resolution`, while persisted artifacts keep the canonical resolution fields.
- Grouped create, grouped resend, and action-groups parity all emit remediation-run schema `v2` with `group_action_ids` and per-action `action_resolutions`.
- Grouped worker consumption is resolution-aware on current `master`: the mixed grouped run failed closed specifically because one per-action resolution resolved to `review_required_bundle`, not because of a shared grouped strategy shortcut.
- Legacy schema `v1` remediation-run messages still resend and execute successfully.
- Unsupported future schema versions are quarantined and not processed.
- `direct_fix` preview/create behavior remains unchanged, does not require `profile_id`, and still uses the legacy schema `v1` queue path.
- The action-detail UI on current master renders the remediation surface and PR-bundle preview when exercised through the local Playwright CLI harness against the isolated master backend.
- Resend rate limiting and tenant isolation remained intact across resend, grouped shared-route, and action-groups entrypoints.

## Missing Evidence Or Blockers

- `RPW4-03` remains `BLOCKED`: the local seeded dataset does not expose a route where two otherwise-equivalent requests can vary only by valid `profile_id` under the same strategy family. The captured remediation-options payload shows one profile per strategy, with `profile_id == strategy_id`.
- `RPW4-06` is closed by the rerun against `7d3cd53a`. The original `500` artifacts remain preserved for traceability, but the latest authoritative outcome is non-`500` for every differentiated request.
- UI validation on local master required Playwright CLI route rewriting from the frontend's hardcoded `http://localhost:8000` local API base to `http://127.0.0.1:18002`, plus authenticated header injection using the already validated tenant bearer. This proved the current master UI artifact, but it did not exercise the browser login flow.

## Tracker Maintenance

- Quick Status Board updated: `no`
- Section 8 go-live blocker checkboxes updated: `no`
- Section 9 changelog entries added for retests: `no`

## Wave Exit Decision

- `Ready for Wave 5`
- Rationale:
  - Gate rule is met on the targeted rerun: `RPW4-06` is now `PASS`, `RPW4-04` rerun remains `PASS`, `RPW4-05` rerun remains `PASS`, and no new blocking regression appeared.
  - `RPW4-03` remains data-limited in this local dataset, but it is not part of the blocker-closure gate requested for Wave 5 readiness.
  - Original failure artifacts are preserved, and the rerun addendum below records the authoritative fixed-backend outcome.

## Rerun Addendum (2026-03-14T21:02:03Z)

- Commit/environment used: `local on master with restarted backend` at `http://127.0.0.1:18003`; `evidence/api/rpw4-rerun-environment.json` proves `HEAD=7d3cd53a` and the isolated rerun queues from `evidence/queue/rpw4-rerun-queue-setup.json`.
- `RPW4-06` closure: `closed`. Identical grouped request stayed `409`, override-different request created distinct run `9c16746d-099c-4191-9661-26a4fc1b99ea`, and repo-target-different returned explicit `409 grouped_active_run_conflict` with no internal `500`.
- Wave 4 readiness for Wave 5: `yes`.
- Residual blocker: `none` for the scoped Wave 4 gate. `RPW4-03` remains a separate local-dataset coverage gap, but it is not blocking the requested closeout.
