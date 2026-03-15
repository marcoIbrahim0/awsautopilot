# Test 01 - real mixed-tier executable grouped bundle generation

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T13:04:26Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18008`
- Branch tested: `master`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `3f392e92-069a-47f7-884e-985d5e5ed035`
- AWS Account: `target=696505809372`, `isolated runtime queues/caller identity=029037611564`
- Region(s): `eu-north-1`
- Required prior artifacts:
  - restored live AWS-backed S3.9 group `75cd4f50-97c9-4aa0-911b-eb3b17ffd804`
  - bucket action `bb487cfd-2d28-41a6-8ec3-5f685e4eaa26`
  - account action `47c023ae-945c-42bf-9b44-018d276046fa`

## Steps Executed

1. Recorded isolated AWS caller identity and confirmed a fresh `AssumeRole` into `arn:aws:iam::696505809372:role/SecurityAutopilotReadRole` now fails with `AccessDenied`, so this run reused exact March 15, 2026 live-ingested S3.9 records instead of widening into target-account IAM repair.
2. Restored the exact March 15, 2026 S3.9 group/action records into the isolated local tenant and fetched the group detail.
3. Verified the mixed-tier decision on current `master` through the real remediation-options API:
   - bucket action remained executable
   - account action remained review-required
4. Created a real grouped bundle run through `POST /api/action-groups/{group_id}/bundle-run` with `strategy_id=s3_enable_access_logging_guided`, `strategy_inputs.log_bucket_name=security-autopilot-access-logs-696505809372`, and `risk_acknowledged=true`.
5. Waited for the worker to finish the remediation run, extracted the generated bundle, and recorded the bundle tree plus contract summary.

## API Evidence

| # | Method | Endpoint | HTTP | Observed | Artifact Path |
|---|---|---|---|---|---|
| 1 | `GET` | `sts:GetCallerIdentity` | `200` | Isolated runtime operated under SaaS account `029037611564` | [../evidence/aws/saas-caller-identity.json](../evidence/aws/saas-caller-identity.json) |
| 2 | `STS` | `AssumeRole arn:aws:iam::696505809372:role/SecurityAutopilotReadRole` | `AccessDenied` | Fresh live ingest path is currently blocked by target-account trust | [../evidence/aws/read-role-assume.err](../evidence/aws/read-role-assume.err) |
| 3 | `GET` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804` | `200` | Restored live S3.9 group exposed both expected members | [../evidence/api/rpw5-post-archive-group-detail.json](../evidence/api/rpw5-post-archive-group-detail.json) |
| 4 | `GET` | `/api/actions/bb487cfd-2d28-41a6-8ec3-5f685e4eaa26/remediation-options` | `200` | Bucket-scoped S3.9 action remained executable | [../evidence/api/rpw5-post-archive-bucket-options.json](../evidence/api/rpw5-post-archive-bucket-options.json) |
| 5 | `GET` | `/api/actions/47c023ae-945c-42bf-9b44-018d276046fa/remediation-options` | `200` | Account-scoped S3.9 action remained review-required | [../evidence/api/rpw5-post-archive-account-options.json](../evidence/api/rpw5-post-archive-account-options.json) |
| 6 | `POST` | `/api/action-groups/75cd4f50-97c9-4aa0-911b-eb3b17ffd804/bundle-run` | `201` | Grouped run `6de0f03c-58c2-4c5f-8739-dfdd9ee51eff` created successfully | [../evidence/api/rpw5-post-archive-01-02-create-request.json](../evidence/api/rpw5-post-archive-01-02-create-request.json), [../evidence/api/rpw5-post-archive-01-02-create-response.json](../evidence/api/rpw5-post-archive-01-02-create-response.json) |
| 7 | `GET` | `/api/remediation-runs/7a7f38cb-10f4-4166-9fa8-03d0e169fcd1` | `200` | Worker completed `success` with `Group PR bundle generated (2 actions)` | [../evidence/api/rpw5-post-archive-remediation-run-detail.json](../evidence/api/rpw5-post-archive-remediation-run-detail.json) |

## Bundle Contract Evidence

- Extracted bundle root:
  - [../evidence/api/generated-bundle/](../evidence/api/generated-bundle/)
- Bundle tree:
  - [../evidence/api/generated-bundle-tree.txt](../evidence/api/generated-bundle-tree.txt)
- Bundle contract summary:
  - [../evidence/api/rpw5-post-archive-bundle-contract-check.json](../evidence/api/rpw5-post-archive-bundle-contract-check.json)

Required files present:

- [../evidence/api/generated-bundle/bundle_manifest.json](../evidence/api/generated-bundle/bundle_manifest.json)
- [../evidence/api/generated-bundle/decision_log.md](../evidence/api/generated-bundle/decision_log.md)
- [../evidence/api/generated-bundle/finding_coverage.json](../evidence/api/generated-bundle/finding_coverage.json)
- [../evidence/api/generated-bundle/README_GROUP.txt](../evidence/api/generated-bundle/README_GROUP.txt)
- [../evidence/api/generated-bundle/run_all.sh](../evidence/api/generated-bundle/run_all.sh)
- [../evidence/api/generated-bundle/run_actions.sh](../evidence/api/generated-bundle/run_actions.sh)

Observed tier roots:

- Executable:
  - [../evidence/api/generated-bundle/executable/actions/01-arn-aws-s3-config-bucket-696505809372-bb487cfd](../evidence/api/generated-bundle/executable/actions/01-arn-aws-s3-config-bucket-696505809372-bb487cfd)
- Review-required metadata:
  - [../evidence/api/generated-bundle/review_required/actions/02-aws-account-696505809372-47c023ae](../evidence/api/generated-bundle/review_required/actions/02-aws-account-696505809372-47c023ae)

## Assertions

- Grouped run succeeded to bundle-generation stage: `pass`
- `bundle_manifest.json` exists: `pass`
- Manifest includes at least one `has_runnable_terraform=true`: `pass`
- Manifest includes at least one non-executable action: `pass`
- On-disk layout includes both executable and review-required roots: `pass`

## Result

- Status: `PASS`
- Severity (if issue found): `n/a`
- Primary tracker mapping: `Wave 5 / RPW5-POST-ARCHIVE-01`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- This proof used the exact March 15, 2026 live AWS-backed S3.9 records restored into an isolated `master` runtime because the target ReadRole trust is currently broken for fresh ingest.
- The restored-data caveat is environmental only; the grouped mixed-tier bundle was generated through the current API and worker on `master`.
