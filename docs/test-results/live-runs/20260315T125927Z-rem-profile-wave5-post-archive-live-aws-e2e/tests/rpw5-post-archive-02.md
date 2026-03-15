# Test 02 - customer-run bundle semantics

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
  - group run `6de0f03c-58c2-4c5f-8739-dfdd9ee51eff`
  - remediation run `7a7f38cb-10f4-4166-9fa8-03d0e169fcd1`
  - extracted customer-run bundle under `../evidence/api/generated-bundle/`

## Steps Executed

1. Opened `bundle_manifest.json`, `README_GROUP.txt`, `decision_log.md`, and `finding_coverage.json` from the extracted grouped bundle.
2. Verified the generated runner layout:
   - `run_all.sh` is a reporting wrapper
   - `run_actions.sh` is the actual Terraform runner
   - `EXECUTION_ROOT` is hardcoded to `executable/actions`
3. Confirmed the review-required folder contains metadata only and no executable Terraform files.
4. Verified the top-level bundle documentation enumerates both grouped actions and explicitly tells the operator to run the bundle locally.

## API Evidence

| # | Method | Endpoint | HTTP | Observed | Artifact Path |
|---|---|---|---|---|---|
| 1 | `GET` | `/api/remediation-runs/7a7f38cb-10f4-4166-9fa8-03d0e169fcd1` | `200` | Run artifacts contained the full customer-run bundle payload | [../evidence/api/rpw5-post-archive-remediation-run-detail.json](../evidence/api/rpw5-post-archive-remediation-run-detail.json) |
| 2 | `artifact extract` | `bundle_manifest.json` | `N/A` | Manifest declared `execution_root=executable/actions`, `runnable_action_count=1`, and one review-required action | [../evidence/api/generated-bundle/bundle_manifest.json](../evidence/api/generated-bundle/bundle_manifest.json) |
| 3 | `artifact extract` | `run_all.sh` and `run_actions.sh` | `N/A` | Wrapper delegates to the executable root only | [../evidence/api/generated-bundle/run_all.sh](../evidence/api/generated-bundle/run_all.sh), [../evidence/api/generated-bundle/run_actions.sh](../evidence/api/generated-bundle/run_actions.sh) |
| 4 | `artifact extract` | `README_GROUP.txt`, `decision_log.md`, `finding_coverage.json` | `N/A` | All grouped actions were enumerated in human-readable and machine-readable metadata | [../evidence/api/generated-bundle/README_GROUP.txt](../evidence/api/generated-bundle/README_GROUP.txt), [../evidence/api/generated-bundle/decision_log.md](../evidence/api/generated-bundle/decision_log.md), [../evidence/api/generated-bundle/finding_coverage.json](../evidence/api/generated-bundle/finding_coverage.json) |
| 5 | `artifact summary` | bundle contract check | `N/A` | Confirmed wrapper semantics, tier counts, and metadata-only review layout | [../evidence/api/rpw5-post-archive-bundle-contract-check.json](../evidence/api/rpw5-post-archive-bundle-contract-check.json) |

## Assertions

- `run_all.sh` targets only `executable/actions`: `pass`
- Review/manual folders are metadata only: `pass`
- `decision_log.md`, `finding_coverage.json`, and `README_GROUP.txt` enumerate all grouped actions: `pass`
- No public SaaS execution route is required for this path: `pass`

## Result

- Status: `PASS`
- Severity (if issue found): `n/a`
- Primary tracker mapping: `Wave 5 / RPW5-POST-ARCHIVE-02`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- This bundle is self-contained for customer-run execution: the runnable path is local shell plus Terraform, and the non-executable tier is explicitly metadata only.
- Archived public SaaS execution routes were validated separately in `RPW5-POST-ARCHIVE-05`.
