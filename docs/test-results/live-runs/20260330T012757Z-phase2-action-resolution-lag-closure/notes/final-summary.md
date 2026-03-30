# Final Summary

## Scope

- Production truth surface: `https://api.ocypheris.com`
- Tenant: `Marco`
- Tenant ID: `e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`
- Canary AWS account: `696505809372`
- Region: `eu-north-1`
- Terraform mirror: `/tmp/terraformrc-codex`
- Canary mutation profile for AWS truth probes: `test28-root`

## Verdict

- Overall Phase 2 signoff: `PASS`
- Gate 2: `PASS`

## Current Phase 2 Truth

- `WI-2` is already closed truthfully on production.
- `WI-8` is already closed truthfully on production.
- `WI-1` remains closed as a semantics conclusion, not as an executable additive-merge candidate.
  - The authoritative March 30 result still stands: the tested existing lifecycle shapes are compliant under live AWS behavior, so production does not currently expose a truthful open additive-merge candidate for `S3.11`.
- The only remaining Gate 2 blocker from the March 30 retained package was the post-apply action-resolution lag.
- This run fixed that lag on production and re-proved the state transition on the live API.

## Local Regression Gate

The required local regression slices all passed before deploy.

- `PYTHONPATH=. ./venv/bin/pytest tests/test_worker_ingest.py -k 'semantic_split or S3_13 or lifecycle'`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_action_engine_merge.py -k 'lifecycle'`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_remediation_runtime_checks.py -k 'lifecycle'`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_remediation_profile_options_preview.py -k 's3_11'`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_remediation_run_resolution_create.py -k 's3_11'`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_step7_components.py -k 's3_11 or lifecycle'`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_remediation_run_worker.py -k 's3_11 or lifecycle'`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_reconcile_inventory_shard_worker.py -q`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_remediation_runs_api.py -q -k 'trigger_reeval'`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_action_engine_merge.py -q -k 'shadow or orphan or lifecycle'`

The detailed command ledger is retained in [local-gate/pytest-phase2-action-resolution-lag.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260330T012757Z-phase2-action-resolution-lag-closure/local-gate/pytest-phase2-action-resolution-lag.txt).

## Production Deploy

- Before deploy, production still exposed the old `trigger-reeval` behavior.
  - Calling `POST /api/actions/53c07253-a9b1-4044-92f9-750063d30b59/trigger-reeval` returned `enqueued_jobs=10`, which is the old global sweep path.
- Production runtime was redeployed from the current workspace using:
  - `/bin/zsh -lc 'set -a; source config/.env.ops; set +a; ./scripts/deploy_saas_serverless.sh --region eu-north-1'`
- The deploy completed successfully with live image tag `20260330T013924Z`.
- Both `security-autopilot-dev-api` and `security-autopilot-dev-worker` rolled forward to the new image tag, and the runtime/DB alignment guard remained at Alembic head `0053_action_group_pending_confirmation_refresh`.

## Lag-Closure Proof

### Proof target selection

- The original March 30 stale `WI-1` action `8d9e8cc1-949a-412d-8db0-98923b513518` was already `resolved` when this run began.
- The still-open deleted-resource stale action `53c07253-a9b1-4044-92f9-750063d30b59` therefore became the active regression target for the lag proof.

### Before deploy

- Action `53c07253-a9b1-4044-92f9-750063d30b59`:
  - `status=open`
  - `action_type=s3_bucket_lifecycle_configuration`
  - `resource_id=arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329004157`
- Linked finding `7adc461d-a5d9-44af-bc4a-764a4abb3500`:
  - `status=NEW`
  - `effective_status=NEW`
  - `remediation_action_status=open`
  - no shadow overlay yet
- AWS truth for the underlying bucket:
  - `AWS_PROFILE=test28-root aws s3api head-bucket --bucket phase2-wi1-lifecycle-696505809372-20260329004157`
  - returned `404 Not Found`

### After deploy

- Reauthenticated truthfully against `https://api.ocypheris.com`.
- Re-ran `POST /api/actions/53c07253-a9b1-4044-92f9-750063d30b59/trigger-reeval`.
- The live response returned:
  - `enqueued_jobs=1`
  - `scope.account_id=696505809372`
  - `scope.region=eu-north-1`
- This proves the targeted reconcile path is live in production.

### Closure result

- On the first retained post-deploy poll at `2026-03-30T01:44:11Z`:
  - action `53c07253-a9b1-4044-92f9-750063d30b59` moved to `resolved`
  - finding `7adc461d-a5d9-44af-bc4a-764a4abb3500` moved to:
    - `status=RESOLVED`
    - `effective_status=RESOLVED`
    - `shadow.status_normalized=RESOLVED`
    - `shadow.status_reason=inventory_resource_deleted`
    - `remediation_action_status=resolved`
- This is the exact production state transition that was still broken in the March 30 blocked package.

## Final Truth

- `WI-1` candidate discovery does not need more seeding under the current live semantics.
- The post-apply action-resolution lag no longer leaves the retained deleted-resource Phase 2 action open after truthful resolved state reaches the live finding.
- Gate 2 is now closed on production.
