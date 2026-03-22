# Test 10 - Config.1 grouped rollback restoration proof on retained rerun runtime

- Wave: `Wave 6`
- Date (UTC): `2026-03-18T21:29:16Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18022`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Exact HEAD tested: `e9a362b3f543154838a72665dcd2866919b5089b`
- Local follow-up patches: `backend/services/aws_config_bundle_support.py`, `backend/services/pr_bundle.py`, `backend/workers/jobs/remediation_run.py`, `infrastructure/templates/run_all.sh`, `tests/test_step7_components.py`, `tests/test_remediation_run_worker.py`
- Local runtime workarounds: grouped Terraform execution preferred the local filesystem mirror `~/.terraform.d/plugin-cache` with `hashicorp/aws 5.100.0`, and the saved `started` plus `finished` callback payloads were replayed to the retained local API because the generated execute-api hostname did not resolve from this workstation

## Preconditions

- Retained Wave 6 rerun runtime reused from [`../notes/final-summary.md`](../notes/final-summary.md) and [`../evidence/runtime/runtime-bootstrap.json`](../evidence/runtime/runtime-bootstrap.json).
- Runtime details:
  - Postgres data dir `/tmp/rpw6-ec253-20260318T030658Z`
  - Postgres port `55442`
  - database `security_autopilot_20260318030658_w6live`
  - API `127.0.0.1:18022`
  - queue family prefix `security-autopilot-rpw6-ec253-20260318t030658z-*`
- Config.1 action group: `7ffdb496-fd8d-476e-8559-c4103b2aed1b`
- Config.1 executable action: `322fbb9e-09be-4f66-9859-0a94159a839b`
- The authoritative closure rerun used:
  - remediation run `ab371865-7d41-4eb2-94e3-91c396f438a3`
  - group run `f431340f-47d2-4bf7-8a1d-e3271c50c6b0`
- A discarded pre-authoritative rerun already proved the March 16 restore-script fix was present, but still exposed two execution blockers on current `master`:
  - the grouped runner needed the local `hashicorp/null` provider path plus lockfile refresh fallback
  - the generated `local-exec` block set `REGION` / `BUCKET` / related variables without exporting them, while `aws_config_apply.py` read them from the process environment
- Local mutation profile `test28-root` was valid for target account `696505809372`.

## Steps Executed

1. Reused the retained March 18 runtime and existing authenticated local API session instead of creating a second Wave 6 closure package.
2. Confirmed the earlier fresh Config rerun `4491053f-1a3b-4db3-806f-b674b5bdb9ae` had already cleared the grouped Terraform init defect but still failed before mutation because `aws_config_apply.py` exited with `REGION is required`.
3. Patched the remaining Config.1 bundle contract:
   - `backend/services/aws_config_bundle_support.py` now embeds bundle defaults into the generated apply and restore helpers
   - `backend/services/pr_bundle.py` now exports the dynamic Terraform values into the `local-exec` environment and passes the resolved defaults into the generated helper scripts
   - the previously added grouped runner/template lockfile-refresh fallback remained in place for the local `hashicorp/null` provider delta
4. Re-ran the focused Config bundle slice `./venv/bin/pytest tests/test_step7_components.py -q -k 'aws_config_enabled'` and confirmed `14 passed`.
5. Restarted only the retained worker against the same Postgres database and queue family so new grouped bundles used the patched code.
6. Generated the authoritative rerun with `POST /api/action-groups/7ffdb496-fd8d-476e-8559-c4103b2aed1b/bundle-run`, producing remediation run `ab371865-7d41-4eb2-94e3-91c396f438a3` and group run `f431340f-47d2-4bf7-8a1d-e3271c50c6b0`.
7. Materialized the grouped bundle under [`../evidence/bundles/w6-live-10-config-group-envfix/`](../evidence/bundles/w6-live-10-config-group-envfix/) and verified it contained:
   - `hashicorp/null = 3.2.4`
   - `terraform_init_with_lockfile_fallback`
   - exported `REGION` / `BUCKET` / `ROLE_ARN` / `ROLLBACK_DIR` lines in `aws_config_enabled.tf`
   - bundle-default `DEFAULT_REGION` wiring in both `scripts/aws_config_apply.py` and `rollback/aws_config_restore.py`
8. Captured fresh pre-apply AWS Config state:
   - recorder `default`
   - original selective `recordingGroup`
   - delivery channel `default` pointing to `config-bucket-696505809372`
   - recorder actively recording with `lastStatus = SUCCESS`
   - current bucket policy on `security-autopilot-w6-envready-config-696505809372`
9. Executed the grouped bundle from [`../evidence/bundles/w6-live-10-config-group-envfix/`](../evidence/bundles/w6-live-10-config-group-envfix/) with `AWS_PROFILE=test28-root AWS_REGION=eu-north-1 bash ./run_all.sh`.
10. Verified truthful live apply behavior:
    - apply succeeded `1/1`
    - recorder `default` and its selective `recordingGroup` stayed unchanged
    - delivery channel `default` redirected from `config-bucket-696505809372` to `security-autopilot-w6-envready-config-696505809372`
    - recorder remained active with `lastStatus = SUCCESS`
