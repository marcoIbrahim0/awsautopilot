# Final Summary

## Scope

- Control family: `S3.2`
- Action type: `s3_bucket_block_public_access`
- Strategy: `s3_migrate_cloudfront_oac_private`
- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- Account: `696505809372`
- Region: `eu-north-1`
- Action group: `9200b6d5-b209-443f-9d78-28a4e60f6fb1`
- Fresh grouped run: `97fd1e76-0fee-4a98-93c6-f5b6c028e9d2`
- Fresh remediation run: `5ad151e3-91e6-46b4-a99b-e787d4f0d6c5`
- Deploy image tag used for this rerun: `20260402T192426Z`

## Proven In This Pass

This fresh April 2, 2026 UTC rerun is the authoritative production-ready proof for the remaining live `S3.2` grouped edge case and the grouped callback precision follow-on.

Fresh grouped-bundle generation for this exact scope produced:

- `33` represented actions
- `31` executable actions
- `2` `manual_guidance_only` actions

The previously failing website bucket action stayed downgraded before execution:

- action id: `da0d429e-6f16-461e-be2f-09ea7997e30a`
- bucket: `arch1-bucket-website-a1-696505809372-eu-north-1`
- result type: `non_executable`
- support tier: `manual_guidance_only`
- blocked reason:
  - `Bucket is still configured for S3 website hosting with a public website-read policy, and BlockPublicPolicy would reject preserving that public statement. Use the website-specific CloudFront cutover path or manual review instead of the generic CloudFront + OAC migration.`

The real affected customer action stayed executable and finished successfully:

- action id: `1dc66e7e-efe9-4fd6-9335-3197211b289f`
- bucket: `security-autopilot-dev-serverless-src-696505809372-eu-north-1`
- result type: `executable`
- execution status: `success`

This rerun did not reopen any of the earlier closed defects:

- `OriginAccessControlAlreadyExists` stayed closed
- the old `HeadBucket 403` downgrade bug stayed closed
- the old `hashicorp/external` startup blocker stayed closed
- the website-policy/BPA blocker stayed closed truthfully by downgrade before execution

## Authoritative Final Outcome

The authoritative terminal evidence is [api/group-run-after-local-apply.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/api/group-run-after-local-apply.json), not the local PTY log capture.

Final persisted grouped-run state:

- `id=97fd1e76-0fee-4a98-93c6-f5b6c028e9d2`
- `status=finished`
- `reporting_source=bundle_callback`
- `started_at=2026-04-02T19:51:43.570784+00:00`
- `finished_at=2026-04-02T20:39:59+00:00`
- `33` represented results
- `31` executable results
- `2` non-executable results
- all `31` executable results persisted as `success`

This proves the grouped callback/result persistence fix is live and production-ready:

- executable members were not flattened to coarse `bundle_runner_failed`
- the website action stayed metadata-only and bounded
- the real affected action stayed executable and `success`

## Evidence Boundaries

The local PTY capture file [apply/run_all.stdout.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/apply/run_all.stdout.log) is empty, so it is not usable as terminal evidence.

The saved callback replay attempt in [api/callback-finished-response.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/api/callback-finished-response.json) returned:

- `error=Group run report conflict`
- `reason=group_run_report_conflict`
- `current_status=finished`
- `already_consumed=true`

That conflict is expected here and confirms the real bundle callback had already finalized the group run before the manual replay attempt.

The later subset rerun retained under `bundle/extracted/tail-run/` plus [apply/run_tail.stdout.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/apply/run_tail.stdout.log) is non-authoritative follow-on evidence only. It was executed after the fresh grouped run had already terminalized successfully and must not be mistaken for the real terminal outcome.

## Recompute Note

The scoped recompute step was attempted twice but remained wedged. The retained artifact [recompute/recompute-result.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/recompute/recompute-result.json) records:

- `status=blocked`
- `step=recompute_account_actions`
- exact scoped target: tenant `9f7616d8-af04-43ca-99cd-713625357b70`, account `696505809372`, region `eu-north-1`
- bounded reason: the recompute invocation produced no stdout and appeared wedged on DB access

The grouped rerun still proceeded with the exact intended live action-group scope and produced the authoritative bundle proof above.

## Validation

Focused local regression coverage for the product fix plus callback precision fix passed:

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

## Outcome

Acceptable end state `2` is now proven production-ready on the live grouped path:

- the previously failing website action `da0d429e-6f16-461e-be2f-09ea7997e30a` is downgraded truthfully before execution with explicit bounded reasoning
- the real affected customer action `1dc66e7e-efe9-4fd6-9335-3197211b289f` remains executable and succeeds
- final grouped callback persistence preserves exact per-action truth for all `33` represented actions

The original S3.2 blocker is closed. The grouped callback precision follow-on is also closed on the live deployed path used by this rerun.
