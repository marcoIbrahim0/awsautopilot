# Test 05 - archived SaaS execution surface regression

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T13:43:16Z`
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
  - remediation run `75379cc5-6322-4735-b86f-e6b3719fe4d4`
  - fresh mixed-tier customer-run bundle from Tests 01-03

## Steps Executed

1. Reused the fresh remediation run produced by the customer-run grouped bundle flow in this rerun package.
2. Posted all four archived public SaaS PR-bundle execution requests against the current runtime.
3. Confirmed that each route still returns the explicit archived response instead of re-enabling SaaS-managed execution.

## API Evidence

| # | Method | Endpoint | HTTP | Observed | Artifact Path |
|---|---|---|---|---|---|
| 1 | `POST` | `/api/remediation-runs/75379cc5-6322-4735-b86f-e6b3719fe4d4/execute-pr-bundle` | `410` | Archived response returned | [../evidence/api/rpw5-post-archive-05-execute-response.json](../evidence/api/rpw5-post-archive-05-execute-response.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 2 | `POST` | `/api/remediation-runs/75379cc5-6322-4735-b86f-e6b3719fe4d4/approve-apply` | `410` | Archived response returned | [../evidence/api/rpw5-post-archive-05-approve-response.json](../evidence/api/rpw5-post-archive-05-approve-response.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 3 | `POST` | `/api/remediation-runs/bulk-execute-pr-bundle` | `410` | Archived response returned | [../evidence/api/rpw5-post-archive-05-bulk-execute-request.json](../evidence/api/rpw5-post-archive-05-bulk-execute-request.json), [../evidence/api/rpw5-post-archive-05-bulk-execute-response.json](../evidence/api/rpw5-post-archive-05-bulk-execute-response.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 4 | `POST` | `/api/remediation-runs/bulk-approve-apply` | `410` | Archived response returned | [../evidence/api/rpw5-post-archive-05-bulk-approve-request.json](../evidence/api/rpw5-post-archive-05-bulk-approve-request.json), [../evidence/api/rpw5-post-archive-05-bulk-approve-response.json](../evidence/api/rpw5-post-archive-05-bulk-approve-response.json), [../evidence/worker/rpw5-post-archive-api-snippet.log](../evidence/worker/rpw5-post-archive-api-snippet.log) |
| 5 | `artifact` | fresh generated bundle | Customer-run bundle remains the supported path | [../evidence/api/rpw5-post-archive-bundle-contract-check.json](../evidence/api/rpw5-post-archive-bundle-contract-check.json), [../evidence/api/generated-bundle/run_all.sh](../evidence/api/generated-bundle/run_all.sh) |

## Assertions

- Archived SaaS execution routes still return the explicit archived response: `pass`
- Customer-run grouped bundle generation/reporting remains the supported product direction: `pass`
- No SaaS-managed PR-bundle execution surface was reintroduced by the lifecycle fix: `pass`

## Result

- Status: `PASS`
- Severity (if issue found): `n/a`
- Primary tracker mapping: `Wave 5 / RPW5-POST-ARCHIVE-05`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- The lifecycle fix for callback-managed `download_bundle` runs did not widen the product surface back into SaaS-managed execution.
- The current supported product direction remains: generate the grouped bundle, run it with customer-owned credentials or pipelines, and optionally report grouped results back through `/api/internal/group-runs/report`.
