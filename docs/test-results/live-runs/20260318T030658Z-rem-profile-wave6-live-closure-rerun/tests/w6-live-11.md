# Test 11 - grouped runner callback finalization proof on retained rerun runtime

- Wave: `Wave 6`
- Date (UTC): `2026-03-18T21:49:25Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18022`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Exact HEAD tested: `e9a362b3f543154838a72665dcd2866919b5089b`
- Local follow-up patches: none; current `master` already contained the grouped callback quoting fix in `backend/workers/jobs/remediation_run.py` and the related wrapper regressions in `tests/test_remediation_run_worker.py`
- Local runtime workarounds: reused the retained March 18 runtime and temporarily recreated the deleted queue family so the authoritative callback-managed reruns could execute on the same local API; grouped Terraform execution continued to use the local `hashicorp/aws 5.100.0` mirror already established by the retained package

## Preconditions

- Retained Wave 6 rerun runtime reused from [`../notes/final-summary.md`](../notes/final-summary.md) and [`../evidence/runtime/runtime-bootstrap.json`](../evidence/runtime/runtime-bootstrap.json).
- Runtime details:
  - Postgres data dir `/tmp/rpw6-ec253-20260318T030658Z`
  - Postgres port `55442`
  - database `security_autopilot_20260318030658_w6live`
  - API `127.0.0.1:18022`
  - queue family prefix `security-autopilot-rpw6-ec253-20260318t030658z-*`
- Verified `backend/workers/jobs/remediation_run.py` now shell-quotes all three grouped wrapper callback payload templates with `shlex.quote(json.dumps(..., separators=(",", ":")))`.
- Re-ran `./venv/bin/pytest tests/test_grouped_remediation_run_service.py tests/test_action_groups_bundle_run.py -q` and confirmed `27 passed`.
- Action groups and authoritative reruns:
  - `S3.2` group `fc1bf69d-2221-4eeb-8842-039edf8223ca` -> remediation run `bcd90932-cb5d-4910-bd49-b7b7fdf6159c` -> group run `180273f7-fa20-4f0f-b39a-6ba3d160c3e7`
  - `S3.9` group `2739b53a-77f4-4efa-8f2f-0d11cf80755f` -> remediation run `1fb320be-5d64-41c8-9483-eb0b00c696c1` -> group run `b4ff3712-0fc4-4262-8fc9-5e09d9a2724c`
  - `CloudTrail.1` group `5cee39e3-2088-43b9-bba0-27c849b40eca` -> remediation run `0abe9405-7d17-47f1-bdd9-e79be91bf1df` -> group run `29d0eaa1-6c73-42fa-8858-673d6c0144a0`
- Operator credentials `AWS_PROFILE=test28-root AWS_REGION=eu-north-1` were valid for the target account.

## Steps Executed

1. Reused the retained March 18 closure package and restarted the retained Postgres, API, and worker processes plus the temporary queue family instead of creating a second Wave 6 closure package.
2. Confirmed the current worker code already contained the expected shell-safe callback wrapper fix: all three generated callback payload templates in `backend/workers/jobs/remediation_run.py` use `shlex.quote(json.dumps(..., separators=(",", ":")))`.
3. Re-ran the targeted grouped callback regression slice `./venv/bin/pytest tests/test_grouped_remediation_run_service.py tests/test_action_groups_bundle_run.py -q` and confirmed `27 passed`.
4. Logged into the retained local API, confirmed the three already-proven grouped families were still present, and saved the relevant action inventory under [`../evidence/api/w6-live-11-relevant-actions.json`](../evidence/api/w6-live-11-relevant-actions.json).
5. Generated and executed the `S3.2` grouped bundle:
  - bundle manifest stayed truthful with `runnable_action_count = 1` and `tier_counts = { executable: 1, manual_guidance: 2, review_required: 0 }`
  - `bash ./run_all.sh` completed successfully from [`../evidence/bundles/w6-live-11-s32-group/`](../evidence/bundles/w6-live-11-s32-group/)
  - group run `180273f7-fa20-4f0f-b39a-6ba3d160c3e7` reached `status = finished` with `reporting_source = bundle_callback`
  - persisted results captured two `manual_guidance_metadata_only` rows plus one executable success row in [`../evidence/api/w6-live-11-s32-group-run-results.tsv`](../evidence/api/w6-live-11-s32-group-run-results.tsv)
