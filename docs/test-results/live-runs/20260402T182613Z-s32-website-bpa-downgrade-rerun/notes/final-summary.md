# Final Summary

## Scope

- Control family: `S3.2`
- Action type: `s3_bucket_block_public_access`
- Strategy: `s3_migrate_cloudfront_oac_private`
- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- Account: `696505809372`
- Region: `eu-north-1`
- Action group: `9200b6d5-b209-443f-9d78-28a4e60f6fb1`
- Fresh grouped run: `f7cbe9e5-fa9b-47fc-8616-42cb0219daeb`
- Fresh remediation run: `bf16fb62-4575-471d-b408-9d3364c27650`
- Deploy image tag used for this rerun: `20260402T182613Z`
- Image build id: `security-autopilot-dev-serverless-image-builder:9c70c3e9-f096-4182-ba1d-89a95503860f`

## Closed In This Pass

The remaining website-policy plus `BlockPublicPolicy` edge case is now closed truthfully before bundle execution.

Fresh grouped-bundle generation for this exact scope produced:

- `33` represented actions
- `31` executable actions
- `2` `manual_guidance_only` actions

The previously failing website bucket action is now downgraded before Terraform generation:

- action id: `da0d429e-6f16-461e-be2f-09ea7997e30a`
- bucket: `arch1-bucket-website-a1-696505809372-eu-north-1`
- support tier: `manual_guidance_only`
- selected profile: `s3_migrate_cloudfront_oac_private_manual_preservation`
- bounded reason:
  - `Bucket is still configured for S3 website hosting with a public website-read policy, and BlockPublicPolicy would reject preserving that public statement. Use the website-specific CloudFront cutover path or manual review instead of the generic CloudFront + OAC migration.`

The real affected customer action stayed executable:

- action id: `1dc66e7e-efe9-4fd6-9335-3197211b289f`
- bucket: `security-autopilot-dev-serverless-src-696505809372-eu-north-1`
- support tier: `deterministic_bundle`
- selected profile: `s3_migrate_cloudfront_oac_private`

This preserves the earlier closed defects:

- `OriginAccessControlAlreadyExists` did not re-open
- the old `HeadBucket 403` downgrade bug stayed closed
- the old `hashicorp/external` startup blocker stayed closed
- the real affected action did not regress back to downgrade-only

## Fresh Live Outcome

Fresh local execution of the downloaded grouped bundle with:

```bash
AWS_PROFILE=test28-root AWS_REGION=eu-north-1 bash ./run_all.sh
```

produced this exact runner truth:

- `28/31` executable action folders succeeded
- `3/31` executable action folders failed
- the old website bucket action `da0d429e-6f16-461e-be2f-09ea7997e30a` was not executed because it had already moved into `manual_guidance/actions/...`

The three executable failures were new and unrelated to the old website-policy/BPA bug:

1. `executable/actions/22-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-d03ad604`
   - Terraform plan failed on live AWS credential validation because `sts.eu-north-1.amazonaws.com` could not be resolved (`lookup ... no such host`)
2. `executable/actions/23-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-d3cf0cc7`
   - CloudFront/OAC discovery preflight failed because the AWS CLI could not connect to `https://cloudfront.amazonaws.com/2020-05-31/distribution`
3. `executable/actions/24-arn-aws-s3-security-autopilot-access-logs-696505-dda812ab`
   - same live CloudFront endpoint connectivity failure as action `23`

So the retained rerun no longer fails because of the old website bucket `PutBucketPolicy 403 AccessDenied` path. That blocker is gone. The new live blocker is transient AWS endpoint/DNS instability during local execution.

## Separate Follow-on Found During Verification

The retained final group-run API state still flattened executable action truth too coarsely once the bundle exited non-zero:

- local runner log truth: `28/31` executable folders succeeded and `3/31` failed
- persisted group-run truth in `api/group-run-after-local-apply.json`: all `31` executable actions were recorded as `bundle_runner_failed`
- non-executable metadata remained truthful:
  - `19337c80-843c-40fb-b35c-fd561406009f` stayed `manual_guidance_only`
  - `da0d429e-6f16-461e-be2f-09ea7997e30a` stayed `manual_guidance_only`

This was not the original S3.2 blocker, but it was tightly related to grouped live verification. A narrow repo-side fix was added in the same pass:

- the active checked-in grouped runner template now emits `.bundle-execution-summary.json`
- the callback wrapper now uses that summary instead of flattening all executable members to a single coarse failure template

That follow-on fix is repo-tested but not re-deployed and re-proven live inside this retained package. This package therefore captures the truthful pre-redeploy behavior.

## Validation

Focused local regression coverage passed:

- `tests/test_remediation_runtime_checks.py`
- `tests/test_remediation_profile_options_preview.py`
- `tests/test_remediation_run_resolution_create.py`
- `tests/test_remediation_run_worker.py`

Targeted command:

```bash
DATABASE_URL='postgresql+asyncpg://user:pass@localhost/db' \
DATABASE_URL_SYNC='postgresql://user:pass@localhost/db' \
DATABASE_URL_FALLBACK='postgresql+asyncpg://user:pass@localhost/db' \
DATABASE_URL_SYNC_FALLBACK='postgresql://user:pass@localhost/db' \
PYTHONPATH=. /opt/homebrew/bin/pytest \
  tests/test_remediation_runtime_checks.py \
  tests/test_remediation_profile_options_preview.py \
  tests/test_remediation_run_resolution_create.py \
  tests/test_remediation_run_worker.py \
  -q \
  -k 's35_captures_public_policy_and_bpa_state or s3_2_oac_captures_public_website_and_bpa_state or oac_strategy_executable_with_runtime_proven_zero_policy or downgrades_oac_strategy_for_public_website_bucket_under_bpa or keeps_oac_apply_time_merge_executable_after_risk_acknowledgement or posts_finished_failed_on_runner_error or uses_execution_summary_for_partial_failures or infra_run_all_template_fails_closed_when_cloudfront_oac_preflight_fails or callback_enabled_group_pr_bundle_includes_wrapper_and_non_executable_results'
```

Result:

- `10 passed`
- only existing Homebrew pytest-config warnings remained

## Outcome

Acceptable end state `2` is satisfied for the remaining live `S3.2` edge case:

- the previously failing website action `da0d429e-6f16-461e-be2f-09ea7997e30a` is now downgraded truthfully before execution with explicit bounded reasoning
- the grouped rerun no longer fails because of that website-policy/BPA case

The remaining blockers after this rerun are new and separate:

- transient live AWS endpoint/DNS failures during local execution
- pre-redeploy grouped callback persistence flattening, now fixed in repo but not live-rerun in this package
