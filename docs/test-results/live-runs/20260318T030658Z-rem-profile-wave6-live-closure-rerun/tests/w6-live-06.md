# Test 06 - S3.11 grouped lifecycle live proof closure on retained rerun runtime

- Wave: `Wave 6`
- Date (UTC): `2026-03-18T18:45:43Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18022`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Exact HEAD tested: `e9a362b3f543154838a72665dcd2866919b5089b`
- Local follow-up patches: `backend/workers/jobs/remediation_run.py`, `infrastructure/templates/run_all.sh`, `tests/test_remediation_run_worker.py`
- Local runtime workarounds: temporary read-only bucket policy added on `security-autopilot-w6-strict-s315-exec-696505809372` so the import role could read lifecycle state; final rollback used the generated `delete-bucket-lifecycle` note command because the downloaded clean bundle did not retain a trustworthy local `terraform destroy` transcript

## Preconditions

- Retained Wave 6 rerun runtime reused from [`../notes/final-summary.md`](../notes/final-summary.md) and [`../evidence/runtime/runtime-bootstrap.json`](../evidence/runtime/runtime-bootstrap.json).
- Runtime details:
  - Postgres data dir `/tmp/rpw6-ec253-20260318T030658Z`
  - Postgres port `55442`
  - database `security_autopilot_20260318030658_w6live`
  - API `127.0.0.1:18022`
  - queue family prefix `security-autopilot-rpw6-ec253-20260318t030658z-*`
- S3.11 action group: `e9941072-b1ce-4355-b710-c8412485d3b8`
- The clean authoritative closure rerun used:
  - remediation run `14870ea9-3e0c-4d33-a6b8-fada6e821eef`
  - group run `9f911a39-df7d-46c1-b11a-2b58b6218fe8`
- The truthful executable/manual split for this group was:
  - executable action `d3be1c75-24ec-4462-b860-c5b2628ea18b` on bucket `security-autopilot-w6-strict-s315-exec-696505809372`
  - manual-guidance actions `a105bf6a-bfd5-413e-9730-e9df4dc74285`, `a62cdfeb-9177-426f-a615-222c089b347e`, `e755b2ce-bea6-4e48-8a13-d5978e01cd1d`, and `aba1694d-1c2a-42e8-92b7-6fbe34b7d310`

## Steps Executed

1. Reused the retained March 18 runtime, queues, and local API/worker process family instead of creating a second isolated package.
2. Refreshed the executable/manual S3.11 options and confirmed only bucket `security-autopilot-w6-strict-s315-exec-696505809372` remained executable while the four other S3.11 members stayed manual-guidance only.
3. Added a narrow temporary read-only bucket policy on `security-autopilot-w6-strict-s315-exec-696505809372` so the import role could read lifecycle and policy state for the executable branch, then captured the changed policy artifact.
4. Captured the first grouped rerun failure and confirmed the old runner defect: the grouped bootstrap reused the same directory for plugin cache and filesystem mirror, so `terraform init` failed with the provider-self-install path conflict.
5. Patched the grouped runner and shared template to separate plugin cache from provider mirror while keeping the Terraform AWS provider bootstrap aligned to the bundle's `>= 4.0` constraint, then added focused regressions.
6. Hardened provider detection to use `find -L` after the retained rerun exposed a symlinked local cache case that the previous probe missed.
7. Generated the clean grouped rerun via `POST /api/action-groups/e9941072-b1ce-4355-b710-c8412485d3b8/bundle-run` and confirmed the bundle stayed truthful:
   - `runnable_action_count = 1`
   - `executable_action_count = 1`
   - `manual_guidance_action_count = 4`
   - `review_required_action_count = 0`
8. Captured pre-apply lifecycle state on the executable bucket and confirmed it started with `NoSuchLifecycleConfiguration`.
9. Executed the clean grouped bundle from [`../evidence/bundles/w6-live-06-s311-group-clean/`](../evidence/bundles/w6-live-06-s311-group-clean/) and verified that only the executable bucket gained the `security-autopilot-abort-incomplete-multipart` rule with `DaysAfterInitiation = 7`.
10. Verified the callback-managed group run persisted `status = finished` with `reporting_source = bundle_callback`.
11. Restored exact fixture state by running the generated rollback note command `aws s3api delete-bucket-lifecycle --bucket security-autopilot-w6-strict-s315-exec-696505809372`, then confirmed the executable bucket again returned `NoSuchLifecycleConfiguration`.
12. Deleted the temporary read-only bucket policy and verified the bucket again returned `NoSuchBucketPolicy`, then deleted the five temporary SaaS-account queues and stopped the retained API, worker, and Postgres processes.

## Key Evidence

