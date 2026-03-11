# Phase 3 P0 Live Validation Summary

- Run ID: `20260309T173444Z-phase3-p0`
- Date: 2026-03-09
- API base: `https://api.valensjewelry.com`
- Tenant used: `67256664-3ff2-4456-a7ea-b8e5f4fb8380` (`Live E2E Tenant`)
- Live tenant admin used: `live.e2e.1773073392@example.com`
- Connected account: `029037611564`
- Account state: `validated`

## What was verified successfully

- `GET /health` was already healthy before the run.
- `GET /api/auth/me` returned `200` using a valid live bearer token for the current tenant admin.
- `GET /api/aws/accounts` returned `200` and showed account `029037611564` in `validated` state.
- `POST /api/aws/accounts/029037611564/ingest-sync` returned `200`.
- `POST /api/actions/compute` returned `202`.
- `POST /api/actions/reconcile` returned `202`.

## What blocked P0 validation

P0.1 through P0.8 require live `actions` data. The live tenant never reached that state.

Observed live result after ingest/compute/reconcile:

- `GET /api/findings?account_id=029037611564&region=eu-north-1` -> `200` with `total=0`
- `GET /api/actions?account_id=029037611564&region=eu-north-1` -> `200` with `total=0`

## Root cause evidence

1. AWS Security Hub is still not subscribed for account `029037611564` in `eu-north-1`.
   Evidence: `notes/securityhub-status.txt`

2. The live worker is creating inventory/shadow states, so there is source risk data in the backend.
   Evidence: `notes/shadow-state-open-controls.txt`

3. Promotion/reconcile is failing in the worker with a duplicate-key error on `finding_shadow_states`, so shadow data is not becoming canonical findings/actions.
   Evidence: `notes/worker-reconcile-error.txt`

## Live impact on P0 scope

Because no live actions exist, the following could not be validated on live:

- P0.1 scoring and ordering
- P0.2 score explainability
- P0.3 toxic-combination prioritization
- P0.4 fail-closed context behavior in action detail
- P0.5 ownership queues
- P0.6 SLA and escalation metadata
- P0.7 execution guidance on action detail
- P0.8 implementation artifacts / handoff-free closure links

## Evidence files

- `evidence/api/p0-11-auth-me.json`
- `evidence/api/p0-12-accounts-list.json`
- `evidence/api/p0-15-ingest-sync.json`
- `evidence/api/p0-17-actions-compute.status`
- `evidence/api/p0-18-actions-reconcile.status`
- `evidence/api/p0-19-findings-list-post-ingest.json`
- `evidence/api/p0-20-actions-list-post-reconcile.json`
- `notes/securityhub-status.txt`
- `notes/shadow-state-open-controls.txt`
- `notes/worker-reconcile-error.txt`

## Conclusion

This live run validated that the platform and account-connection path are up, but it did not validate Phase 3 P0 behavior. The live dataset generation pipeline is still broken before actions are created.

Required before rerun:

1. Fix duplicate-key failure in `reconcile_inventory_shard` / shadow-state promotion.
2. Decide whether live testing depends on Security Hub subscription, or keep the shadow-state path sufficient on its own.
3. Rerun ingest -> compute -> reconcile until `GET /api/actions` returns non-empty data for the live tenant.
