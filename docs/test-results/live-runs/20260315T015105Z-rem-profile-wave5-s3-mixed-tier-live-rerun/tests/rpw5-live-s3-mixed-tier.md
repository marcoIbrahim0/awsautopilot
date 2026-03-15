# Test - Wave 5 narrowed live S3.9 mixed-tier executable grouped proof

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T02:50:00Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18006`
- Branch tested: `master`

## Preconditions

- Isolated runtime:
  - Postgres: `security_autopilot_rpw5_s39` on `127.0.0.1:55433`
  - Backend: `http://127.0.0.1:18006`
  - Worker: local queue consumer against isolated SQS queues
- Source live AWS-backed evidence package:
  - [20260315T001855Z-rem-profile-wave5-live-aws-e2e](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T001855Z-rem-profile-wave5-live-aws-e2e/notes/final-summary.md)
- Exact grouped family under test:
  - `s3_bucket_access_logging`
  - group `75cd4f50-97c9-4aa0-911b-eb3b17ffd804`
  - bucket action `bb487cfd-2d28-41a6-8ec3-5f685e4eaa26`
  - account action `47c023ae-945c-42bf-9b44-018d276046fa`

## Steps Executed

1. Confirmed the narrowed product bug required code changes, not only different live data: `s3_enable_access_logging_guided` had no specialization and both live S3.9 actions collapsed into `risk_evaluation_not_specialized`.
2. Added the narrow S3.9 risk specialization and focused tests on current `master`.
3. Confirmed a fresh direct `AssumeRole` into `arn:aws:iam::696505809372:role/SecurityAutopilotReadRole` now returned `AccessDenied`, so this rerun did not widen into target-account IAM repair.
4. Restored the exact March 15, 2026 live-ingested S3.9 group records from the earlier Wave 5 evidence package into the isolated runtime for the current tenant.
5. Verified the restored actions now split correctly through the current API:
   - bucket action remediation options exposed `s3_access_logging_bucket_scope_confirmed = pass`
   - account action remediation options exposed `s3_access_logging_scope_requires_review = warn`
6. Created a real grouped bundle run through `POST /api/action-groups/{group_id}/bundle-run` with:
   - `strategy_id = s3_enable_access_logging_guided`
   - `strategy_inputs.log_bucket_name = security-autopilot-access-logs-696505809372`
   - `risk_acknowledged = true`
7. Waited for the worker to complete the grouped remediation run and extracted the generated bundle files from the persisted run artifacts.

## API Evidence

| # | Method | Endpoint | HTTP | Observed | Artifact Path |
|---|---|---|---|---|---|
| 1 | `GET` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804` | `200` | Restored live S3.9 group visible with both expected members | [s3-live-group-detail-restored.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/api/s3-live-group-detail-restored.json) |
| 2 | `GET` | `/api/actions/bb487cfd-2d28-41a6-8ec3-5f685e4eaa26/remediation-options` | `200` | Bucket-scoped S3.9 action now specialized to executable path | [s3-live-bucket-action-options.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/api/s3-live-bucket-action-options.json) |
| 3 | `GET` | `/api/actions/47c023ae-945c-42bf-9b44-018d276046fa/remediation-options` | `200` | Account-scoped S3.9 action now downgraded to review-required | [s3-live-account-action-options.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/api/s3-live-account-action-options.json) |
| 4 | `POST` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804/bundle-run` | `201` | Grouped bundle run created | [s3-live-group-bundle-run-request.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/api/s3-live-group-bundle-run-request.json), [s3-live-group-bundle-run-response.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/api/s3-live-group-bundle-run-response.json) |
| 5 | `GET` | `/api/remediation-runs/3feb85a9-2845-4ee3-b4f2-2530ff0eb0c7` | `200` | Worker completed `success` with `Group PR bundle generated (2 actions)` | [s3-live-remediation-run-summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/api/s3-live-remediation-run-summary.json) |
| 6 | `GET` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804/runs` | `200` | Group run finished cleanly | [s3-live-group-runs.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/api/s3-live-group-runs.json) |

## Bundle Contract Evidence

- Extracted bundle root:
  - [generated-bundle/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle)
- Contract check:
  - [s3-live-bundle-contract-check.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/api/s3-live-bundle-contract-check.json)

Required files present:

- [bundle_manifest.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/bundle_manifest.json)
- [decision_log.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/decision_log.md)
- [finding_coverage.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/finding_coverage.json)
- [README_GROUP.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/README_GROUP.txt)
- [run_all.sh](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/run_all.sh)

Observed mixed-tier folders:

- Executable:
  - [executable/actions/01-arn-aws-s3-config-bucket-696505809372-bb487cfd](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/executable/actions/01-arn-aws-s3-config-bucket-696505809372-bb487cfd)
- Metadata-only review:
  - [review_required/actions/02-aws-account-696505809372-47c023ae](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/review_required/actions/02-aws-account-696505809372-47c023ae)

## Assertions

- Mixed-tier executable grouped case exists on real AWS-backed data: `pass`
- At least one `deterministic_bundle` action exists: `pass`
- At least one `review_required_bundle` action exists: `pass`
- Manifest shows both executable and metadata-only action records: `pass`
- Generated bundle includes the required top-level files: `pass`
- Runnable Terraform is confined to `executable/actions/...`: `pass`
- Metadata-only output is confined to `review_required/actions/...`: `pass`

## Result

- Status: `PASS`
- Severity: `closure evidence`
- Primary tracker mapping: `Wave 5 / mixed-tier executable grouped proof`

## Notes

- This rerun closed the product gap with the narrow S3.9 specialization fix. It did not widen into repairing target-account IAM trust.
- A fresh end-to-end live ingest rerun against account `696505809372` still needs the target `SecurityAutopilotReadRole` trust restored, but that is an environment issue rather than a remaining grouped-bundle product bug.
