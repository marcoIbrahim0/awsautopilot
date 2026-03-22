# Test 05 - S3.5 grouped SSL-enforcement live proof closure on retained rerun runtime

- Wave: `Wave 6`
- Date (UTC): `2026-03-18T17:30:46Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18022`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Exact HEAD tested: `e9a362b3f543154838a72665dcd2866919b5089b`
- Local follow-up patches: `backend/services/aws_s3_bundle_support.py`, `backend/services/pr_bundle.py`, `backend/services/remediation_profile_selection.py`, `backend/services/remediation_strategy.py`
- Local runtime workarounds: `TF_CLI_ARGS_init=-plugin-dir=/tmp/tf-plugin-mirror`; saved `finished` callback payload replayed to the retained local API because the generated external execute-api hostname did not resolve from this workstation

## Preconditions

- Retained Wave 6 rerun runtime reused from [`../notes/final-summary.md`](../notes/final-summary.md).
- Repo-authoritative `S3.5` is `s3_bucket_require_ssl` bucket-policy enforcement, not S3 public-access-block.
- S3.5 action group: `3bda23a8-b803-417d-92c4-96a4110c4bc1`
- Local mutation profile `test28-root` was valid again for target account `696505809372`.
- First post-fix grouped rerun `w6-live-05c` generated zero runnable actions because grouped persistence still dropped S3 preservation evidence before the worker called `generate_pr_bundle(...)`.
- Final closure rerun `w6-live-05d` used:
  - remediation run `453a20e2-72ee-4059-9cf7-0aa7d3f7a35a`
  - group run `25227531-815f-4066-9232-c9323ca66ec6`

## Steps Executed

1. Recreated the five temporary SaaS-account queues, restarted the retained Postgres data directory on `55442`, and restarted the main API plus worker against the retained isolated database on `127.0.0.1:18022`.
2. Generated the first post-Task-3.1 grouped rerun `w6-live-05c` and found a second live blocker:
   - `runnable_action_count = 0`
   - all seven deterministic S3.5 actions degraded to `executable_generation_failed`
   - the missing evidence was `existing_bucket_policy_json` / `existing_bucket_policy_statement_count`, proving grouped action resolutions still were not persisting the S3 preservation evidence needed by the worker
3. Patched grouped S3 family persistence so `resolve_create_profile_selection(...)` retains S3 policy preservation evidence in `strategy_inputs`, and updated the S3.5 bundle generator to honor those explicit grouped inputs without needing a per-action `risk_snapshot`.
4. Added focused regressions for grouped S3.5 evidence persistence and explicit preservation-input bundle generation, then reran the targeted suites locally.
5. Generated the final grouped rerun via `POST /api/action-groups/3bda23a8-b803-417d-92c4-96a4110c4bc1/bundle-run` and confirmed the mixed contract stayed truthful:
   - `runnable_action_count = 7`
   - `review_required_action_count = 5`
   - preservation-gated account action `c89e2c01-cda1-4d35-8945-cca8096b8b60` stayed review-only
6. Captured pre-state bucket policies for all seven executable S3 buckets by running the bundle-local `python3 scripts/s3_policy_capture.py` helper in every deterministic action folder.
7. Worked around a local Terraform provider-install hang by mirroring the cached AWS provider into `/tmp/tf-plugin-mirror` and exporting `TF_CLI_ARGS_init=-plugin-dir=/tmp/tf-plugin-mirror` for bundle execution.
8. Executed `./run_all.sh` for the final grouped bundle and verified truthful live AWS apply behavior:
   - bundle apply succeeded `7/7`
   - every executable bucket gained `DenyInsecureTransport`
   - every bucket preserved its pre-existing statements, including the multi-statement CloudTrail and Config policies
9. Replayed the saved `finished` bundle callback payload to the retained local API route `/api/internal/group-runs/report` because the generated external execute-api hostname did not resolve from this workstation, then verified group run `25227531-815f-4066-9232-c9323ca66ec6` persisted `status = finished`.
10. Executed the generated rollback path by running `terraform destroy` plus bundle-local `python3 rollback/s3_policy_restore.py` in every executable action folder.
11. Captured post-restore bucket policies and verified normalized exact-hash equality against the pre-state across all seven executable buckets.
12. Deleted the temporary SaaS-account queues and stopped the retained API, worker, and Postgres processes.

