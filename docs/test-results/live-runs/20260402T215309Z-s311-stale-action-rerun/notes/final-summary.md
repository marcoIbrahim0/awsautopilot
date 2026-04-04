# Final Summary

## Scope

- Control family: `S3.11`
- Action type: `s3_bucket_lifecycle_configuration`
- Strategy: `s3_enable_abort_incomplete_uploads`
- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- Account: `696505809372`
- Region: `eu-north-1`
- Action group: `eefe66d1-91e6-49cd-a27a-5c1afa72557d`
- Fresh grouped run: `29845b58-eeab-47af-8b3a-9218ada62452`
- Fresh remediation run: `6bb01238-e82d-4923-b488-77dfb493ad57`

## Exact stale targets used for proof

The fresh grouped rerun still represented the historical stale or deleted bucket names from the April 1 handoff, but only as truthful metadata-only members:

- `phase2-wi1-lifecycle-696505809372-20260329004157`
- `phase2-wi1-lifecycle-696505809372-20260328224331`
- `sa-wi7-seed-696505809372-20260328205857`
- `ocypheris-live-ct-20260328t181200z-eu-north-1`
- `sa-wi5-site-696505809372-20260328t164043z`
- `wi1-noncurrent-lifecycle-696505809372-20260330003655`

These are the same stale-bucket names that previously caused misleading grouped execution evidence.

## Proven in this pass

Fresh grouped-bundle generation for this exact scope produced:

- `21` represented actions
- `0` executable actions
- `8` `manual_guidance_only` actions
- `13` `review_required_bundle` actions

The stale bucket members are no longer executable. The retained decision evidence says, in substance:

- bucket existence could not be verified from this account context `(403)`
- do not keep the existing-bucket remediation path executable until bucket existence is proven

That is the truthful end state the April 1 stale-action handoff was asking for. The stale targets are still visible as metadata-only decisions, but they no longer survive as runnable grouped folders and therefore cannot fail locally with misleading `NoSuchBucket` execution output.

## Authoritative final outcome

The authoritative terminal evidence is [api/group-run-after-local-callback.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/api/group-run-after-local-callback.json).

Final persisted grouped-run state:

- `id=29845b58-eeab-47af-8b3a-9218ada62452`
- `status=finished`
- `reporting_source=bundle_callback`
- all `21` persisted results are `result_type=non_executable`
- the historical stale bucket targets above persist as `manual_guidance_only` or `review_required_bundle`

The paired remediation run [api/remediation-run-after-local-callback.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/api/remediation-run-after-local-callback.json) also records the same truth:

- `generated_action_count=21`
- `executable_action_count=0`
- `manual_guidance_action_count=8`
- `review_required_action_count=13`

## Local bundle execution

Because the fresh bundle contained `0` executable action folders, no real AWS mutation was required or attempted in this pass.

The retained local transcript [apply/run_all.stdout.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/apply/run_all.stdout.log) shows the bounded result:

```text
No executable Terraform action folders found under executable/actions/.
```

This is the correct local outcome. The fresh bundle no longer offered any misleading runnable stale members.

## Recompute investigation

The stale-action concern turned out to be already closed on the live grouped path. The remaining actual bug was a separate scoped recompute reliability issue.

Retained recompute evidence shows:

- before the query-shape fix, primary-path recompute timed out after `120s`
- fallback-only recompute succeeded in `18.2s`
- after the fix, primary-path recompute succeeded in `71.41s`

The retained pre-fix timeout summary [recompute/primary-path-pre-fix-timeout.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/recompute/primary-path-pre-fix-timeout.json) identifies the real hot path:

- `backend/services/action_groups.py::_groups_by_key`
- inside `ensure_membership_for_actions`
- where SQLAlchemy was selectin-loading `ActionGroup` relationship history, including grouped runs and remediation runs, during scoped recompute

## What was fixed

This pass landed a combination fix, but only for the recompute bug:

- recompute/projection path fix:
  - [backend/services/action_groups.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/action_groups.py)
  - narrowed `_groups_by_key` and `_memberships_by_action_id` to `noload(...)` the heavy relationship trees they do not need
- failover/connectivity hardening:
  - [backend/config.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/config.py)
  - [backend/services/database_failover.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/database_failover.py)
  - added bounded connect timeouts for sync and async database candidates

The stale-action behavior itself did not need a new resolver, ingest, or stale-target patch in this pass. Fresh live evidence shows that part was already behaving truthfully.

## Why the final behavior is truthful

The April 1 handoff asked for deleted or drifted targets to either:

- be removed from the live grouped plan, or
- be downgraded truthfully before execution

This rerun satisfies the second acceptable outcome on the real live path:

- stale deleted buckets are not exposed as executable grouped folders
- the final API state classifies them as non-executable support-tier results
- the local runner confirms there are no executable Terraform folders to run

That means deleted or drifted S3 targets can no longer survive as misleading executable grouped members for this live family.

## Separate-bug conclusion

The scoped recompute wedge was a separate bug, not the same root cause as the stale-action concern.

- stale-action concern: already closed on the live grouped path before code changes in this pass
- recompute wedge: fixed here by removing ORM-heavy projection fanout and adding bounded database connect-timeout hardening

## Validation

Focused regression coverage passed after the code changes:

```bash
DATABASE_URL='postgresql+asyncpg://user:pass@localhost/db' \
DATABASE_URL_SYNC='postgresql://user:pass@localhost/db' \
DATABASE_URL_FALLBACK='postgresql+asyncpg://user:pass@localhost/db2' \
DATABASE_URL_SYNC_FALLBACK='postgresql://user:pass@localhost/db2' \
PYTHONPATH=. ./venv/bin/python -m pytest \
  tests/test_action_groups_service.py \
  tests/test_database_failover.py \
  -q
```

Result:

- `16 passed`

## Outcome

The remaining April 1 stale-action reconciliation concern is now closed truthfully on a fresh live grouped path.

- stale deleted or drifted S3 bucket members did not survive as executable grouped actions
- the fresh grouped S3.11 bundle was entirely metadata-only
- the local bundle run confirmed there was nothing executable to mutate
- the separately wedged scoped recompute path is now fixed and completes successfully on the primary database path