6. Generated and executed the `S3.9` grouped bundle:
  - bundle manifest stayed truthful with `runnable_action_count = 1` and `tier_counts = { executable: 1, manual_guidance: 0, review_required: 11 }`
  - `bash ./run_all.sh` completed successfully from [`../evidence/bundles/w6-live-11-s39-group/`](../evidence/bundles/w6-live-11-s39-group/)
  - group run `b4ff3712-0fc4-4262-8fc9-5e09d9a2724c` reached `status = finished` with `reporting_source = bundle_callback`
  - persisted results captured eleven `review_required_metadata_only` rows plus one executable success row in [`../evidence/api/w6-live-11-s39-group-run-results.tsv`](../evidence/api/w6-live-11-s39-group-run-results.tsv)
7. Generated and executed the `CloudTrail.1` grouped bundle:
  - bundle manifest stayed truthful with `runnable_action_count = 1` and `tier_counts = { executable: 1, manual_guidance: 0, review_required: 0 }`
  - `bash ./run_all.sh` completed successfully from [`../evidence/bundles/w6-live-11-cloudtrail-group/`](../evidence/bundles/w6-live-11-cloudtrail-group/)
  - group run `29d0eaa1-6c73-42fa-8858-673d6c0144a0` reached `status = finished` with `reporting_source = bundle_callback`
8. Spot-checked all three grouped wrapper logs and confirmed none contained `command not found` or `JSONDecodeError`.
9. Restored the mutated AWS fixtures and retained runtime state:
  - `S3.2` `terraform destroy` removed the bucket public-access-block resource and an explicit `put-public-access-block` reset the bucket baseline to all `false`
  - `S3.9` `terraform destroy` removed bucket logging from `security-autopilot-w6-envready-config-696505809372`
  - `CloudTrail.1` `terraform destroy` removed trail `security-autopilot-trail`
  - retained API, worker, and Postgres were stopped again, and the recreated queue family was deleted again

## Key Evidence

