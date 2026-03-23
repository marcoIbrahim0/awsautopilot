# Grouped PR-Bundle Local Follow-Up Rerun Summary

Run root: `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260323T031500Z-grouped-pr-bundle-local-rerun-followup`

This follow-up rerun exercised the four previously unresolved grouped PR-bundle families on March 23, 2026 UTC against shared live tenant/account data using a local current-head API at `http://127.0.0.1:8000`. Fresh executable-path planning still could not rely on SaaS role-assumption proof because the local runtime continues to hit `sts:SetSourceIdentity` denial against the tenant read role, so retained March 22 bundle resolutions were reused where needed.

## Headline Outcome

- `11-eu-north-1-s3_bucket_lifecycle_configuration` now reaches grouped `finished` on the corrected current-head rerun when the create request includes `risk_acknowledged=true`.
- `13-eu-north-1-sg_restrict_public_ports` also reaches grouped `finished` on current-head, even though the local bundle runner timed out and the Terraform apply hit duplicate-ingress errors that the runner tolerated intentionally.
- `08-eu-north-1-s3_bucket_access_logging` remains blocked by the shared DB state: the exact action still collides with `uq_remediation_runs_action_active` because an older active remediation row is present.
- `17-us-east-1-ebs_default_encryption` no longer fails at create planning on the current action-group row, but the execute rerun is still blocked by an older active remediation row on the same action.

## Case Matrix

- `08-eu-north-1-s3_bucket_access_logging`: blocked by active remediation run `e0d62069-0431-4987-b38f-de12163585ec`; grouped run remains `queued`
- `11-eu-north-1-s3_bucket_lifecycle_configuration`: grouped `finished`, remediation run `success`, local runner `returncode=124`
- `13-eu-north-1-sg_restrict_public_ports`: grouped `finished`, remediation run `success`, local runner `returncode=124`, duplicate ingress tolerated
- `17-us-east-1-ebs_default_encryption`: fresh current-group create planning OK, but execute rerun blocked by active remediation run `3c47f1bb-2d8f-4489-b498-22b72405b315`

## Practical Readout

The remaining product bug from the earlier current-head rerun is now narrowed further. The two families that were still reproducing `group_run started` are no longer stuck after the follow-up rerun:

- `s3_bucket_lifecycle_configuration` is now terminal when rerun with the correct risk-acknowledged grouped request.
- `sg_restrict_public_ports` now finalizes to grouped `finished` even when duplicate ingress rules already exist and the local wrapper itself times out before returning.

The only unresolved blockers from this four-family follow-up are environment-state blockers on the shared Neon dataset:

- clear or retire the stale active remediation row for `s3_bucket_access_logging`
- clear or retire the stale active remediation row for `us-east-1 ebs_default_encryption`
