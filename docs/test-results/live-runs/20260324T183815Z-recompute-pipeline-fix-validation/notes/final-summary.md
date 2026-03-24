# Recompute Pipeline Fix Validation

Date: 2026-03-24 18:38:15 UTC

## Summary

Local current-head validation proved that the recompute pipeline no longer hangs indefinitely on the shared live tenant/account scope.

Verified scope:

- tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- account: `696505809372`
- local target-account credential split:
  - default SaaS-side credentials for queue/runtime access
  - `ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION=true`
  - `LOCAL_TARGET_ACCOUNT_AWS_PROFILE=test28-root`

No deploy was performed.

## What Changed

- Added phase-level timing logs to `compute_actions_for_tenant(...)` and the worker `compute_actions` job.
- Replaced per-action `action_group` membership/state projection with a set-based bulk path.
- Replaced relationship-driven resolve/reopen passes with batched unresolved-count queries.
- Added explicit before/after logging for sync-task dispatch and attack-path enqueue.
- Switched attack-path enqueue to the parsed SQS queue region instead of the generic runtime region.

## Focused Automated Validation

- `PYTHONPATH=. ./venv/bin/pytest tests/test_action_groups_service.py tests/test_action_engine_merge.py tests/test_action_engine_account_scoped_sg.py tests/test_phase3_p1_5_integrations_bidirectional.py -q`
  - `35 passed`
- `PYTHONPATH=. ./venv/bin/python -m py_compile backend/services/action_groups.py backend/services/action_engine.py backend/workers/jobs/compute_actions.py backend/services/integration_sync.py backend/services/attack_path_materialized.py tests/test_action_groups_service.py tests/test_action_engine_merge.py tests/test_phase3_p1_5_integrations_bidirectional.py`
  - passed

## Live Local Recompute Proof

Command:

```bash
set -a; source backend/.env; set +a
unset AWS_PROFILE
export ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION=true
export LOCAL_TARGET_ACCOUNT_AWS_PROFILE=test28-root
PYTHONPATH=. ./venv/bin/python scripts/recompute_account_actions.py \
  --tenant-id 9f7616d8-af04-43ca-99cd-713625357b70 \
  --account-id 696505809372
```

Observed result:

- command completed successfully instead of hanging
- returned:
  - `actions_updated=45`
  - `actions_created=0`
  - `actions_resolved=0`
  - `action_findings_linked=58`
- returned phase timings:
  - `grouping=19380ms`
  - `upsert=14211ms`
  - `group_projection=39713ms`
  - `resolve_reopen=236ms`
  - `security_graph=5891ms`
  - `total=79436ms`

Interpretation:

- the original indefinite hang is fixed
- the remaining dominant cost is still `group_projection`, but it is now a slow, attributable phase rather than an unbounded stall
- security graph is not the primary blocker on this dataset

## Queue Worker Proof

Local worker run:

```bash
unset AWS_PROFILE
export ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION=true
export LOCAL_TARGET_ACCOUNT_AWS_PROFILE=test28-root
PYTHONPATH=. ./venv/bin/python -m backend.workers.main
```

Queued one scoped `compute_actions` job for the same tenant/account on the legacy ingest queue.

Observed evidence that the worker completed `compute_actions`:

- the legacy queue did not stay pinned at the earlier `compute_actions` in-flight symptom
- after the queued compute job, the worker immediately began processing:
  - `job_type=integration_sync`
  - `job_type=attack_path_materialization`
- those follow-on jobs are emitted only after `compute_actions` finishes its core work and post-commit dispatch path

Unrelated local worker noise:

- the tenant’s existing Jira integration then failed locally on `SSL: CERTIFICATE_VERIFY_FAILED`
- that failure is outside the recompute pipeline fix and does not indicate a `compute_actions` stall

## Outcome

- Recompute pipeline: fixed enough to complete truthfully on the real local tenant/account scope
- Queue worker `compute_actions` path: no longer reproduces the earlier indefinite stuck symptom
- Deploy: intentionally not run

