# Test 17

- Wave: 06
- Focus: Grouped PR bundle creation endpoints and execution flow
- Status: PASS
- Severity (if issue): N/A

## Preconditions

- Identity: Tenant A admin token reused from `evidence/api/test-13-rerun-postdeploy-00-login-admin.json` and revalidated via `GET /api/auth/me`.
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`).
- AWS account: `029037611564`.
- Region(s): `eu-north-1`.
- Prerequisite IDs/tokens: Group payload selected from live actions inventory and posted to grouped endpoint. Created run ID (post-deploy rerun): `0b91ccbd-1c39-4cb3-8791-4e3a363c0fcb`.

## Steps Executed

1. Revalidated admin auth context and fetched actions inventory.
2. Built grouped-create payload from live selection (`action_type/account_id/status/region`).
3. Executed grouped create, immediate duplicate retry, invalid-filter probe, and no-auth probe.
4. Polled run detail/execution to terminal success and captured contract summary.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <admin_token>` | `200` | Admin tenant context confirmed. | 2026-03-01T01:01:14Z | `evidence/api/test-17-rerun-postdeploy-20260301T010114Z-01-auth-me-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/actions?limit=200&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Actions inventory returned; grouped selection artifacts generated. | 2026-03-01T01:01:14Z | `evidence/api/test-17-rerun-postdeploy-20260301T010114Z-02-actions-list.*`, `...-03-group-selection.json`, `...-03-selected-group.json` |
| 3 | POST | `https://api.valensjewelry.com/api/remediation-runs/group-pr-bundle` | `{"action_type":"s3_bucket_encryption_kms","account_id":"029037611564","status":"open","region":"eu-north-1"}` + admin token | `201` | Group run created (`id=0b91ccbd-1c39-4cb3-8791-4e3a363c0fcb`, `status=pending`). | 2026-03-01T01:01:15Z | `evidence/api/test-17-rerun-postdeploy-20260301T010114Z-04-group-pr-bundle-create-first.*`, `...-04-run-id.txt` |
| 4 | POST | `https://api.valensjewelry.com/api/remediation-runs/group-pr-bundle` (immediate retry) | Same as #3 | `409` | Duplicate pending-run guard enforced. | 2026-03-01T01:01:15Z | `evidence/api/test-17-rerun-postdeploy-20260301T010114Z-05-group-pr-bundle-create-retry-immediate.*` |
| 5 | POST | `https://api.valensjewelry.com/api/remediation-runs/group-pr-bundle` | Missing `region` and `region_is_null` | `400` | Region filter validation enforced. | 2026-03-01T01:01:15Z | `evidence/api/test-17-rerun-postdeploy-20260301T010114Z-06-group-pr-bundle-invalid-region-filter.*` |
| 6 | POST | `https://api.valensjewelry.com/api/remediation-runs/group-pr-bundle` | Same payload as #3, no auth | `401` | Unauthenticated request blocked. | 2026-03-01T01:01:15Z | `evidence/api/test-17-rerun-postdeploy-20260301T010114Z-07-group-pr-bundle-no-auth.*` |
| 7 | GET | `https://api.valensjewelry.com/api/remediation-runs/0b91ccbd-1c39-4cb3-8791-4e3a363c0fcb` (final poll) | `Authorization: Bearer <admin_token>` | `200` | Terminal run success with `outcome="Group PR bundle generated (25 actions; 1 skipped)"`; `group_bundle` + `pr_bundle` present. | 2026-03-01T01:03:31Z | `evidence/api/test-17-rerun-postdeploy-20260301T010114Z-14-run-detail-poll-final.*` |
| 8 | GET | `https://api.valensjewelry.com/api/remediation-runs/0b91ccbd-1c39-4cb3-8791-4e3a363c0fcb/execution` (final poll) | `Authorization: Bearer <admin_token>` | `200` | Execution/progress terminal success (`progress_percent=100`). | 2026-03-01T01:03:31Z | `evidence/api/test-17-rerun-postdeploy-20260301T010114Z-15-run-execution-poll-final.*` |
| 9 | N/A | Contract summary | N/A | N/A | `contract_ok=true`; generated actions `25`, skipped actions `1`. | 2026-03-01T01:03:31Z | `evidence/api/test-17-rerun-postdeploy-20260301T010114Z-13-contract-check.json`, `...-99-context-summary.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/pr-bundles/create/summary` (no auth session) | Deterministic route behavior without crash | Previously verified `200` HTML shell in same run set; no UI defect observed | N/A |

## Assertions

- Positive path: PASS. Grouped create endpoint returned `201`, produced run ID, and run reached `success` with bundle artifacts.
- Negative path: PASS. Invalid region filter returned `400` as expected.
- Auth boundary: PASS. No-auth grouped create returned `401`.
- Contract shape: PASS. Duplicate pending guard returned `409`; execution endpoint remained pollable and stable.
- Auditability: PASS. Full request/status/body/timestamp artifacts captured, including contract summary.

## Tracker Updates

- Primary tracker section/row: Section 1 row #11 and Section 4 row #7.
- Tracker section hint: Section 1 and Section 4.
- Section 8 checkbox impact: `T17-7` remains complete.
- Section 9 changelog update needed: No new status change (already fixed), but rerun evidence can be referenced.

## Notes

- Post-deploy rerun evidence prefix: `test-17-rerun-postdeploy-20260301T010114Z-*`.
- No product code changes were made during this live validation run.
