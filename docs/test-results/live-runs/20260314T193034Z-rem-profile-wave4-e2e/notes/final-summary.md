# Remediation-profile Wave 4 Summary

- Wave: `RPW4`
- Date (UTC): `2026-03-14T20:20:00Z`
- Branch tested: `master`
- Environment used: `local on master`
- Frontend URL: `http://localhost:3000`
- Backend URL: `http://127.0.0.1:18002`
- Queue isolation: dedicated ingest/quarantine SQS queues from `evidence/queue/isolated-queue-setup.json`

## Outcome Counts

- Pass: `10`
- Fail: `1`
- Partial: `0`
- Blocked: `1`

## Highest Severity Findings

| Test | Severity | Issue | Tracker Section/Row |
|---|---|---|---|
| `RPW4-06` | `🔴 BLOCKING` | Grouped duplicate differentiation is broken on current `master`: an identical grouped request correctly returns `409`, but materially different override-map and `repo_target` requests both return `500 Internal Server Error` instead of creating distinct runs. | `Scoped remediation-profile Wave 4 matrix / RPW4-06` |

## Core Contract Status

| Test | Status | Contract | Queue/worker proof |
|---|---|---|---|
| `RPW4-01` | `PASS` | Single-run create emits remediation-run schema `v2` with canonical `resolution`. | `Direct` queue capture in `evidence/queue/rpw4-01-receive-message.json` plus worker/result evidence in `evidence/worker/master-worker.log` and `evidence/api/rpw4-01-post-worker-detail.json`. |
| `RPW4-02` | `PASS` | Single-run resend reconstructs schema `v2` payload with canonical `resolution`. | `Direct` queue capture in `evidence/queue/rpw4-02-receive-message.json`. |
| `RPW4-03` | `BLOCKED` | Duplicate guard should distinguish different `profile_id` values. | No testable same-strategy multi-profile case exists in this local seeded runtime; see `evidence/api/rpw4-03-remediation-options.json`. |
| `RPW4-04` | `PASS` | Shared grouped route emits schema `v2` with per-action `action_resolutions`. | `Direct` queue capture in `evidence/queue/rpw4-04-receive-message.json`; worker consumed per-action decisions and failed closed on `review_required_bundle`, confirmed in `evidence/api/rpw4-04-post-worker-detail.json`. |
| `RPW4-05` | `PASS` | `POST /api/action-groups/{group_id}/bundle-run` preserves grouped-route parity, linkage, and `repo_target`. | `Direct` queue capture in `evidence/queue/rpw4-05-receive-message.json` plus successful worker/result evidence in `evidence/api/rpw4-05-post-worker-detail.json`. |
| `RPW4-06` | `FAIL` | Grouped duplicate guard should distinguish override-map and `repo_target` changes. | No queue proof exists because the differentiated requests failed at the API layer with `500`. |
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
- `RPW4-06` is a real product failure, not a missing-evidence gap. The blocking condition is the API behavior itself: differentiated grouped requests return `500` before enqueue.
- UI validation on local master required Playwright CLI route rewriting from the frontend's hardcoded `http://localhost:8000` local API base to `http://127.0.0.1:18002`, plus authenticated header injection using the already validated tenant bearer. This proved the current master UI artifact, but it did not exercise the browser login flow.

## Tracker Maintenance

- Quick Status Board updated: `no`
- Section 8 go-live blocker checkboxes updated: `no`
- Section 9 changelog entries added for retests: `no`

## Wave Exit Decision

- `Stop for fixes`
- Rationale:
  - Gate rule is not met because `RPW4-06` failed.
  - Core queue-v2 tests (`RPW4-01`, `RPW4-04`, `RPW4-05`) all have direct queue proof, so this is not a missing-evidence stop.
  - `RPW4-03` can stay blocked for a future rerun, but the current `RPW4-06` backend regression must be fixed before Wave 5.