11. Executed `terraform destroy` and bundle-local `python3 rollback/aws_config_restore.py` in the executable action folder.
12. Captured post-rollback AWS Config state and verified:
    - configuration recorders matched the fresh pre-state exactly
    - delivery channels matched the fresh pre-state exactly
    - the centralized bucket policy matched the fresh pre-state exactly
    - recorder status matched after normalizing away AWS-generated stop/start timestamp metadata
13. Replayed the saved `started` and `finished` callback payloads to `http://127.0.0.1:18022/api/internal/group-runs/report` because the generated external callback URL did not resolve locally, then verified group run `f431340f-47d2-4bf7-8a1d-e3271c50c6b0` reached `status = finished` with `reporting_source = bundle_callback`.
14. Stopped the retained API, worker, and Postgres processes again and deleted the reused queue family so the retained March 18 package returned to a clean post-proof state.

## Key Evidence

- Authoritative grouped create response: [`../evidence/api/w6-live-10-config-group-create-response-envfix.json`](../evidence/api/w6-live-10-config-group-create-response-envfix.json)
- Authoritative remediation run detail: [`../evidence/api/w6-live-10-config-run-detail-post-callback-envfix.json`](../evidence/api/w6-live-10-config-run-detail-post-callback-envfix.json)
- Final group-run state after callback replay: [`../evidence/api/w6-live-10-config-group-runs-post-callback-envfix.json`](../evidence/api/w6-live-10-config-group-runs-post-callback-envfix.json)
- Callback acceptance proof: [`../evidence/api/w6-live-10-config-started-callback-status-envfix.txt`](../evidence/api/w6-live-10-config-started-callback-status-envfix.txt), [`../evidence/api/w6-live-10-config-finished-callback-status-envfix.txt`](../evidence/api/w6-live-10-config-finished-callback-status-envfix.txt)
- Final bundle apply log: [`../evidence/bundles/w6-live-10-config-group-envfix/run_all-apply.log`](../evidence/bundles/w6-live-10-config-group-envfix/run_all-apply.log)
- Terraform destroy transcript: [`../evidence/aws/w6-live-10-config-terraform-destroy-envfix.log`](../evidence/aws/w6-live-10-config-terraform-destroy-envfix.log)
- Bundle-local restore transcript: [`../evidence/aws/w6-live-10-config-rollback-restore-envfix.log`](../evidence/aws/w6-live-10-config-rollback-restore-envfix.log)
- Apply and rollback comparison summary: [`../evidence/aws/w6-live-10-config-compare-envfix.json`](../evidence/aws/w6-live-10-config-compare-envfix.json)
- Final queue cleanup proof: [`../evidence/aws/w6-live-10-final-queue-cleanup.txt`](../evidence/aws/w6-live-10-final-queue-cleanup.txt), [`../evidence/aws/w6-live-10-final-queue-post-delete-checks.txt`](../evidence/aws/w6-live-10-final-queue-post-delete-checks.txt)
- Final process cleanup proof: [`../evidence/runtime/w6-live-10-final-process-cleanup.txt`](../evidence/runtime/w6-live-10-final-process-cleanup.txt)

## Assertions

- The authoritative grouped Config.1 bundle stayed truthful on current `master`:
  - one executable action
  - zero review-required actions
  - zero manual-guidance actions
- Live apply preserved the original recorder contract while changing only the intended delivery target:
  - recorder name stayed `default`
  - selective `recordingGroup` stayed unchanged
  - delivery channel name stayed `default`
  - delivery bucket changed to `security-autopilot-w6-envready-config-696505809372`
- Bundle-local rollback restored the original AWS Config state:
  - recorder JSON matched the pre-state exactly
  - delivery-channel JSON matched the pre-state exactly
  - centralized bucket policy matched the pre-state exactly
  - recorder status returned to the same active `SUCCESS` state, with exact JSON differing only on AWS-generated `lastStartTime` / `lastStopTime` / `lastStatusChangeTime`
- Group run `f431340f-47d2-4bf7-8a1d-e3271c50c6b0` reached `finished` with `reporting_source = bundle_callback`.
- The retained local runtime and queue family were stopped and deleted again after proof capture.

## Result

- Status: `PASS`
- Severity: `NONE`
- Tracker mapping: `W6-LIVE-10`

## Notes

- The authoritative closure evidence for `W6-LIVE-10` is rerun `ab371865-7d41-4eb2-94e3-91c396f438a3` / `f431340f-47d2-4bf7-8a1d-e3271c50c6b0`.
- Earlier rerun `4491053f-1a3b-4db3-806f-b674b5bdb9ae` is retained only as discarded debug evidence for the pre-authoritative `REGION is required` bundle defect.
- The current generated restore helper does not emit a standalone `rollback_receipt.json`; the authoritative rollback proof in this package is the restore transcript plus [`../evidence/aws/w6-live-10-config-compare-envfix.json`](../evidence/aws/w6-live-10-config-compare-envfix.json).
