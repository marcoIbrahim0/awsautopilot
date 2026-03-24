# CloudTrail.1 and S3.5 Local Live-Data E2E Summary

Run root: `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260323T033827Z-cloudtrail-s35-local-e2e`

This rerun exercised the current-head `CloudTrail.1` and `S3.5` grouped PR-bundle paths on March 23, 2026 UTC against the shared live tenant/account data for account `696505809372` in `eu-north-1`, using a local API at `http://127.0.0.1:8000` after applying migration `0048_action_group_pending_confirmation_bucket`.

## Headline Outcome

- `CloudTrail.1` is now behaving truthfully: the grouped family still exists, but a fresh risk-acknowledged grouped create fails closed as `400 invalid_strategy_inputs` because `trail_bucket_name` is unresolved. The flat findings API shows `pending_confirmation=false` for both live `CloudTrail.1` findings.
- `S3.5` still does not show the pending-confirmation banner in this live dataset, but the reason is now explicit: the current grouped bundle is entirely `review_required_metadata_only` for all `12` member actions because bucket-policy preservation evidence is missing for merge-safe SSL enforcement. No executable fix was applied.
- The generated `S3.5` bundle still failed to finalize locally through the internal callback path in this rerun. The remediation run completed `success` and the bundle was downloaded, but the `ActionGroupRun` remained `started` after local `run_all.sh` execution timed out posting back to the local callback URL.

## Case Matrix

- `01-eu-north-1-cloudtrail_enabled`
  - group id: `d0ea8837-bb23-48d4-82cd-eb64d697f42f`
  - create with `risk_acknowledged=true`: `400 invalid_strategy_inputs`
  - reason: unresolved CloudTrail log bucket name
- `02-eu-north-1-s3_bucket_require_ssl`
  - group id: `c5920987-fba3-4ea5-8363-8ccae8f39c08`
  - group run id: `fd8e6c29-2ddf-4f0f-bac8-e0e92d2013d6`
  - remediation run id: `7d5e9342-a5e7-4391-a727-3ac50ecb024b`
  - remediation worker result: `success`
  - bundle manifest: `12` actions, all `review_required_metadata_only`
  - final grouped state after local replay attempt: `started`

## Practical Readout

The `CloudTrail.1` fix is validated on local current-head against the shared live dataset: the card is no longer implying a successful or pending-successful remediation, and the grouped create path no longer crashes.

The `S3.5` flat cards still correctly show no waiting-for-AWS banner in this run, but not because the pending-confirmation projection is wrong. In this specific live dataset, the grouped family currently degrades to review-required metadata only, so there is no truthful executable success to project. The remaining product bug exposed here is narrower: the local callback/finalization path still left the metadata-only grouped run in `started` instead of a terminal state after bundle execution/replay.
