# Test 02 - customer-run grouped bundle semantics regression

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T13:42:32Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18010`
- Branch tested: `master`
- Commit / HEAD: `7eee3cbb57ee99fa9866d811aa5f1bdf5f428a73`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `fbdc7dfe-4aad-4cf3-b6ba-078aa4d8476a`
- AWS Account: `target=696505809372`, `isolated runtime queues/caller identity=029037611564`
- Region(s): `eu-north-1`
- Required prior artifacts:
  - grouped run `f31c9c99-f24f-4536-8774-abff4a765eab`
  - remediation run `75379cc5-6322-4735-b86f-e6b3719fe4d4`
  - extracted mixed-tier bundle under `../evidence/api/generated-bundle/`

## Steps Executed

1. Reused the fresh grouped bundle generated in Test 01 from the current rerun environment.
2. Inspected `bundle_manifest.json`, `run_all.sh`, `run_actions.sh`, `decision_log.md`, `finding_coverage.json`, and the on-disk tier roots.
3. Verified that the customer-run execution path stays rooted at `executable/actions`, while review-required output remains metadata only.

## Evidence

| # | Artifact | Observed | Artifact Path |
|---|---|---|---|
| 1 | grouped bundle create response | Callback-managed grouped bundle was created successfully | [../evidence/api/rpw5-post-archive-01-02-create-response.json](../evidence/api/rpw5-post-archive-01-02-create-response.json) |
| 2 | remediation run detail | Worker completed bundle generation with `success` | [../evidence/api/rpw5-post-archive-remediation-run-detail.json](../evidence/api/rpw5-post-archive-remediation-run-detail.json) |
| 3 | bundle contract summary | `layout_version=grouped_bundle_mixed_tier/v1`, `execution_root=executable/actions`, one runnable action, one non-executable action | [../evidence/api/rpw5-post-archive-bundle-contract-check.json](../evidence/api/rpw5-post-archive-bundle-contract-check.json) |
| 4 | extracted bundle tree | Bundle contains both executable and review-required roots plus manifest/log/coverage/readme files | [../evidence/api/generated-bundle-tree.txt](../evidence/api/generated-bundle-tree.txt) |
| 5 | executable runner | `run_actions.sh` hardcodes `EXECUTION_ROOT=\"executable/actions\"` | [../evidence/api/generated-bundle/run_actions.sh](../evidence/api/generated-bundle/run_actions.sh) |
| 6 | customer-run wrapper | `run_all.sh` remains the customer-run/reporting wrapper rather than a SaaS execution surface | [../evidence/api/generated-bundle/run_all.sh](../evidence/api/generated-bundle/run_all.sh) |

## Assertions

- Executable output is rooted only under `executable/actions`: `pass`
- Review/manual output is metadata only under `review_required/actions`: `pass`
- `bundle_manifest.json`, `decision_log.md`, `finding_coverage.json`, and `README_GROUP.txt` are all present: `pass`
- Customer-run callback wrapper remains present in the generated bundle: `pass`
- No internal `500` surfaced while generating the mixed-tier bundle: `pass`

## Result

- Status: `PASS`
- Severity (if issue found): `n/a`
- Primary tracker mapping: `Wave 5 / RPW5-POST-ARCHIVE-02`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- The generated bundle continues to expose exactly one runnable executable folder for the bucket-scoped action and one metadata-only review-required folder for the account-scoped action.
- This confirms the archived-SaaS product direction still points operators to download and run the bundle themselves while optionally reporting results back through the grouped callback.
