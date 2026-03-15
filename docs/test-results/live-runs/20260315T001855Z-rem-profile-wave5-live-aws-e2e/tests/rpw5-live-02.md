# Test 02 - mixed-tier run_all and manifest semantics

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
- Required prior artifacts: `zero-executable grouped run 8745650b-c730-416f-8375-7fbbec760aff`

## Steps Executed

1. Created a real AWS-backed grouped run for the EBS public-snapshot family with `strategy_id=snapshot_block_all_sharing` and `risk_acknowledged=true`.
2. Fetched the generated run detail and extracted `bundle_manifest.json`, `README_GROUP.txt`, `decision_log.md`, `finding_coverage.json`, and `run_all.sh`.
3. Verified that the grouped layout used the Wave 5 mixed-tier manifest shape and that the wrapper script only targeted `executable/actions`.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `POST` | `/api/action-groups/40041bfb-2ee9-4afd-9436-cb93a976c6ca/bundle-run` | `strategy_id=snapshot_block_all_sharing`, `risk_acknowledged=true` | `201` | Zero-executable grouped bundle created successfully | `2026-03-15T00:36:39Z` | `../evidence/api/rpw5-live-07-create-request.json`, `../evidence/api/rpw5-live-07-create-response.json` |
| 2 | `GET` | `/api/remediation-runs/8745650b-c730-416f-8375-7fbbec760aff` | none | `200` | Returned bundle artifacts with `layout_version=grouped_bundle_mixed_tier/v1` and `execution_root=executable/actions` | `2026-03-15T00:36:44Z` | `../evidence/api/rpw5-live-07-run-detail-1.json` |
| 3 | `artifact extract` | `bundle_manifest.json`, `run_all.sh`, `decision_log.md`, `finding_coverage.json`, `README_GROUP.txt` | extracted from run detail | `N/A` | Raw copies saved for direct inspection | `2026-03-15T00:42:02Z` | `../evidence/api/rpw5-live-07-bundle_manifest.json`, `../evidence/api/rpw5-live-07-run_all.sh`, `../evidence/api/rpw5-live-07-decision_log.md`, `../evidence/api/rpw5-live-07-finding_coverage.json`, `../evidence/api/rpw5-live-07-README_GROUP.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `pass` — the bundle manifest declared `layout_version` and `execution_root`, and the wrapper only targeted `executable/actions`.
- Negative path: `pass` — review-only folders were present under `review_required/actions/...` but were not treated as Terraform roots.
- Auth boundary: `not exercised`
- Contract shape: `pass` — this is the mixed-tier layout contract required by Wave 5.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — raw extracted copies of the key files were saved.

## Result

- Status: `PASS`
- Severity (if issue found): `n/a`
- Primary tracker mapping: `Wave 5 / RPW5-LIVE-02`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- This proof used a zero-executable mixed-tier layout because no live grouped family in the isolated dataset produced an executable plus review/manual split.
