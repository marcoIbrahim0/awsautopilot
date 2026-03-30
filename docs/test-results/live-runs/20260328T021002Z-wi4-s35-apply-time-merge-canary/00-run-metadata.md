# Live E2E Run Metadata

- Run ID: `20260328T021002Z-wi4-s35-apply-time-merge-canary`
- Created at (UTC): `2026-03-28T02:10:02Z`
- Primary frontend target: `https://ocypheris.com`
- Primary backend target: `https://api.ocypheris.com`
- Preferred proof tenant/account from the completion plan: tenant `Valens`, account `696505809372`, region `eu-north-1`
- Retained proof environment actually used: isolated current-head local API/worker at `http://127.0.0.1:18031`
- Auth path for retained proof: local bearer for `wi4-canary-20260328@ocypheris.com`
- Environment type: `isolated_current_head_real_aws`
- Fallback used: `yes`
- Fallback reason: the first production attempt did not expose a qualifying WI-4 S3.5 candidate on the deployed runtime, so the run pivoted to the approved isolated-runtime fallback against the same real AWS account

## Local Runtime Context

- Local tenant id: `c72adafc-0989-47ec-8cce-8ecfecba1e47`
- Local user id: `7fef9b6a-8986-4e42-8ea7-2dcc65c0ac64`
- Local AWS account row id: `1be48ee9-e9cb-437d-802e-19c4e672083c`
- Local Postgres database: `wi4_wi4s3503280216`
- Local Postgres port: `55461`
- API session id during run: `21729`
- Worker session id during run: `31465`

## AWS Validation Context

- Real AWS account: `696505809372`
- Real AWS region: `eu-north-1`
- Customer mutation profile used for local execution: `AWS_PROFILE=test28-root`
- Customer mutation region env: `AWS_REGION=eu-north-1`
- Target single-run bucket: `security-autopilot-access-logs-696505809372-r221001`
- Grouped executable buckets:
  - `security-autopilot-access-logs-696505809372-r222018`
  - `security-autopilot-access-logs-696505809372-r94854`
  - `security-autopilot-access-logs-696505809372-r221001`

## Live Run IDs

- Single-run WI-4 proof
  - action id: `7a438b0e-37e8-444e-a211-04a906891a69`
  - remediation run id: `1d71393a-4250-4e3c-bf24-9e07a7d69f41`
  - strategy id: `s3_enforce_ssl_strict_deny`
- Grouped WI-4 proof
  - group id: `78d0ba9d-a8ad-4d40-9623-153acb0cb9bb`
  - grouped remediation run id: `447bf598-d864-4d0c-9311-d7cf63e47f90`
  - group run id: `a08746a9-4461-4144-84fe-d3bd23656309`
  - strategy id: `s3_enforce_ssl_strict_deny`

## Key Observations

- The canonical single-run options response for `r221001` shows the truthful WI-4 branch:
  - `support_tier=deterministic_bundle`
  - `preservation_summary.apply_time_merge=true`
  - `preservation_summary.merge_safe_policy_available=false`
  - `preservation_summary.executable_policy_merge_allowed=true`
- The live current-head create path needed one additional risk-layer fix during this closure run:
  - `backend/services/remediation_risk.py` previously kept `access_path_evidence_unavailable` at `fail` even after the resolver selected the WI-4 apply-time merge branch
  - the fix downgraded that one check to `warn` for the S3.5 apply-time merge path and was revalidated with focused tests
- The grouped proof surfaced a runner behavior nuance:
  - grouped execution succeeds and callback finalization works
  - per-action rollback snapshots created inside the temp workspace are not retained in the extracted grouped artifact after execution
  - retained grouped restore therefore used:
    - exact pre-apply restore for `r221001`
    - derived functionally equivalent restore for `r222018` and `r94854` by removing only the managed `DenyInsecureTransport` statement

## Local Validation Stamp

- `PYTHONPATH=. ./venv/bin/pytest tests/test_remediation_profile_options_preview.py -q -k 's3_5'`
  - `3 passed`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_remediation_run_resolution_create.py -q -k 's3_5'`
  - `4 passed`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_step7_components.py -q -k 's3_5 or apply_time_merge'`
  - `4 passed`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_grouped_remediation_run_service.py -q -k 's3_ssl'`
  - `2 passed`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_remediation_run_worker.py -q -k 'apply_time_merge or executable_actions'`
  - `3 passed`
- `PYTHONPATH=. ./venv/bin/pytest tests/test_internal_group_run_report.py -q -k 'replay or repair'`
  - `2 passed`
