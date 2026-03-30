# Run Metadata

## Scope

- Run ID: `20260330T012757Z-phase2-action-resolution-lag-closure`
- Date: `2026-03-30`
- Production truth surface: `https://api.ocypheris.com`
- Tenant: `Marco`
- Tenant ID: `e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`
- Canary AWS account: `696505809372`
- Region: `eu-north-1`
- Terraform mirror: `/tmp/terraformrc-codex`
- AWS profile used for truthful probes: `test28-root`

## Runtime Change

- Purpose: close the remaining Phase 2 targeted re-evaluation lag on production
- Deploy script: `scripts/deploy_saas_serverless.sh`
- Live image tag deployed: `20260330T013924Z`
- Deploy log: `deploy/deploy-serverless.log`

## Local Validation

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

## Production Proof Target

- Active regression target: action `53c07253-a9b1-4044-92f9-750063d30b59`
- Action type: `s3_bucket_lifecycle_configuration`
- Resource: `arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329004157`
- Linked finding: `7adc461d-a5d9-44af-bc4a-764a4abb3500`

## Retained Evidence

- API before/after action state:
  - `api/actions_53c07253-a9b1-4044-92f9-750063d30b59.before.json`
  - `api/actions_53c07253-a9b1-4044-92f9-750063d30b59.after.json`
- API before/after finding state:
  - `api/findings_7adc461d-a5d9-44af-bc4a-764a4abb3500.before.json`
  - `api/findings_7adc461d-a5d9-44af-bc4a-764a4abb3500.after.json`
- Trigger-reeval before/after deploy:
  - `api/actions_53c07253-a9b1-4044-92f9-750063d30b59.trigger-reeval.json`
  - `api/actions_53c07253-a9b1-4044-92f9-750063d30b59.trigger-reeval-postdeploy.json`
- Poll ledger:
  - `api/actions_53c07253-a9b1-4044-92f9-750063d30b59.poll.tsv`
- AWS deleted-resource truth:
  - `aws/phase2-wi1-lifecycle-head-bucket.stdout`
  - `aws/phase2-wi1-lifecycle-head-bucket.stderr`
- Detailed local gate transcript:
  - `local-gate/pytest-phase2-action-resolution-lag.txt`