- Runtime bootstrap: [`../evidence/runtime/runtime-bootstrap.json`](../evidence/runtime/runtime-bootstrap.json)
- Executable-branch options: [`../evidence/api/w6-live-06-d3be1c75-24ec-4462-b860-c5b2628ea18b-remediation-options-post-ingest.json`](../evidence/api/w6-live-06-d3be1c75-24ec-4462-b860-c5b2628ea18b-remediation-options-post-ingest.json)
- Manual-branch options: [`../evidence/api/w6-live-06-e755b2ce-bea6-4e48-8a13-d5978e01cd1d-remediation-options-post-ingest.json`](../evidence/api/w6-live-06-e755b2ce-bea6-4e48-8a13-d5978e01cd1d-remediation-options-post-ingest.json)
- Initial grouped runner failure state: [`../evidence/api/w6-live-06-group-runs-after-init-failure.json`](../evidence/api/w6-live-06-group-runs-after-init-failure.json)
- Temporary executable-bucket policy addition: [`../evidence/aws/w6-live-06-post-change-strict-s315-exec-policy.json`](../evidence/aws/w6-live-06-post-change-strict-s315-exec-policy.json)
- Clean grouped create response: [`../evidence/api/w6-live-06-action-group-bundle-run-response-clean.json`](../evidence/api/w6-live-06-action-group-bundle-run-response-clean.json)
- Clean remediation run detail: [`../evidence/api/w6-live-06-action-group-run-detail-clean-poll-2.json`](../evidence/api/w6-live-06-action-group-run-detail-clean-poll-2.json)
- Clean bundle tree: [`../evidence/bundles/w6-live-06-s311-group-clean.tree`](../evidence/bundles/w6-live-06-s311-group-clean.tree)
- Clean bundle apply log: [`../evidence/bundles/w6-live-06-s311-group-clean/run_all-apply.log`](../evidence/bundles/w6-live-06-s311-group-clean/run_all-apply.log)
- Pre-apply lifecycle absence: [`../evidence/aws/w6-live-06-pre-apply-clean-strict-s315-exec-lifecycle.err`](../evidence/aws/w6-live-06-pre-apply-clean-strict-s315-exec-lifecycle.err)
- Post-apply lifecycle state: [`../evidence/aws/w6-live-06-post-apply-clean-strict-s315-exec-lifecycle.json`](../evidence/aws/w6-live-06-post-apply-clean-strict-s315-exec-lifecycle.json)
- Clean group-run terminal state: [`../evidence/api/w6-live-06-group-runs-after-clean-apply.json`](../evidence/api/w6-live-06-group-runs-after-clean-apply.json)
- Rollback command transcript: [`../evidence/bundles/w6-live-06-s311-group-clean/rollback-delete-bucket-lifecycle.log`](../evidence/bundles/w6-live-06-s311-group-clean/rollback-delete-bucket-lifecycle.log)
- Post-rollback lifecycle absence: [`../evidence/aws/w6-live-06-post-rollback-clean-strict-s315-exec-lifecycle.err`](../evidence/aws/w6-live-06-post-rollback-clean-strict-s315-exec-lifecycle.err)
- Post-cleanup policy absence: [`../evidence/aws/w6-live-06-post-cleanup-strict-s315-exec-policy.err`](../evidence/aws/w6-live-06-post-cleanup-strict-s315-exec-policy.err)
- Final queue cleanup: [`../evidence/aws/w6-live-06-final-queue-post-delete-checks.txt`](../evidence/aws/w6-live-06-final-queue-post-delete-checks.txt)
- Final process cleanup: [`../evidence/runtime/w6-live-06-final-process-cleanup.txt`](../evidence/runtime/w6-live-06-final-process-cleanup.txt)

## Assertions

- The clean grouped S3.11 bundle stayed truthful on current `master`:
  - one executable lifecycle action
  - four manual-guidance-only actions
  - zero review-required actions
- The manual branch stayed non-executable throughout the authoritative clean rerun.
- Live apply added exactly one lifecycle rule on the executable bucket:
  - rule ID `security-autopilot-abort-incomplete-multipart`
  - `DaysAfterInitiation = 7`
- Group run `9f911a39-df7d-46c1-b11a-2b58b6218fe8` reached `finished` with `reporting_source = bundle_callback`.
- Final AWS fixture state was fully restored:
  - executable bucket lifecycle returned `NoSuchLifecycleConfiguration`
  - temporary read-only bucket policy was removed and now returns `NoSuchBucketPolicy`
  - the four manual-guidance actions remained non-mutated throughout

## Result

- Status: `PASS`
- Severity: `NONE`
- Tracker mapping: `W6-LIVE-06`

## Notes

- The authoritative closure evidence for `W6-LIVE-06` is the clean rerun `14870ea9-3e0c-4d33-a6b8-fada6e821eef` / `9f911a39-df7d-46c1-b11a-2b58b6218fe8`.
- The earlier callback-aware rerun `0f8bbe08-ef67-421d-b3ec-3143a65b96fe` / `8e0e85dc-8e35-48c4-b263-eabae94cffa2` is retained only as noisy debug evidence and should not be used as the pass claim.
- The clean rollback transcript file is empty because the final `aws s3api delete-bucket-lifecycle` command succeeded silently; the authoritative rollback proof is the post-rollback `NoSuchLifecycleConfiguration` evidence.
