# Next-Agent Handoff

## Purpose

This handoff is for the next agent to continue the failed live validation from:

- [Grouped runner / support-bucket live validation README](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/README.md)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/notes/final-summary.md)

The next agent should fix/debug the helper-bucket failure, then do a real live recompute -> create/download PR bundle -> run bundle -> verify post-apply outcome cycle again.

## Authoritative scope

- Repo root: `/Users/marcomaher/AWS Security Autopilot`
- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- Account: `696505809372`
- Region: `eu-north-1`
- AWS mutation profile: `test28-root`
- Current date context when this handoff was written: `2026-04-02`

## What is already proven

### Live deployment-path fix is proven

The original production issue from April 1 was real: live grouped mixed-tier bundles still shipped the old embedded runner even after the code had landed on `master`.

This is now fixed on live.

Relevant proof:

- [predeploy/bundle_inspection.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/predeploy/bundle_inspection.json)
  - old runtime showed `runner_template_source = embedded_mixed_tier`
- [postdeploy-final-s39/bundle_inspection.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy-final-s39/bundle_inspection.json)
  - current live runtime shows `runner_template_source = repo:infrastructure/templates/run_all.sh`

Live runtime that was finally validated:

- final deployed tag: `20260401T215310Z`

Relevant retained runtime artifacts:

- [postdeploy/api_lambda.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy/api_lambda.json)
- [postdeploy/worker_lambda.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy/worker_lambda.json)
- [postdeploy/health.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy/health.json)
- [postdeploy/ready.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy/ready.json)

### Repo packaging fix already landed locally

The live deploy-path bug was not just stale runtime. The repo’s own deployment packaging was incomplete.

Files already edited for that:

- [Containerfile.lambda-worker](/Users/marcomaher/AWS%20Security%20Autopilot/Containerfile.lambda-worker)
  - added `COPY infrastructure ${LAMBDA_TASK_ROOT}/infrastructure`
- [scripts/deploy_saas_serverless.sh](/Users/marcomaher/AWS%20Security%20Autopilot/scripts/deploy_saas_serverless.sh)
  - source zip now includes `infrastructure`

These edits were necessary because:

- worker bundle generation reads the checked-in runner from `infrastructure/templates/run_all.sh`
- the image and source zip previously did not include `infrastructure/`

### Live grouped helper-bucket apply path is proven executable

The live `S3.9` family remained non-executable because the account context still could not prove bucket existence and destination safety for the targeted buckets.

The run pivoted to `Config.1`, which is the cleanest retained executable helper-bucket family.

Chosen live action group:

- action group `37139f5c-9319-4719-b086-430848feaf90`
- control `Config.1`
- strategy `config_enable_account_local_delivery`

Bundle/apply identifiers:

- remediation run `57a301ac-1370-4c7d-bbc8-93b3362e6bd7`
- group run `10d76c2b-765a-4a38-98ee-69d2d7d145bd`

Relevant artifacts:

- [config-live/bundle_run_request.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/bundle_run_request.json)
- [config-live/bundle_run_create.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/bundle_run_create.json)
- [config-live/bundle_run_final.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/bundle_run_final.json)
- [config-live/pr-bundle.zip](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/pr-bundle.zip)
- [config-live/bundle_inspection.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/bundle_inspection.json)
- [config-live/bundle/execution_output.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/bundle/execution_output.log)
- [config-live/group_run_after_apply.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/group_run_after_apply.json)

Observed live facts:

- grouped bundle is executable
- customer-run apply succeeded
- grouped callback terminalized as `finished`
- helper bucket inventory is present in grouped metadata

## Current blocker

The acceptance failure is no longer “runner path is stale” or “bundle cannot run.”

The current blocker is helper-bucket outcome correctness.

Created helper bucket:

- `security-autopilot-config-696505809372-eu-north-1`

Observed helper-bucket tags:

- `security-autopilot:managed-support-bucket = true`
- `security-autopilot:support-bucket-role = aws-config-delivery`

Relevant tag artifact:

