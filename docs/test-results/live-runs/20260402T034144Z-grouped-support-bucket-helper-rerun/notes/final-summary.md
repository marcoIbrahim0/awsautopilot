# Final Summary

## Scope

- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- Account: `696505809372`
- Region: `eu-north-1`
- AWS mutation profile: `test28-root`
- Final live backend/worker tag: `20260402T033620Z`

## Run inventory

- Action group: `37139f5c-9319-4719-b086-430848feaf90`
- Strategy: `config_enable_account_local_delivery`
- Remediation run: `28610289-282e-4e41-8067-a9674344f99f`
- Group run: `10b69819-7965-4272-bd9f-c8d9c7223f78`
- Post-apply S3 reconciliation run: `d3b11ae4-0493-428b-8f35-c0b034660340`

## Result

Overall status: `PASS`

What changed:

1. The Config helper-bucket bundle path now creates the delivery bucket with object lock enabled and applies the `aws-config-delivery` support-bucket baseline, which adds versioning, EventBridge notifications, and object-lock configuration.
2. Targeted S3 reconciliation no longer reproduces the retained duplicate `finding_shadow_states` collision for account-shaped `S3.2` shadow fingerprints during global S3 sweeps.

What passed live:

1. Scoped recompute for tenant `9f7616d8-af04-43ca-99cd-713625357b70` / account `696505809372` / region `eu-north-1` completed before bundle generation.
2. Fresh grouped bundle generation succeeded and the downloaded bundle retained:
   - `helper_bucket_inventory[]`
   - `runner_template_source = repo:infrastructure/templates/run_all.sh`
   - shipped `aws_config_apply.py` logic for `--object-lock-enabled-for-bucket`, `put-bucket-versioning`, `put-bucket-notification-configuration`, and `put-object-lock-configuration`
3. Live bundle execution succeeded with `AWS_PROFILE=test28-root AWS_REGION=eu-north-1 bash ./run_all.sh`.
4. The grouped callback finalized truthfully:
   - `status = finished`
   - `reporting_source = bundle_callback`
   - `finished_at = 2026-04-02T03:49:43+00:00`
5. Raw AWS helper-bucket state is clean:
   - versioning: `Enabled`
   - notification: `EventBridgeConfiguration {}`
   - object lock: `ObjectLockEnabled = Enabled`
   - tags: `security-autopilot:managed-support-bucket=true`, `security-autopilot:support-bucket-role=aws-config-delivery`
   - Security Hub active findings for the helper bucket: `0`
6. Post-apply product refresh is clean:
   - S3 reconciliation run `d3b11ae4-0493-428b-8f35-c0b034660340` finished `succeeded`
   - helper-bucket `S3.5` is `RESOLVED`
   - helper-bucket `S3.9` is `RESOLVED`
   - helper-bucket `S3.11` is absent
   - helper-bucket `S3.15` is absent

## Key evidence

### 1. Fresh bundle generation and shipped contract

- [api/create_group_run_response.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/api/create_group_run_response.json)
- [api/remediation_run_success.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/api/remediation_run_success.json)
- [bundle/unpacked/bundle_manifest.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/bundle/unpacked/bundle_manifest.json)
- [bundle/unpacked/executable/actions/01-aws-account-696505809372-7d51a23a/scripts/aws_config_apply.py](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/bundle/unpacked/executable/actions/01-aws-account-696505809372-7d51a23a/scripts/aws_config_apply.py)

Observed facts:

- The bundle manifest retains `helper_bucket_inventory[]` with:
  - `bucket_name = security-autopilot-config-696505809372-eu-north-1`
  - `helper_bucket_role = aws-config-delivery`
  - `created = true`
  - `reused = false`
- The shipped runner metadata still proves the canonical grouped runner contract:
  - `runner_template_source = repo:infrastructure/templates/run_all.sh`
  - `runner_template_version = sha256:b27ab21c1a58e3f6`
- The shipped apply script contains the new helper-bucket baseline calls and the object-lock-enabled bucket creation path.

### 2. Live customer-run execution and truthful callback finalization

- [runtime/run_all_live.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/runtime/run_all_live.log)
- [api/group_run_post_apply.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/api/group_run_post_apply.json)

Observed facts:

- `run_all.sh` exited `0`
- Terraform apply succeeded for the grouped `Config.1` folder
- The server-side group run finalized as:
  - `status = finished`
  - `reporting_source = bundle_callback`

### 3. Raw AWS helper-bucket state after apply

- [runtime/helper_bucket_versioning.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/runtime/helper_bucket_versioning.json)
- [runtime/helper_bucket_notification.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/runtime/helper_bucket_notification.json)
- [runtime/helper_bucket_object_lock.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/runtime/helper_bucket_object_lock.json)
- [runtime/helper_bucket_tags.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/runtime/helper_bucket_tags.json)
- [runtime/securityhub_helper_bucket_active_findings.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/runtime/securityhub_helper_bucket_active_findings.json)
- [runtime/securityhub_helper_bucket_all_findings.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/runtime/securityhub_helper_bucket_all_findings.json)

Observed facts:

- The helper bucket is now versioned.
- EventBridge notification wiring exists on the helper bucket.
- Object lock is enabled on the helper bucket.
- The expected helper-bucket tags are present.
- Security Hub returned zero active findings for the helper bucket, and zero findings overall for that resource filter in the retained query.

### 4. Post-apply refresh and product-facing findings

- [api/reconciliation_run_create.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/api/reconciliation_run_create.json)
- [api/reconciliation_status_after_wait.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/api/reconciliation_status_after_wait.json)
- [api/findings_s3-5_bucket-arn.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/api/findings_s3-5_bucket-arn.json)
- [api/findings_s3-9_bucket-arn.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/api/findings_s3-9_bucket-arn.json)
- [api/findings_s3-11_bucket-arn.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/api/findings_s3-11_bucket-arn.json)
- [api/findings_s3-15_bucket-arn.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/api/findings_s3-15_bucket-arn.json)

Observed facts:

- The forced S3 reconciliation run for the same account/region succeeded instead of failing on `uq_finding_shadow_states_tenant_source_fingerprint`.
- The findings API resolves the helper bucket on the product side by the bucket ARN resource id:
  - `arn:aws:s3:::security-autopilot-config-696505809372-eu-north-1`
- Post-refresh product-facing result:
  - `S3.5 = RESOLVED`
  - `S3.9 = RESOLVED`
  - `S3.11 = not present`
  - `S3.15 = not present`

## Notes

- The pre-bundle scoped recompute completed successfully and is retained in [runtime/recompute.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/runtime/recompute.log).
- A later direct local recompute invocation was retried for completeness but did not yield an additional retained JSON payload in this session. The authoritative post-apply refresh proof in this run is the successful S3 reconciliation plus the product findings API state above.

## Final conclusion

The April 1 helper-bucket blocker is closed on live.

This rerun preserves the canonical grouped runner deployment behavior and proves the final helper-bucket outcome is clean on both sides:

- raw AWS helper-bucket state is compliant for the previously blocked checks
- grouped callback finalization is truthful
- helper-bucket inventory is present in the shipped bundle contract
- product-facing helper-bucket findings are resolved/absent after refresh
