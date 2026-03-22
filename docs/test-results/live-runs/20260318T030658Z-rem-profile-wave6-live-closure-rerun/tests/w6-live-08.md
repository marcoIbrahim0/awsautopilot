# Test 08 - S3.15 grouped SSE-KMS live proof closure on retained rerun runtime

- Wave: `Wave 6`
- Date (UTC): `2026-03-18T20:45:42Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18022`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Exact HEAD tested: `e9a362b3f543154838a72665dcd2866919b5089b`
- Local follow-up patches: `backend/services/aws_s3_encryption_bundle_support.py`, `backend/services/pr_bundle.py`, `backend/services/remediation_strategy.py`, `backend/workers/jobs/remediation_run.py`, `infrastructure/templates/run_all.sh`, `tests/test_step7_components.py`, `tests/test_remediation_runs_api.py`, `tests/test_remediation_run_worker.py`
- Local runtime workarounds: grouped Terraform execution now prefers the local filesystem mirror `~/.terraform.d/plugin-cache` with `hashicorp/aws 5.100.0` because the retained `6.31.0` and downloaded `6.36.0` darwin_arm64 providers crash with `SIGILL`; saved `started` and `finished` callback payloads were replayed to the retained local API because the generated execute-api hostname did not resolve from this workstation

## Preconditions

- Retained Wave 6 rerun runtime reused from [`../notes/final-summary.md`](../notes/final-summary.md) and [`../evidence/runtime/runtime-bootstrap.json`](../evidence/runtime/runtime-bootstrap.json).
- Runtime details:
  - Postgres data dir `/tmp/rpw6-ec253-20260318T030658Z`
  - Postgres port `55442`
  - database `security_autopilot_20260318030658_w6live`
  - API `127.0.0.1:18022`
  - queue family prefix `security-autopilot-rpw6-ec253-20260318t030658z-*`
- S3.15 action group: `743ec36e-958e-4b70-8fdf-d5e1c237543e`
- The authoritative closure rerun used:
  - remediation run `53650698-fb06-4cc3-9ff4-b201e588cd75`
  - group run `0a3154d4-0870-438f-bcf5-b96e98b83958`
- The truthful executable and review split for this group was:
  - ten executable AWS-managed KMS actions
  - one review-required customer-managed KMS action `52947557-0b35-4c03-99d6-4fdf77c86a24` on bucket `security-autopilot-w6-strict-s315-manual-696505809372` with `blocked_reasons = ["AccessDeniedException"]`
- Local mutation profile `test28-root` was valid again for target account `696505809372`.

## Steps Executed

1. Reused the retained March 18 runtime and evidence package under [`../`](../) instead of creating a second Wave 6 closure package.
2. Implemented the missing S3.15 exact-rollback support:
   - added bundle-local encryption capture and restore helpers in `backend/services/aws_s3_encryption_bundle_support.py`
   - wired those helpers plus real `bundle_rollback_entries` into the S3.15 Terraform bundle generator
   - updated generic rollback guidance so `s3_bucket_encryption_kms` no longer implies an inexact fallback
3. Hardened the grouped Terraform runner and shared template for the retained workstation reality:
   - prefer `~/.terraform.d/plugin-cache` as the filesystem mirror
   - pin the AWS provider to `5.100.0`
   - keep plugin cache and provider mirror separate
4. Added focused S3.15 bundle, rollback-guidance, and grouped-runner regressions, then reran the targeted pytest slices locally.
5. Generated the final grouped rerun via `POST /api/action-groups/743ec36e-958e-4b70-8fdf-d5e1c237543e/bundle-run` and confirmed the bundle stayed truthful:
   - executable results `10`
   - review-required results `1`
   - the only non-executable action stayed on the customer-managed branch with `blocked_reasons = ["AccessDeniedException"]`
6. Captured clean pre-apply encryption state for all 11 grouped buckets and confirmed the new `w6-live-08g` baseline matched the earlier clean `08f` pre-state exactly.
7. Executed the final grouped bundle from [`../evidence/bundles/w6-live-08g-s315-group/`](../evidence/bundles/w6-live-08g-s315-group/) and verified truthful live AWS apply behavior:
   - `run_actions.sh` completed successfully `10/10`
   - the ten executable buckets moved to AWS-managed SSE-KMS with `alias/aws/s3`
   - the review-required customer-managed fixture bucket stayed at its original `AES256` baseline
