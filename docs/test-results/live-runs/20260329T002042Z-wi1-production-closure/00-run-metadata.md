# Run Metadata

## Identity And Scope

- Run ID: `20260329T002042Z-wi1-production-closure`
- Created at (UTC): `2026-03-29T00:20:42Z`
- Completed at (UTC): `2026-03-29T00:52:00Z`
- Branch: `master`
- Commit: `481b5a00f8ec00f26174d20350e2bf740e5d856e`
- Frontend base: `https://ocypheris.com`
- API base: `https://api.ocypheris.com`
- Tenant: `Marco`
- Tenant ID: `e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`
- AWS account: `696505809372`
- AWS region: `eu-north-1`
- AWS profile used for live proof: `test28-root`
- Terraform mirror config: `/tmp/terraformrc-codex`
- Production runtime image tag deployed during this run: `20260329T003636Z`

## Intent

Close `WI-1` truthfully on the real production surface by:

- proving whether a seeded renderable lifecycle bucket becomes a live finding after ingest
- proving whether reconcile and compute can materialize a truthful live S3.11 action when Security Hub does not
- fixing the narrowest code path only if production truth showed a real defect
- retaining the final result as either `PASS` or `BLOCKED` without forcing a synthetic success case

## Code And Regression Slice

The code change landed in:

- [backend/workers/services/shadow_state.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/services/shadow_state.py)
- [tests/test_shadow_state.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_shadow_state.py)
- [tests/test_action_engine_merge.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_action_engine_merge.py)

Targeted validation passed:

- `tests/test_shadow_state.py`: `17 passed`
- `tests/test_action_engine_merge.py`: `19 passed`
- `tests/test_worker_ingest.py -k 'semantic_split or S3_13 or lifecycle'`: `4 passed`
- `tests/test_action_engine_merge.py -k 'lifecycle'`: `3 passed`
- `tests/test_remediation_runtime_checks.py -k 'lifecycle'`: `3 passed`
- `tests/test_remediation_profile_options_preview.py -k 's3_11'`: `4 passed`
- `tests/test_remediation_run_resolution_create.py -k 's3_11'`: `4 passed`
- `tests/test_step7_components.py -k 's3_11 or lifecycle'`: `14 passed`
- `tests/test_remediation_run_worker.py -k 's3_11 or lifecycle'`: `2 passed`

## Production Session Facts

- The runtime deploy completed successfully through [scripts/deploy_saas_serverless.sh](/Users/marcomaher/AWS%20Security%20Autopilot/scripts/deploy_saas_serverless.sh).
- The deploy transcript retains:
  - build stack unchanged
  - runtime stack updated successfully
  - both Lambda images active on tag `20260329T003636Z`
  - runtime/DB alignment at head before and after the scripted Alembic step
- The active AWS caller for the deploy was account `029037611564`, ARN `arn:aws:iam::029037611564:user/AutoPilotAdmin`.
- The fresh post-deploy WI-1 seed bucket was `phase2-wi1-lifecycle-696505809372-20260329004157`.
- The fresh bucket lifecycle document was read back successfully from AWS before any API-side refresh or reconcile call.

## Final Decisions

- Local regression slice: `PASS`
- Runtime deploy: `PASS`
- Missing finding materialization via reconcile: `FIXED`
- Truthful WI-1 additive-merge production candidate: `BLOCKED`
- Overall WI-1 production-closure result: `BLOCKED`