- Relevant grouped action inventory: [`../evidence/api/w6-live-11-relevant-actions.json`](../evidence/api/w6-live-11-relevant-actions.json)
- `S3.2` grouped create response and final state: [`../evidence/api/w6-live-11-s32-group-create-response.json`](../evidence/api/w6-live-11-s32-group-create-response.json), [`../evidence/api/w6-live-11-s32-group-runs-post-apply.json`](../evidence/api/w6-live-11-s32-group-runs-post-apply.json)
- `S3.9` grouped create response and final state: [`../evidence/api/w6-live-11-s39-group-create-response.json`](../evidence/api/w6-live-11-s39-group-create-response.json), [`../evidence/api/w6-live-11-s39-group-runs-post-apply.json`](../evidence/api/w6-live-11-s39-group-runs-post-apply.json)
- `CloudTrail.1` grouped create response and final state: [`../evidence/api/w6-live-11-cloudtrail-group-create-response.json`](../evidence/api/w6-live-11-cloudtrail-group-create-response.json), [`../evidence/api/w6-live-11-cloudtrail-group-runs-post-apply.json`](../evidence/api/w6-live-11-cloudtrail-group-runs-post-apply.json)
- Mixed-result persistence proof: [`../evidence/api/w6-live-11-s32-group-run-results.tsv`](../evidence/api/w6-live-11-s32-group-run-results.tsv), [`../evidence/api/w6-live-11-s39-group-run-results.tsv`](../evidence/api/w6-live-11-s39-group-run-results.tsv)
- Bundle manifests: [`../evidence/bundles/w6-live-11-s32-group/bundle_manifest.json`](../evidence/bundles/w6-live-11-s32-group/bundle_manifest.json), [`../evidence/bundles/w6-live-11-s39-group/bundle_manifest.json`](../evidence/bundles/w6-live-11-s39-group/bundle_manifest.json), [`../evidence/bundles/w6-live-11-cloudtrail-group/bundle_manifest.json`](../evidence/bundles/w6-live-11-cloudtrail-group/bundle_manifest.json)
- Wrapper apply logs: [`../evidence/bundles/w6-live-11-s32-group/run_all-apply.log`](../evidence/bundles/w6-live-11-s32-group/run_all-apply.log), [`../evidence/bundles/w6-live-11-s39-group/run_all-apply.log`](../evidence/bundles/w6-live-11-s39-group/run_all-apply.log), [`../evidence/bundles/w6-live-11-cloudtrail-group/run_all-apply.log`](../evidence/bundles/w6-live-11-cloudtrail-group/run_all-apply.log)
- AWS cleanup proof: [`../evidence/aws/w6-live-11-s32-post-cleanup-public-access-block.json`](../evidence/aws/w6-live-11-s32-post-cleanup-public-access-block.json), [`../evidence/aws/w6-live-11-s39-post-cleanup-bucket-logging.json`](../evidence/aws/w6-live-11-s39-post-cleanup-bucket-logging.json), [`../evidence/aws/w6-live-11-cloudtrail-post-cleanup-describe-trails.json`](../evidence/aws/w6-live-11-cloudtrail-post-cleanup-describe-trails.json)
- Final queue/process cleanup proof: [`../evidence/aws/w6-live-11-final-queue-cleanup.txt`](../evidence/aws/w6-live-11-final-queue-cleanup.txt), [`../evidence/aws/w6-live-11-final-queue-post-delete-checks.txt`](../evidence/aws/w6-live-11-final-queue-post-delete-checks.txt), [`../evidence/runtime/w6-live-11-final-process-cleanup.txt`](../evidence/runtime/w6-live-11-final-process-cleanup.txt)

## Assertions

- The grouped wrapper callback fix already on current `master` now proves out on the supported customer-run bundle path:
  - `S3.2` group run `180273f7-fa20-4f0f-b39a-6ba3d160c3e7` finished via `bundle_callback`
  - `S3.9` group run `b4ff3712-0fc4-4262-8fc9-5e09d9a2724c` finished via `bundle_callback`
  - `CloudTrail.1` group run `29d0eaa1-6c73-42fa-8858-673d6c0144a0` finished via `bundle_callback`
- Mixed grouped bundles now persist metadata-only non-executable outcomes instead of losing them during wrapper finalization:
  - `S3.2` persisted two `manual_guidance_metadata_only` rows
  - `S3.9` persisted eleven `review_required_metadata_only` rows
- None of the three grouped wrapper logs contained `command not found` or `JSONDecodeError`.
- The retained runtime and queue family were cleaned again after proof capture, and all three AWS fixtures were restored to baseline.

## Result

- Status: `PASS`
- Severity: `NONE`
- Tracker mapping: `W6-LIVE-11`

## Notes

- The public group-run API proves terminal `finished` state and `reporting_source = bundle_callback`, but it does not expose per-action metadata-only outcomes directly. The authoritative persistence proof for non-executable grouped members in this package is the saved `action_group_run_results` TSV output.
- The retained queue family briefly continued to appear in `list-queues` immediately after deletion, but every direct `GetQueueAttributes` probe already returned `AWS.SimpleQueueService.NonExistentQueue`, and the delayed list check in [`../evidence/aws/w6-live-11-final-queue-post-delete-checks.txt`](../evidence/aws/w6-live-11-final-queue-post-delete-checks.txt) eventually returned `None`.