- [config-live/helper_bucket_tags.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_tags.json)

### Raw AWS state after apply

These are the most important raw AWS findings artifacts:

- [config-live/helper_bucket_securityhub_target_controls.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_securityhub_target_controls.json)
- [config-live/helper_bucket_securityhub_failed_active.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_securityhub_failed_active.json)

Important raw AWS result:

- `S3.2` = `PASSED`
- `S3.5` = `PASSED`
- `S3.9` = `PASSED`
- `S3.11` = `FAILED`
- `S3.15` = `FAILED`

Other failed raw controls also appeared:

- `S3.14`
- `S3.7`

So the current helper bucket is not “adjacency-safe” in raw AWS Security Hub terms.

### Product state after forced refresh

After the apply, the run explicitly triggered:

- scoped ingest
- scoped action compute

Artifacts:

- [config-live/post_apply_ingest_trigger.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/post_apply_ingest_trigger.json)
- [config-live/post_apply_compute_trigger.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/post_apply_compute_trigger.json)

Then internal findings were rechecked on the helper bucket:

- [config-live/internal_findings_S32.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_S32.json)
- [config-live/internal_findings_S35.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_S35.json)
- [config-live/internal_findings_s39.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_s39.json)
- [config-live/internal_findings_s311.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_s311.json)
- [config-live/internal_findings_s315.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_s315.json)

Observed internal state after refresh:

- `S3.2` = `RESOLVED`
- `S3.5` = `NEW`
- `S3.9` = `NEW`
- `S3.11` = not present
- `S3.15` = not present

Interpretation:

1. Raw AWS still shows real follow-on failed controls on the helper bucket.
2. Product-facing findings are also stale or incomplete:
   - raw AWS says `S3.5` and `S3.9` passed
   - internal findings still show them open

This means the next agent likely has to fix both:

- helper-bucket baseline or suppression/ignore contract
- post-apply refresh/reconcile truthfulness

## Strongest hypotheses for the next fix

### Hypothesis 1: support-bucket baseline is still too narrow

The current helper-bucket baseline in [remediation_support_bucket.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_support_bucket.py) clearly covers:

- public-access block
- default encryption
- SSL-only deny policy
- lifecycle abort-incomplete
- optional versioning

But the retained raw AWS state shows that for the Config delivery helper bucket this is still insufficient for:

- `S3.11` object lock
- `S3.15` event notifications

The control titles and IDs in raw AWS are counterintuitive compared to older naming assumptions, so do not trust memory. Re-verify the live control mapping from actual Security Hub results before changing code.

### Hypothesis 2: inventory reconcile / finding projection is stale after apply

The product still showed:

- `S3.5` open
- `S3.9` open

even after raw AWS showed them passed and after a forced ingest + compute.

The next likely places to inspect are:

- [backend/workers/services/post_apply_reconcile.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/services/post_apply_reconcile.py)
- [backend/workers/services/inventory_reconcile.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/services/inventory_reconcile.py)
- [backend/workers/jobs/reconcile_inventory_shard.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/jobs/reconcile_inventory_shard.py)
- [backend/workers/jobs/ingest_findings.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/jobs/ingest_findings.py)
- [backend/workers/jobs/ingest_control_plane_events.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/jobs/ingest_control_plane_events.py)

### Hypothesis 3: product policy may need a deliberate helper-bucket exception contract

It is possible the product-managed helper bucket should not be expected to satisfy every modern S3 control literally.

If so, the fix may need to be one of:

- broaden helper-bucket hardening so it truly passes the required controls
- or add a narrow and explicit product-managed helper-bucket suppression policy for additional controls

If you take the suppression route:

- keep it narrow
- tie it to deterministic tags
- retain proof that normal customer buckets are not suppressed

## Important commands and live workflow

### Scoped recompute

```bash
PYTHONPATH=. ./venv/bin/python scripts/recompute_account_actions.py \
  --tenant-id 9f7616d8-af04-43ca-99cd-713625357b70 \
  --account-id 696505809372 \
  --region eu-north-1
```

