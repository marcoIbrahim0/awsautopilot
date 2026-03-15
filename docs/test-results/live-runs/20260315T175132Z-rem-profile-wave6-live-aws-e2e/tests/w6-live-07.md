# Test 07 - S3.9 destination-safety branching

- Wave: `Wave 6`
- Date (UTC): `2026-03-15T18:07:58Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18012`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `a2805c66-3117-430d-9ab5-699835441dda`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Required prior artifacts: `group_id=a02f5fa8-4b27-4e2d-8c4b-70621ea557a3`, `group_run_id=19c522c0-9256-4124-8b39-42b707bdd812`, `run_id=837fccdc-a51e-4b1f-a8d0-ed7cc6eea3a3`

## Steps Executed

1. Previewed the bucket-scoped `S3.9` review profile after tenant defaults were set to `config-bucket-696505809372`.
2. Attempted grouped create without `risk_acknowledged` and observed the expected explicit `400` gate.
3. Retried grouped create with top-level `strategy_inputs.log_bucket_name` but without duplicating that input inside each action override and observed unexpected `500 Internal Server Error` responses in the API log.
4. Corrected the grouped request by repeating `strategy_inputs.log_bucket_name` inside each per-action override, then re-ran grouped create successfully.
5. Fetched the grouped remediation run detail and action-group run list.
6. Downloaded and inspected `bundle_manifest.json`, `decision_log.md`, `finding_coverage.json`, `README_GROUP.txt`, and `run_all.sh`.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `GET` | `/api/actions/bee5888e-8c14-43f2-87f6-77b9fcd8c4aa/remediation-preview` | `mode=pr_only`, review profile preview | `200` | Preview resolution downgraded the bucket action to destination-safety review | `2026-03-15T18:05:08Z` | `../evidence/api/w6-live-07-s3-9-preview.json` |
| 2 | `POST` | `/api/action-groups/a02f5fa8-4b27-4e2d-8c4b-70621ea557a3/bundle-run` | grouped create without `risk_acknowledged` | `400` | Public route enforced the explicit risk-acknowledgement gate | `2026-03-15T18:07:20Z` | `../evidence/api/w6-live-07-s3-9-group-create-request.json`, `../evidence/worker/api.log` |
| 3 | `POST` | `/api/action-groups/a02f5fa8-4b27-4e2d-8c4b-70621ea557a3/bundle-run` | grouped create with top-level-only `strategy_inputs.log_bucket_name` | `500` | API log captured `ValueError: strategy_inputs.log_bucket_name is required` instead of a fail-closed validation response | `2026-03-15T18:07:20Z` | `../evidence/worker/api.log` |
| 4 | `POST` | `/api/action-groups/a02f5fa8-4b27-4e2d-8c4b-70621ea557a3/bundle-run` | corrected grouped create with per-override `strategy_inputs.log_bucket_name` | `201` | Grouped review-only run created successfully | `2026-03-15T18:07:56Z` | `../evidence/api/w6-live-07-s3-9-group-create-ack-request.json`, `../evidence/api/w6-live-07-s3-9-group-create-ack-response.json` |
| 5 | `GET` | `/api/remediation-runs/837fccdc-a51e-4b1f-a8d0-ed7cc6eea3a3` | none | `200` | Group bundle persisted both actions as `review_required_bundle` with `runnable_action_count=0` | `2026-03-15T18:07:58Z` | `../evidence/api/w6-live-07-s3-9-group-run-detail.json` |
| 6 | `GET` | `/api/action-groups/a02f5fa8-4b27-4e2d-8c4b-70621ea557a3/runs` | none | `200` | Latest group run completed successfully | `2026-03-15T18:07:58Z` | `../evidence/api/w6-live-07-s3-9-group-runs.json` |
| 7 | `artifact extract` | `bundle_manifest.json`, `README_GROUP.txt`, `decision_log.md`, `finding_coverage.json`, `run_all.sh` | extracted from bundle zip | `N/A` | Mixed-tier grouped bundle carried only review-required metadata folders and no executable actions | `2026-03-15T18:08:00Z` | `../evidence/bundles/w6-live-07-s3-9-group/` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `fail` — no destination-safe executable S3.9 branch existed in the live account, so only the downgrade path was proven.
- Negative path: `pass` — the successful grouped run placed both actions into `review_required/actions` with `runnable_action_count=0` and metadata-only action folders.
- Auth boundary: `not exercised in this test`
- Contract shape: `fail` — the first grouped create returned `500` instead of a fail-closed validation error when grouped overrides lacked duplicated `strategy_inputs.log_bucket_name`.
- Idempotency/retry: `pass` — once the request shape was corrected, the grouped run completed successfully and persisted canonical action resolutions.
- Auditability: `pass` — the run detail, group runs list, bundle manifest files, and the API stack trace were saved.

## Result

- Status: `FAIL`
- Severity (if issue found): `🟠 HIGH`
- Primary tracker mapping: `Wave 6 / W6-LIVE-07`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- The grouped bundle itself behaved correctly after the request was normalized: `README_GROUP.txt` and `bundle_manifest.json` showed `review_required_metadata_only` for both actions and no executable folders.
- The public grouped-create route still exposed a real `500` regression on the top-level-only `strategy_inputs` request shape, which blocks Wave 6 completion even before considering the missing executable branch.
- The failing `500` response body was not preserved as a standalone JSON artifact during the run; the saved proof is the API stack trace plus the successful corrected retry.
