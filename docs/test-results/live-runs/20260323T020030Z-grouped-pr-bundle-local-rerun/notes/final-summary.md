# Grouped PR-Bundle Local Current-Head Rerun Summary

Run root: `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260323T020030Z-grouped-pr-bundle-local-rerun`

This run exercised the March 23 current-head grouped PR-bundle fixes against live tenant/account data without redeploying the backend runtime. The local API pointed at the shared Neon database, and executable-path checks reused retained March 22 `group_bundle.action_resolutions` where the local-only runtime could not safely reproduce SaaS role-assumption behavior.

## Headline Outcome

- `cloudtrail_enabled` in both `eu-north-1` and `us-east-1` no longer crashes at grouped create time. Both now fail closed as structured `invalid_strategy_inputs` with the expected unresolved `trail_bucket_name` message.
- `ebs_default_encryption` in `eu-north-1` regenerated on current-head, executed locally with `AWS_PROFILE=test28-root`, and finished cleanly with grouped status `finished`.
- `s3_bucket_encryption_kms` regenerated on current-head and the shared DB recorded `remediation_run=success` plus grouped status `finished`, confirming that this family is no longer stuck in `started` under the retained current-head rerun path.
- `s3_bucket_lifecycle_configuration` and `sg_restrict_public_ports` both regenerated on current-head and advanced to `remediation_run=success`, but their grouped runs still remained `started`, so grouped finalization is still not reliable for those families.
- `s3_bucket_access_logging` and `us-east-1 ebs_default_encryption` were blocked by already-active remediation rows on the shared DB, not by current-head create-time crashes.

## Case Matrix

- `02-eu-north-1-cloudtrail_enabled`: `validation_error` / `invalid_strategy_inputs`
- `03-eu-north-1-ebs_default_encryption`: `finished`, `exec_returncode=0`
- `08-eu-north-1-s3_bucket_access_logging`: blocked by active pending remediation run `e0d62069-0431-4987-b38f-de12163585ec`
- `10-eu-north-1-s3_bucket_encryption_kms`: grouped `finished`, remediation run `success`
- `11-eu-north-1-s3_bucket_lifecycle_configuration`: remediation run `success`, grouped run still `started`
- `13-eu-north-1-sg_restrict_public_ports`: remediation run `success`, grouped run still `started`
- `16-us-east-1-cloudtrail_enabled`: `validation_error` / `invalid_strategy_inputs`
- `17-us-east-1-ebs_default_encryption`: fresh create planning OK, but execute rerun blocked by older pending remediation run `3c47f1bb-2d8f-4489-b498-22b72405b315`

## Practical Readout

The March 23 create-time fixes are confirmed. The March 23 runner/callback hardening is partially confirmed: it closes `eu-north-1 ebs_default_encryption` and `s3_bucket_encryption_kms`, but `s3_bucket_lifecycle_configuration` and `sg_restrict_public_ports` still reproduce a `group_run started` finalization gap even after the worker marks the remediation run itself successful.

The remaining blockers for a clean full rerun are now:

- clear or retire the stale active remediation rows for `s3_bucket_access_logging` and `us-east-1 ebs_default_encryption`
- root-cause why `s3_bucket_lifecycle_configuration` and `sg_restrict_public_ports` can still end with `remediation_run=success` while the grouped run never posts a terminal callback
