# Run Metadata

## Scope

- Run ID: `20260330T011601Z-phase1-action-resolution-closure`
- Date: `2026-03-30`
- Production truth surface: `https://api.ocypheris.com`
- Tenant: `Marco`
- Tenant ID: `e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`
- Canary AWS account: `696505809372`
- Region: `eu-north-1`
- Terraform mirror: `/tmp/terraformrc-codex`
- AWS profile used for truthful mutations: `test28-root`

## Runtime Change

- Main code change:
  - `backend/workers/jobs/reconcile_inventory_shard.py`
  - `backend/workers/jobs/ingest_control_plane_events.py`
- Main test change:
  - `tests/test_reconcile_inventory_shard_worker.py`
  - `tests/test_ingest_control_plane_events.py`
- The production deploy was executed from isolated worktree `/tmp/aws-security-autopilot-phase1-deploy` so only the two runtime files above were shipped despite the dirty main workspace.
- Deploy command path: `scripts/deploy_saas_serverless.sh`
- Live image tag deployed: `20260330T013354Z`
- Migration requirement: none

## Local Validation

- `PYTHONPATH=. ./venv/bin/pytest tests/test_reconcile_inventory_shard_worker.py`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_ingest_control_plane_events.py`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_action_engine_merge.py -k 'shadow or resolved'`

## Production Targets

### Pre-deploy lag reproduction

- Action ID: `54b0d584-d60a-409d-86e3-5458bd8054b1`
- Bucket: `security-autopilot-w6-envready-s311-exec-696505809372`
- Resource ID: `arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372`
- Production run ID: `b9c90690-f124-491b-922d-2ac0bb8ff252`

### Post-deploy closure proof

- Same action family reused after truthful reopen
- Production run ID: `ec7fa11c-e4d0-4f54-a26a-084e3aa92d39`
- Targeted truthful reconcile response after trust repair:
  - `scenarios/wi1-postdeploy/api/internal-reconcile-after-trust-fix.json`

## Key Retained Evidence

### Pre-deploy

- Action still open after real apply:
  - `scenarios/wi1-predeploy/api/existing-action-detail-post-apply-prerecompute.json`
- Manual scoped compute that closed the stale action:
  - `scenarios/wi1-predeploy/api/existing-compute-post-apply.json`
- Action resolved after manual compute:
  - `scenarios/wi1-predeploy/api/existing-action-detail-post-compute.json`
- Local Terraform proof:
  - `scenarios/wi1-predeploy/bundle/terraform-plan.log`
  - `scenarios/wi1-predeploy/bundle/terraform-apply.log`

### Post-deploy

- Fresh production run detail:
  - `scenarios/wi1-postdeploy/api/run-detail-final.json`
- Old public re-eval path still showed global sweep behavior on this action before targeted reconcile:
  - `scenarios/wi1-postdeploy/api/trigger-reeval-after-apply.json`
- Targeted truthful reconcile after read-role trust repair:
  - `scenarios/wi1-postdeploy/api/internal-reconcile-after-trust-fix.json`
- Action resolved automatically without manual compute:
  - `scenarios/wi1-postdeploy/api/action-detail-resolved-after-trust-fix.json`
  - `scenarios/wi1-postdeploy/api/action-detail-resolved-final.json`
- Local Terraform proof:
  - `scenarios/wi1-postdeploy/bundle/terraform-plan.log`
  - `scenarios/wi1-postdeploy/bundle/terraform-apply.log`

### AWS / environment repair

- Original canary read-role trust policy:
  - `aws/read-role-trust.json`
- Updated canary read-role trust policy:
  - `aws/read-role-trust-updated.json`
- Worker log showing `AccessDenied` before trust repair:
  - `scenarios/wi1-postdeploy/aws/worker-tail-after-apply.txt`
- Worker log window after trust repair:
  - `scenarios/wi1-postdeploy/aws/worker-tail-after-trust-fix.txt`

## Cleanup State

- Final AWS cleanup deleted the lifecycle configuration again and restored the bucket to its original no-lifecycle state.
- Cleanup AWS proof:
  - `scenarios/wi1-postdeploy/aws/cleanup-delete-lifecycle.json`
  - `scenarios/wi1-postdeploy/aws/cleanup-lifecycle-after-delete.stderr`
- Cleanup action reopen polls remained noisy during the retained observation window and are not used as the signoff proof.
