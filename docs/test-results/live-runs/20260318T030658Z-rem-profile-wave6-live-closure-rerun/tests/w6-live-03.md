# Test 03 - IAM.4 authoritative disable + rollback proof on retained rerun runtime

- Wave: `Wave 6`
- Date (UTC): `2026-03-18T14:58:22Z`
- Tester: `Codex`
- Backend URLs:
  - main API `http://127.0.0.1:18022`
  - authoritative root-key API `http://127.0.0.1:18021`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Exact HEAD tested: `e9a362b3f543154838a72665dcd2866919b5089b`
- Local follow-up patches: `backend/services/root_key_remediation_executor_worker.py`, `tests/test_root_key_remediation_executor_worker.py`

## Preconditions

- Retained Wave 6 rerun runtime reused from [`../notes/final-summary.md`](../notes/final-summary.md).
- Generic IAM.4 action: `ab24939a-ffe5-41ba-b92f-8d46ed80b1f7`
- Observer base context remained configured as profile `default`.
- The target account was prepared with two long-lived root keys before the fresh rerun:
  - caller key `<REDACTED_AWS_ACCESS_KEY_ID>` `Active`
  - disposable key `<REDACTED_AWS_ACCESS_KEY_ID>` `Active`
- The retained observer role `CodexP2SecurityHubImportRole` can assume into the target account, but it cannot call `iam:GetAccountSummary`; the preserved caller root session can.

## Steps Executed

1. Recreated the five temporary SaaS-account queues, restarted the retained Postgres data directory on `5432`, reran Alembic, and restarted the main API, authoritative root-key API, and worker against the retained isolated database.
2. Captured fresh AWS baseline evidence:
   - `default` successfully assumed `arn:aws:iam::696505809372:role/CodexP2SecurityHubImportRole`
   - both target-account root keys were `Active`
3. Replayed the earlier blocked retained run `01e495a2-291a-4b2d-b02b-6ec77a8c4145` and found a second real defect:
   - the caller key was preserved and the disposable key was disabled
   - the automatic breakage-signal rollback path marked the run `rolled_back`
   - but it did not reactivate the disabled key before returning
4. Patched the root-key executor worker so:
   - automatic rollback on breakage signals now reactivates inactive root keys and records a truthful rollback summary
   - post-disable health and usage signal collection can fall back to the preserved mutation session when the separate observer role lacks CloudTrail / IAM read permissions
5. Added focused worker regressions for both fixes and reran the affected root-key suites.
6. Restarted the authoritative root-key API on the patched workspace and created a fresh IAM.4 run:
   - fresh run `aecccbd7-6c3a-4619-94ce-b1a5b9732b98`
7. Called `POST /api/root-key-remediation-runs/aecccbd7-6c3a-4619-94ce-b1a5b9732b98/disable` and verified:
   - response `200`
   - run advanced to `disable_window/running`
   - disposable key became `Inactive`
   - caller key stayed `Active`
8. Queried artifact metadata from the isolated DB and confirmed the disable evidence recorded:
   - `window_clean = true`
   - `breakage_signals = []`
   - `caller_key_preserved = "AKIA...IFNM"`
9. Called `POST /api/root-key-remediation-runs/aecccbd7-6c3a-4619-94ce-b1a5b9732b98/rollback` and verified:
   - response `200`
   - run moved to `rolled_back`
   - rollback summary recorded `reactivated_count = 1`
   - both root keys returned to `Active`
10. Revalidated the generic IAM.4 `remediation-options` and `remediation-preview` surfaces; both remained metadata-only with `manual_guidance_only` authority routing to `/api/root-key-remediation-runs`.
11. Deleted the disposable March 15 root key after proof capture, leaving only the current March 18 caller key active, then stopped the local runtime and deleted the temporary queues again.

## Key Evidence

