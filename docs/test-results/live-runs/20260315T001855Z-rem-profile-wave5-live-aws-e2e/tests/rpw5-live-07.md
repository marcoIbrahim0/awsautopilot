# Test 07 - zero-executable mixed-tier behavior is explicit and non-500

- Wave: `Wave 5`
- Date (UTC): `2026-03-15T00:36:44Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18004`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `69d0da9c-3244-47ca-b556-37993e25f6ea`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Required prior artifacts: `group_id=40041bfb-2ee9-4afd-9436-cb93a976c6ca`, `run_id=8745650b-c730-416f-8375-7fbbec760aff`

## Steps Executed

1. Created a grouped EBS run with `risk_acknowledged=true`.
2. Fetched the generated run detail and confirmed that both grouped actions resolved to `review_required_bundle` with `runnable_action_count=0`.
3. Extracted the generated manifest and readme files.
4. Called `POST /api/remediation-runs/{run_id}/execute-pr-bundle` on the zero-executable run.
5. Queried the action-group runs listing for the generated group run.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `POST` | `/api/action-groups/40041bfb-2ee9-4afd-9436-cb93a976c6ca/bundle-run` | `strategy_id=snapshot_block_all_sharing`, `risk_acknowledged=true` | `201` | Zero-executable grouped bundle created | `2026-03-15T00:36:39Z` | `../evidence/api/rpw5-live-07-create-request.json`, `../evidence/api/rpw5-live-07-create-response.json` |
| 2 | `GET` | `/api/remediation-runs/8745650b-c730-416f-8375-7fbbec760aff` | none | `200` | Bundle metadata showed `runnable_action_count=0`, `review_required_action_count=2` | `2026-03-15T00:36:44Z` | `../evidence/api/rpw5-live-07-run-detail-1.json` |
| 3 | `artifact extract` | `bundle_manifest.json`, `README_GROUP.txt`, `decision_log.md`, `finding_coverage.json`, `run_all.sh` | extracted from run detail | `N/A` | Raw file copies saved | `2026-03-15T00:42:02Z` | `../evidence/api/rpw5-live-07-bundle_manifest.json`, `../evidence/api/rpw5-live-07-README_GROUP.txt`, `../evidence/api/rpw5-live-07-decision_log.md`, `../evidence/api/rpw5-live-07-finding_coverage.json`, `../evidence/api/rpw5-live-07-run_all.sh` |
| 4 | `POST` | `/api/remediation-runs/8745650b-c730-416f-8375-7fbbec760aff/execute-pr-bundle` | `{}` | `400` | Explicit `reason=no_executable_bundle`; no `500` | `2026-03-15T00:37:28Z` | `../evidence/api/rpw5-live-07-execute-response.json` |
| 5 | `GET` | `/api/action-groups/40041bfb-2ee9-4afd-9436-cb93a976c6ca/runs` | none | `200` | Group run finished cleanly with `reporting_source=system` | `2026-03-15T00:37:34Z` | `../evidence/api/rpw5-live-07-group-runs.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `pass` — generation was explicit, and execution refusal was a precise non-500 contract.
- Negative path: `pass` — metadata-only review-required folders were still present in the generated artifacts.
- Auth boundary: `not exercised in this test`
- Contract shape: `pass` — the route returned `reason=no_executable_bundle` with `layout_version` and `execution_root`.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — the raw bundle files and the execute response were saved.

## Result

- Status: `PASS`
- Severity (if issue found): `n/a`
- Primary tracker mapping: `Wave 5 / RPW5-LIVE-07`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- The generated bundle used the Wave 5 mixed-tier layout even though both grouped actions landed in the `review_required` tier and no executable folders were emitted.
