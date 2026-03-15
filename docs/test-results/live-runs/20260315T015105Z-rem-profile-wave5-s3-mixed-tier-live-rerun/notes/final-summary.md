# Wave 5 narrowed live S3.9 mixed-tier executable rerun summary

- Wave: `Remediation-profile Wave 5 narrowed live rerun`
- Date (UTC): `2026-03-15T02:50:00Z`
- Environment used: `local master against isolated backend http://127.0.0.1:18006 plus isolated Postgres/SQS, using real AWS-backed S3.9 action records captured on March 15, 2026`
- Branch tested: `master`
- AWS account referenced by the proven scenario: `696505809372`
- Region used: `eu-north-1`

## Outcome

- Product result: `PASS`
- Product gap type: `required narrow code change`
- Exact family used for proof: `s3_bucket_access_logging` / `S3.9`

## Root Cause Closed

- `s3_enable_access_logging_guided` had no family-specific specialization in [remediation_risk.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_risk.py).
- Both S3.9 actions therefore emitted `risk_evaluation_not_specialized`, and grouped resolution collapsed the real mixed-scope family into all-review when `risk_acknowledged=true`.
- The fix specialized bucket-scoped S3.9 actions into an executable path and explicitly downgraded account-scoped S3.9 actions to review-required.

## Exact Proven Scenario

- Group ID: `75cd4f50-97c9-4aa0-911b-eb3b17ffd804`
- Group run ID: `cebf8d7a-e416-4d2e-9f72-6e284580e5b0`
- Remediation run ID: `3feb85a9-2845-4ee3-b4f2-2530ff0eb0c7`
- Bucket-scoped executable action:
  - `bb487cfd-2d28-41a6-8ec3-5f685e4eaa26`
  - target `arn:aws:s3:::config-bucket-696505809372`
  - resolved `support_tier = deterministic_bundle`
- Account-scoped metadata-only action:
  - `47c023ae-945c-42bf-9b44-018d276046fa`
  - target `AWS::::Account:696505809372`
  - resolved `support_tier = review_required_bundle`

## Bundle Proof

- Contract check artifact:
  - [s3-live-bundle-contract-check.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/api/s3-live-bundle-contract-check.json)
- Generated bundle root:
  - [generated-bundle/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle)

Observed contract:

- Required files present:
  - [bundle_manifest.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/bundle_manifest.json)
  - [decision_log.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/decision_log.md)
  - [finding_coverage.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/finding_coverage.json)
  - [README_GROUP.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/README_GROUP.txt)
  - [run_all.sh](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/run_all.sh)
- Manifest reported:
  - `layout_version = grouped_bundle_mixed_tier/v1`
  - `execution_root = executable/actions`
  - `tier_counts = { executable: 1, review_required: 1, manual_guidance: 0 }`
- Folder layout proved:
  - [executable/actions/01-arn-aws-s3-config-bucket-696505809372-bb487cfd](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/executable/actions/01-arn-aws-s3-config-bucket-696505809372-bb487cfd)
  - [review_required/actions/02-aws-account-696505809372-47c023ae](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T015105Z-rem-profile-wave5-s3-mixed-tier-live-rerun/evidence/generated-bundle/review_required/actions/02-aws-account-696505809372-47c023ae)

## Environment Note

- A fresh direct `AssumeRole` into `arn:aws:iam::696505809372:role/SecurityAutopilotReadRole` now returned `AccessDenied` during this rerun.
- To keep the scope narrow, the isolated runtime restored the exact March 15, 2026 live-ingested S3.9 action/group records from the earlier Wave 5 run instead of widening into target-account IAM repair.
- The grouped bundle proof therefore uses real AWS-backed records and the current `master` API/worker bundle path, but it is not a fresh ingest proof.

## Exit Position

- Wave 5 mixed-tier executable grouped product gap: `closed`
- Wave 5 narrowed live rerun readiness: `yes for product logic`
- Remaining external prerequisite for a fresh ingest-based rerun: restore target-account `SecurityAutopilotReadRole` trust for SaaS-account assumption
