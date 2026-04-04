# Final Summary

## Scope

- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- Account: `696505809372`
- Region: `eu-north-1`
- AWS mutation profile: `test28-root`
- Initial live backend/worker tag before redeploy: `20260331T183708Z`
- Final live backend/worker tag after redeploy: `20260401T215310Z`

## Run inventory

- Predeploy `S3.9` proof run:
  - remediation run `e99ec964-b607-43a3-a917-eeffd5de1d14`
  - group `fc55bea6-c85c-4c94-a694-64368ea42d4f`
- First stale postdeploy `S3.9` proof run:
  - remediation run `80d4c578-2f08-4736-b818-3668543982d5`
  - group run `b2119cd2-8a5b-43d6-8fa0-75b4f9e3c02d`
- Final canonical-runner `S3.9` proof run:
  - remediation run `aad6b818-1019-480f-bc60-3506d1c2e000`
  - group run `8a0f970e-3385-4839-96f4-9cef0ec29623`
- Live helper-bucket execution run:
  - action group `37139f5c-9319-4719-b086-430848feaf90`
  - remediation run `57a301ac-1370-4c7d-bbc8-93b3362e6bd7`
  - group run `10d76c2b-765a-4a38-98ee-69d2d7d145bd`

## Result

Overall status: `FAIL`

What passed:

1. The live runtime under test is now on a deploy tag that includes the grouped-runner fixes.
2. Fresh deployed grouped `S3.9` bundles now retain `runner_template_source = repo:infrastructure/templates/run_all.sh`.
3. Fresh deployed grouped bundles still ship `run_all.sh` as the top-level callback wrapper and delegate execution to `run_actions.sh`.
4. The shipped bundle path contains the expected mixed-tier execution-root handling and `adopt_existing_log_bucket` logic in `run_actions.sh`.
5. Fresh grouped `Config.1` bundle generation was executable, downloaded successfully, and customer-run apply completed successfully on the live target account.
6. The grouped callback finalized successfully for the live `Config.1` apply.
7. The helper bucket carries the deterministic product-managed tags from [`remediation_support_bucket.py`](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_support_bucket.py).

What failed:

1. The helper-bucket acceptance gate is still not closed.
2. Raw AWS Security Hub on the helper bucket shows failed `S3.11` and `S3.15`.
3. Product-facing findings for the same helper bucket remained stale after a forced ingest refresh:
   - `S3.5` still `NEW`
   - `S3.9` still `NEW`
4. This run therefore does not satisfy the required “no helper-bucket follow-on findings outside the narrow tagged `S3.9` path” acceptance criterion.

## Key live proof

### 1. Deploy-path fix was required and is now live

Predeploy proof still showed the old mixed-tier runner source:

- [predeploy/bundle_inspection.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/predeploy/bundle_inspection.json)
  - `runner_template_source = embedded_mixed_tier`

The first redeploy was still incomplete because the worker image context did not include `infrastructure/`. This run fixed the operator packaging path in:

- [Containerfile.lambda-worker](/Users/marcomaher/AWS%20Security%20Autopilot/Containerfile.lambda-worker)
- [scripts/deploy_saas_serverless.sh](/Users/marcomaher/AWS%20Security%20Autopilot/scripts/deploy_saas_serverless.sh)

Final deployed runtime proof:

- [postdeploy/api_lambda.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy/api_lambda.json)
- [postdeploy/worker_lambda.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy/worker_lambda.json)

### 2. Fresh deployed grouped bundles now use the canonical checked-in runner contract

Final postdeploy `S3.9` bundle inspection:

- [postdeploy-final-s39/bundle_inspection.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy-final-s39/bundle_inspection.json)
- [postdeploy-final-s39/bundle/bundle_manifest.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy-final-s39/bundle/bundle_manifest.json)
- [postdeploy-final-s39/bundle/run_all.sh](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy-final-s39/bundle/run_all.sh)
- [postdeploy-final-s39/bundle/run_actions.sh](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy-final-s39/bundle/run_actions.sh)

Observed live facts:

- `runner_template_source = repo:infrastructure/templates/run_all.sh`
- `runner_template_version = sha256:a5cf62e37840be74`
- no active metadata references `embedded_mixed_tier` or `embedded_fallback`
- shipped `run_all.sh` calls `./run_actions.sh`
- shipped `run_actions.sh` contains:
  - `EXECUTION_ROOT="${EXECUTION_ROOT:-executable/actions}"`
  - `adopt_existing_log_bucket`

Note:

- The top-level `run_all.sh` is not byte-identical to the checked-in repo template because live bundle generation injects callback/reporting payloads into that wrapper.
- The canonical proof is the live metadata contract plus the shipped wrapper/delegation behavior above.

### 3. Live helper-bucket grouped execution succeeded

Selected live family:

- action group `37139f5c-9319-4719-b086-430848feaf90`
- control `Config.1`
- strategy `config_enable_account_local_delivery`

Bundle and execution proof:

- [config-live/bundle_run_create.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/bundle_run_create.json)
- [config-live/bundle_run_final.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/bundle_run_final.json)
- [config-live/bundle_inspection.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/bundle_inspection.json)
- [config-live/bundle/execution_output.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/bundle/execution_output.log)
- [config-live/group_run_after_apply.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/group_run_after_apply.json)

Observed live facts:

- `helper_bucket_inventory[]` present with:
  - `bucket_name = security-autopilot-config-696505809372-eu-north-1`
  - `helper_bucket_role = aws-config-delivery`
  - `created = true`
  - `reused = false`
- grouped callback finalized as:
  - `status = finished`
  - `execution_status = success`

### 4. Helper bucket tags and posture

Helper bucket:

- `security-autopilot-config-696505809372-eu-north-1`

Tag evidence:

- [config-live/helper_bucket_tags.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_tags.json)

Observed tags:

- `security-autopilot:managed-support-bucket = true`
- `security-autopilot:support-bucket-role = aws-config-delivery`

Bucket posture evidence:

- [config-live/helper_bucket_public_access_block.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_public_access_block.json)
- [config-live/helper_bucket_encryption.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_encryption.json)
- [config-live/helper_bucket_policy_wrapper.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_policy_wrapper.json)
- [config-live/helper_bucket_lifecycle.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_lifecycle.json)
- [config-live/helper_bucket_versioning.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_versioning.json)

Observed posture:

- public-access block: all four flags enabled
- default encryption: `aws:kms` with `alias/aws/s3`
- SSL-only deny statement present
- lifecycle abort-incomplete rule present
- versioning response empty

### 5. Post-apply finding state on the helper bucket

Raw AWS Security Hub target-control evidence:

- [config-live/helper_bucket_securityhub_target_controls.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_securityhub_target_controls.json)
- [config-live/helper_bucket_securityhub_failed_active.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/helper_bucket_securityhub_failed_active.json)

Raw AWS result for the controls explicitly requested in this task:

- `S3.2` = `PASSED`
- `S3.5` = `PASSED`
- `S3.9` = `PASSED`
- `S3.11` = `FAILED`
- `S3.15` = `FAILED`

Product-facing finding evidence after a forced refresh:

- [config-live/post_apply_ingest_trigger.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/post_apply_ingest_trigger.json)
- [config-live/post_apply_compute_trigger.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/post_apply_compute_trigger.json)
- [config-live/internal_findings_S32.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_S32.json)
- [config-live/internal_findings_S35.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_S35.json)
- [config-live/internal_findings_s39.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_s39.json)
- [config-live/internal_findings_s311.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_s311.json)
- [config-live/internal_findings_s315.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/internal_findings_s315.json)

Observed product-facing state after refresh:

- `S3.2` = `RESOLVED`
- `S3.5` = `NEW`
- `S3.9` = `NEW`
- `S3.11` = not present
- `S3.15` = not present

Interpretation:

- Raw AWS state proves the helper bucket still violates the requested acceptance bar because `S3.11` and `S3.15` are failed on the live helper bucket.
- Internal product state is also stale/incomplete because `S3.5` and `S3.9` remained open even though raw AWS now shows those controls as passed.

## Post-apply reconcile note

Grouped callback finalization is proven by [config-live/group_run_after_apply.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live/group_run_after_apply.json).

Helper-bucket targeting is proven at the shipped-contract level by:

- grouped run metadata carrying `helper_bucket_inventory[]`
- live bundle inspection showing the helper bucket name
- deployed code path in [`post_apply_reconcile.py`](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/services/post_apply_reconcile.py), where helper buckets are appended into targeted S3 resource IDs

Current gap:

- This run did not capture a clean live queue/shard artifact that names the helper bucket inside the post-apply targeted enqueue payload.
- The downstream product state is not clean enough to treat the helper-bucket reconcile objective as passed.

## Trust-drift diagnostics

- No fresh bounded stale-trust repro was performed in this run.
- Existing readiness evidence for the healthy account scope remains in:
  - [predeploy/service_readiness.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/predeploy/service_readiness.json)

## Final conclusion

This run closes the deployment-path uncertainty:

- current deployed grouped bundles now use the canonical checked-in runner source on live
- current deployed grouped bundles ship the expected mixed-tier execution root and `adopt_existing_log_bucket` logic on the runnable bundle path

This run does not close the helper-bucket acceptance gate:

- a live grouped helper-bucket family (`Config.1`) applied successfully
- but the resulting helper bucket still carries failed raw `S3.11` and `S3.15`
- and the product-facing `S3.5` / `S3.9` state remained stale/open after refresh

Required follow-up:

1. Decide whether product-managed Config helper buckets must be hardened/suppressed for the newer failed raw controls (`S3.11`, `S3.15`, and likely `S3.14` / `S3.7`) or whether the helper-bucket design itself needs to change.
2. Fix the product refresh/reconcile path so helper-bucket `S3.5` and `S3.9` no longer remain stale/open after the bucket becomes compliant in raw AWS state.
3. Retain one more live rerun after those fixes to satisfy the original acceptance criteria end to end.