- Fresh generic options: [`../evidence/api/w6-live-03-iam4-options-fresh.json`](../evidence/api/w6-live-03-iam4-options-fresh.json)
- Fresh generic preview: [`../evidence/api/w6-live-03-iam4-preview-fresh.json`](../evidence/api/w6-live-03-iam4-preview-fresh.json)
- Fresh create response: [`../evidence/api/w6-live-03-iam4-create-response-rerun.json`](../evidence/api/w6-live-03-iam4-create-response-rerun.json)
- Fresh disable response: [`../evidence/api/w6-live-03-iam4-disable-response-rerun.json`](../evidence/api/w6-live-03-iam4-disable-response-rerun.json)
- Fresh rollback response: [`../evidence/api/w6-live-03-iam4-rollback-response-rerun.json`](../evidence/api/w6-live-03-iam4-rollback-response-rerun.json)
- Fresh run detail after disable: [`../evidence/api/w6-live-03-run-after-disable-rerun.json`](../evidence/api/w6-live-03-run-after-disable-rerun.json)
- Fresh run detail after rollback: [`../evidence/api/w6-live-03-run-after-rollback-rerun.json`](../evidence/api/w6-live-03-run-after-rollback-rerun.json)
- Fresh AWS pre-state with two active keys: [`../evidence/aws/w6-live-03-iam4-two-active-pre-rerun.json`](../evidence/aws/w6-live-03-iam4-two-active-pre-rerun.json)
- Fresh AWS state after disable: [`../evidence/aws/w6-live-03-iam4-post-disable-rerun-list-access-keys.json`](../evidence/aws/w6-live-03-iam4-post-disable-rerun-list-access-keys.json)
- Fresh AWS state after rollback: [`../evidence/aws/w6-live-03-iam4-post-rollback-rerun-list-access-keys.json`](../evidence/aws/w6-live-03-iam4-post-rollback-rerun-list-access-keys.json)
- Final AWS state after deleting the disposable key: [`../evidence/aws/w6-live-03-final-list-access-keys.json`](../evidence/aws/w6-live-03-final-list-access-keys.json)
- Disable + rollback artifact metadata, including `caller_key_preserved`: [`../evidence/runtime/w6-live-03-rerun-artifact-metadata.tsv`](../evidence/runtime/w6-live-03-rerun-artifact-metadata.tsv)
- Observer-permission evidence:
  - [`../evidence/aws/w6-live-03-observer-assume-role.json`](../evidence/aws/w6-live-03-observer-assume-role.json)
  - [`../evidence/aws/w6-live-03-observer-get-account-summary.err`](../evidence/aws/w6-live-03-observer-get-account-summary.err)
  - [`../evidence/aws/w6-live-03-root-get-account-summary.json`](../evidence/aws/w6-live-03-root-get-account-summary.json)

## Assertions

- Generic IAM.4 routes remained additive metadata only and did not expose a generic executable path.
- The authoritative disable route now truthfully bridges `migration -> validation -> disable_window` on the live path.
- The executor worker now preserves the current caller key and records that preservation explicitly in disable evidence.
- Post-disable signal capture can stay clean even when the observer role lacks `iam:GetAccountSummary`, because the preserved mutation caller can safely provide those post-disable reads.
- Fresh live disable proof is present:
  - response `200`
  - state `disable_window`
  - disposable key `Inactive`
  - caller key still `Active`
- Fresh live rollback proof is present:
  - response `200`
  - run state `rolled_back`
  - disposable key reactivated
  - final cleanup deleted the disposable key again

## Result

- Status: `PASS`
- Severity: `NONE`
- Tracker mapping: `W6-LIVE-03`

## Notes

- Validation command: `./venv/bin/pytest tests/test_root_key_remediation_executor_worker.py tests/test_root_key_remediation_runs_api.py -q` -> `40 passed in 0.33s`
- The rollback terminal contract still uses `state = rolled_back` with `status = failed`; this rerun treated the state transition as authoritative for the rollback proof.
- The current March 18 caller key was pasted into the chat earlier in the thread. Rotate or delete it after the remaining Wave 6 live tasks are finished.