## Key Evidence

- Grouped persistence blocker evidence: [`../evidence/api/w6-live-05c-s35-group-create-response.json`](../evidence/api/w6-live-05c-s35-group-create-response.json), [`../evidence/bundles/w6-live-05c-s35-group/bundle_manifest.json`](../evidence/bundles/w6-live-05c-s35-group/bundle_manifest.json)
- Final bundle create response: [`../evidence/api/w6-live-05d-s35-group-create-response.json`](../evidence/api/w6-live-05d-s35-group-create-response.json)
- Final run detail: [`../evidence/api/w6-live-05d-s35-run-detail.json`](../evidence/api/w6-live-05d-s35-run-detail.json)
- Final bundle manifest: [`../evidence/bundles/w6-live-05d-s35-group/bundle_manifest.json`](../evidence/bundles/w6-live-05d-s35-group/bundle_manifest.json)
- Pre-state bucket policies: [`../evidence/aws/w6-live-05d-s35-pre/`](../evidence/aws/w6-live-05d-s35-pre/)
- Bundle-local pre-capture log: [`../evidence/bundles/w6-live-05d-s35-group/pre_capture.log`](../evidence/bundles/w6-live-05d-s35-group/pre_capture.log)
- Final bundle apply log: [`../evidence/bundles/w6-live-05d-s35-group/run_all-apply.log`](../evidence/bundles/w6-live-05d-s35-group/run_all-apply.log)
- Post-apply comparison: [`../evidence/aws/w6-live-05d-s35-apply-compare.json`](../evidence/aws/w6-live-05d-s35-apply-compare.json)
- Local callback acceptance proof: [`../evidence/api/w6-live-05d-s35-local-callback-finished-response.json`](../evidence/api/w6-live-05d-s35-local-callback-finished-response.json)
- Final group-run state: [`../evidence/api/w6-live-05d-s35-group-runs-post-apply.json`](../evidence/api/w6-live-05d-s35-group-runs-post-apply.json)
- Final bundle rollback log: [`../evidence/bundles/w6-live-05d-s35-group/run_all-rollback.log`](../evidence/bundles/w6-live-05d-s35-group/run_all-rollback.log)
- Final exact-restore proof: [`../evidence/aws/w6-live-05d-s35-post-restore-compare.json`](../evidence/aws/w6-live-05d-s35-post-restore-compare.json)
- Cleanup evidence: [`../evidence/aws/w6-live-05d-final-queue-post-delete-checks.txt`](../evidence/aws/w6-live-05d-final-queue-post-delete-checks.txt), [`../evidence/runtime/w6-live-05d-final-process-cleanup.txt`](../evidence/runtime/w6-live-05d-final-process-cleanup.txt)

## Assertions

- The grouped S3.5 contract remained partially executable on current `master`:
  - seven executable bucket actions
  - five review-only actions
- The preservation-gated account action `c89e2c01-cda1-4d35-8945-cca8096b8b60` stayed review-only in the final generated bundle.
- Live apply preserved the pre-existing bucket-policy statements on all seven executable buckets while appending `DenyInsecureTransport`.
- Live rollback restored exact normalized pre-state on all seven executable buckets through the bundle-local S3 policy restore helper.
- Final group run `25227531-815f-4066-9232-c9323ca66ec6` reached `finished` after the saved callback payload was replayed to the retained local API.

## Result

- Status: `PASS`
- Severity: `NONE`
- Tracker mapping: `W6-LIVE-05`

## Notes

- The first post-fix rerun `w6-live-05c` exposed a second live defect in grouped persistence rather than in the S3 bundle helpers themselves. `backend/services/remediation_profile_selection.py` now persists `existing_bucket_policy_json` and `existing_bucket_policy_statement_count` into grouped `strategy_inputs`, and `backend/services/pr_bundle.py` now honors those explicit inputs when the worker generates the executable bundle.
- External callback delivery from the generated bundle to the public execute-api hostname was still blocked by local DNS resolution, so the saved `finished` callback payload was replayed directly to the retained local API internal reporting route. The API accepted it and persisted `reporting_source = bundle_callback`.
