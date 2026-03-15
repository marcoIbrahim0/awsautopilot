# Test 05 - archived SaaS execution surfaces are no longer part of the supported Wave 5 path

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T13:10:08Z`
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
  - remediation run `7a7f38cb-10f4-4166-9fa8-03d0e169fcd1`
  - extracted customer-run bundle under `../evidence/api/generated-bundle/`

## Steps Executed

1. Called each archived public SaaS PR-bundle route with valid authenticated requests:
   - `POST /api/remediation-runs/{run_id}/execute-pr-bundle`
   - `POST /api/remediation-runs/{run_id}/approve-apply`
   - `POST /api/remediation-runs/bulk-execute-pr-bundle`
   - `POST /api/remediation-runs/bulk-approve-apply`
2. Verified every route returned the explicit archived `410` response.
3. Cross-checked current docs that describe customer-run PR bundles as the supported model.

## API Evidence

| # | Method | Endpoint | HTTP | Observed | Artifact Path |
|---|---|---|---|---|---|
| 1 | `POST` | `/api/remediation-runs/7a7f38cb-10f4-4166-9fa8-03d0e169fcd1/execute-pr-bundle` | `410` | Archived SaaS execution response returned | [../evidence/api/rpw5-post-archive-05-execute-response.json](../evidence/api/rpw5-post-archive-05-execute-response.json) |
| 2 | `POST` | `/api/remediation-runs/7a7f38cb-10f4-4166-9fa8-03d0e169fcd1/approve-apply` | `410` | Archived SaaS apply response returned | [../evidence/api/rpw5-post-archive-05-approve-response.json](../evidence/api/rpw5-post-archive-05-approve-response.json) |
| 3 | `POST` | `/api/remediation-runs/bulk-execute-pr-bundle` | `410` | Archived bulk SaaS plan response returned | [../evidence/api/rpw5-post-archive-05-bulk-execute-request.json](../evidence/api/rpw5-post-archive-05-bulk-execute-request.json), [../evidence/api/rpw5-post-archive-05-bulk-execute-response.json](../evidence/api/rpw5-post-archive-05-bulk-execute-response.json) |
| 4 | `POST` | `/api/remediation-runs/bulk-approve-apply` | `410` | Archived bulk SaaS apply response returned | [../evidence/api/rpw5-post-archive-05-bulk-approve-request.json](../evidence/api/rpw5-post-archive-05-bulk-approve-request.json), [../evidence/api/rpw5-post-archive-05-bulk-approve-response.json](../evidence/api/rpw5-post-archive-05-bulk-approve-response.json) |

## Docs Evidence

- Customer-run PR bundles are documented as the supported model in:
  - [docs/remediation-profile-resolution/README.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/README.md)
  - [docs/remediation-profile-resolution/wave-5-mixed-tier-grouped-bundles.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/wave-5-mixed-tier-grouped-bundles.md)
- The generated bundle itself is customer-run and self-contained:
  - [../evidence/api/generated-bundle/run_all.sh](../evidence/api/generated-bundle/run_all.sh)
  - [../evidence/api/generated-bundle/run_actions.sh](../evidence/api/generated-bundle/run_actions.sh)
  - [../evidence/api/generated-bundle/README_GROUP.txt](../evidence/api/generated-bundle/README_GROUP.txt)

## Assertions

- Public SaaS execution routes return the archived response: `pass`
- Docs/evidence clearly show customer-run bundles as the supported path: `pass`
- This test is informational and does not replace mixed-tier/customer-run proof: `pass`

## Result

- Status: `PASS`
- Severity (if issue found): `informational`
- Primary tracker mapping: `Wave 5 / RPW5-POST-ARCHIVE-05`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- This test confirms product direction only. The narrowed Wave 5 gate still depends on `RPW5-POST-ARCHIVE-01` through `RPW5-POST-ARCHIVE-04`.