8. Replayed the saved `started` and `finished` callback payloads to the retained local API route `/api/internal/group-runs/report` because the generated external execute-api hostname did not resolve from this workstation, then verified group run `0a3154d4-0870-438f-bcf5-b96e98b83958` persisted `status = finished` with `reporting_source = bundle_callback`.
9. The first rollback attempt from a fresh shell used the default SaaS-account profile and failed cross-account with `AccessDenied`; that log was preserved only as debug evidence.
10. Rewrote each executable action folder's `.s3-encryption-rollback/encryption_snapshot.json` from the saved pre-apply JSON, then reran the rollback under `AWS_PROFILE=test28-root AWS_REGION=eu-north-1`.
11. Executed `terraform destroy` plus bundle-local `python3 rollback/s3_encryption_restore.py` in every executable S3.15 action folder.
12. Captured post-rollback bucket encryption state for all 11 buckets and verified exact normalized JSON equality against the pre-apply snapshots.

## Key Evidence

- Final grouped create response: [`../evidence/api/w6-live-08g-s315-group-create-response.json`](../evidence/api/w6-live-08g-s315-group-create-response.json)
- Final group-run state after callbacks: [`../evidence/api/w6-live-08g-s315-group-runs-post-callback.json`](../evidence/api/w6-live-08g-s315-group-runs-post-callback.json)
- Final remediation run detail: [`../evidence/api/w6-live-08g-s315-run-detail-post-callback.json`](../evidence/api/w6-live-08g-s315-run-detail-post-callback.json)
- Callback acceptance proof: [`../evidence/api/w6-live-08g-started-callback-status.txt`](../evidence/api/w6-live-08g-started-callback-status.txt), [`../evidence/api/w6-live-08g-finished-callback-status.txt`](../evidence/api/w6-live-08g-finished-callback-status.txt)
- Final bundle manifest: [`../evidence/bundles/w6-live-08g-s315-group/bundle_manifest.json`](../evidence/bundles/w6-live-08g-s315-group/bundle_manifest.json)
- Final bundle apply log: [`../evidence/bundles/w6-live-08g-s315-group/run_actions-apply.log`](../evidence/bundles/w6-live-08g-s315-group/run_actions-apply.log)
- Pre-apply encryption snapshots: [`../evidence/aws/w6-live-08g-pre-apply/`](../evidence/aws/w6-live-08g-pre-apply/)
- Post-apply comparison: [`../evidence/aws/w6-live-08g-post-apply/compare-to-pre.tsv`](../evidence/aws/w6-live-08g-post-apply/compare-to-pre.tsv)
- Final rollback transcript: [`../evidence/aws/w6-live-08g-rollback.log`](../evidence/aws/w6-live-08g-rollback.log)
- Post-rollback exact-restore proof: [`../evidence/aws/w6-live-08g-post-rollback/compare-to-pre.tsv`](../evidence/aws/w6-live-08g-post-rollback/compare-to-pre.tsv)
- Wrong-profile debug log from the discarded rollback attempt: [`../evidence/aws/w6-live-08g-rollback-wrong-profile.log`](../evidence/aws/w6-live-08g-rollback-wrong-profile.log)

## Assertions

- The final grouped S3.15 bundle stayed truthful on current `master`:
  - ten executable AWS-managed SSE-KMS actions
  - one review-required customer-managed KMS action
  - zero manual-guidance actions
- Live apply changed only the executable action set:
  - the ten executable buckets moved from `AES256` to `aws:kms|arn:aws:kms:eu-north-1:696505809372:alias/aws/s3`
  - the customer-managed review-required bucket stayed `AES256`
- Group run `0a3154d4-0870-438f-bcf5-b96e98b83958` reached `finished` with `reporting_source = bundle_callback`.
- Final AWS fixture state was fully restored:
  - all ten executable buckets returned to their exact captured pre-apply encryption JSON
  - the review-required customer-managed bucket remained unchanged throughout
  - post-rollback comparison shows all 11 buckets `match`

## Result

- Status: `PASS`
- Severity: `NONE`
- Tracker mapping: `W6-LIVE-08`

## Notes

- The authoritative closure evidence for `W6-LIVE-08` is the clean rerun `53650698-fb06-4cc3-9ff4-b201e588cd75` / `0a3154d4-0870-438f-bcf5-b96e98b83958`.
- The first rollback attempt under the default `AutoPilotAdmin` SaaS-account identity is intentionally retained only as a discarded debug transcript. Exact rollback proof uses the target-account root mutation profile `test28-root`.
- On this workstation, `hashicorp/aws` `6.31.0` and `6.36.0` crash with `SIGILL`. The authoritative live proof therefore uses the grouped runner and shared template logic that prefer the local `5.100.0` filesystem mirror and preserve lockfile bootstrap against that mirror.