### Bundle generation helper

```bash
PYTHONPATH=. ./venv/bin/python scripts/run_no_ui_pr_bundle_agent.py \
  --api-base https://api.ocypheris.com \
  --account-id 696505809372 \
  --region eu-north-1
```

### Grouped customer-run execution

```bash
AWS_PROFILE=test28-root AWS_REGION=eu-north-1 bash ./run_all.sh
```

### Production deploy path

```bash
bash scripts/deploy_saas_serverless.sh --tag <TAG>
```

Then separately:

```bash
/bin/zsh -lc 'set -a; source config/.env.ops; set +a; ./venv/bin/alembic upgrade heads'
```

## Recommended next live validation path

1. Inspect the retained helper-bucket artifacts first. Do not rediscover from scratch.
2. Determine the intended truth for product-managed `aws-config-delivery` helper buckets:
   - should they truly pass `S3.11` / `S3.15` raw AWS checks?
   - or should the product suppress/ignore those findings narrowly for tagged support buckets?
3. Implement the smallest correct fix.
4. Run focused tests for the touched code.
5. If backend/worker runtime changes are involved, redeploy production again through the supported path.
6. Recompute the same tenant/account/region scope.
7. Generate a fresh grouped bundle again.
8. Download and inspect the fresh bundle again.
9. Run the bundle live again with `AWS_PROFILE=test28-root`.
10. Verify:
   - grouped callback finalization
   - helper bucket inventory
   - helper bucket raw AWS findings
   - product-facing findings after refresh
11. Retain a new live evidence package rather than overwriting the old one.

## What not to redo

- Do not spend time re-proving the old embedded-runner issue unless something indicates regression.
- Do not treat the current failure as an auth or trust blocker; this run already reached real live apply.
- Do not rely on the live `S3.9` grouped family as the main apply target unless you first prove it is executable again; the retained April 1 data showed it still downgraded to review-only because of bucket-existence `403` proof gaps.

## Useful retained files

### Main run package

- [README.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/README.md)
- [final-summary.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/notes/final-summary.md)

### Best helper-bucket evidence set

- [config-live/bundle_inspection.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/bundle_inspection.json)
- [config-live/group_run_after_apply.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/group_run_after_apply.json)
- [config-live/helper_bucket_tags.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_tags.json)
- [config-live/helper_bucket_public_access_block.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_public_access_block.json)
- [config-live/helper_bucket_encryption.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_encryption.json)
- [config-live/helper_bucket_policy_wrapper.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_policy_wrapper.json)
- [config-live/helper_bucket_lifecycle.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_lifecycle.json)
- [config-live/helper_bucket_securityhub_target_controls.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_securityhub_target_controls.json)
- [config-live/helper_bucket_securityhub_failed_active.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_securityhub_failed_active.json)
- [config-live/internal_findings_S32.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_S32.json)
- [config-live/internal_findings_S35.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_S35.json)
- [config-live/internal_findings_s39.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_s39.json)
- [config-live/internal_findings_s311.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_s311.json)
- [config-live/internal_findings_s315.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_s315.json)

### Canonical runner proof set

- [postdeploy-final-s39/bundle_inspection.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy-final-s39/bundle_inspection.json)
- [postdeploy-final-s39/bundle/bundle_manifest.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy-final-s39/bundle/bundle_manifest.json)
- [postdeploy-final-s39/bundle/run_all.sh](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy-final-s39/bundle/run_all.sh)
- [postdeploy-final-s39/bundle/run_actions.sh](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy-final-s39/bundle/run_actions.sh)

## Final instruction to the next agent

Treat this as a live debugging continuation, not a greenfield investigation.

Start from the retained evidence above, fix the real helper-bucket issue, then rerun the exact live cycle:

- recompute
- create/download bundle
- inspect bundle
- run bundle live
- verify grouped callback
- verify helper-bucket raw AWS findings
- verify internal findings after refresh

Do not stop at bundle download.
