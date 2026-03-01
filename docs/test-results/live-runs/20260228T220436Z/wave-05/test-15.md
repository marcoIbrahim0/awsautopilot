# Test 15

- Wave: 05
- Focus: Run progress and findings filter contract behavior
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity: Tenant A admin `maromaher54@gmail.com` (token sourced from prior login artifact and revalidated in this rerun)
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens: Reused `run_id=216b042f-ee97-4dd4-aeaf-51880e2260df` from `evidence/api/test-14-12-first-run-id.txt`; token source `evidence/api/test-13-rerun-postdeploy-00-login-admin.json` recorded in `evidence/api/test-15-rerun-postdeploy-00-token-source.txt`

## Steps Executed

1. Deployed runtime image `20260228T235701Z` to dev SaaS.
2. Loaded admin context (`/api/auth/me`, `/api/aws/accounts`) and confirmed tenant/account/region preconditions.
3. Reused the completed remediation run ID and executed run-progress polling matrix: three polls of `/api/remediation-runs/{id}` and three polls of `/api/remediation-runs/{id}/execution`.
4. Captured run-progress contract summaries, including execution `current_step` and numeric progress fields from each poll.
5. Executed findings baseline call, single-filter matrix (severity/account/status/source), combined-filter call, invalid filter (`severity=NOPE`), pagination duplicate-ID check, and auth-boundary probes.
6. Captured unauthenticated UI route probes for `/findings` and `/remediation-runs/{id}`.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <admin_token>` | `200` | Tenant/user context confirmed (`tenant=Valens`, `role=admin`) | 2026-03-01T00:01:57Z | `evidence/api/test-15-rerun-postdeploy-01-auth-me-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/aws/accounts` | `Authorization: Bearer <admin_token>` | `200` | Connected account/region context confirmed (`029037611564`, `eu-north-1`) | 2026-03-01T00:01:57Z | `evidence/api/test-15-rerun-postdeploy-02-accounts-admin.*` |
| 3 | GET | `https://api.valensjewelry.com/api/remediation-runs/216b042f-ee97-4dd4-aeaf-51880e2260df` | `Authorization: Bearer <admin_token>` | `200` | Run detail returned with stable `status=success` | 2026-03-01T00:01:58Z | `evidence/api/test-15-rerun-postdeploy-04-run-detail-poll-1.*` |
| 4 | GET | `https://api.valensjewelry.com/api/remediation-runs/216b042f-ee97-4dd4-aeaf-51880e2260df/execution` | `Authorization: Bearer <admin_token>` | `200` | Execution payload returned from run fallback with `current_step=completed`, `progress_percent=100` | 2026-03-01T00:01:58Z | `evidence/api/test-15-rerun-postdeploy-05-run-execution-poll-1.*` |
| 5 | GET | `https://api.valensjewelry.com/api/remediation-runs/216b042f-ee97-4dd4-aeaf-51880e2260df` (poll 2) | `Authorization: Bearer <admin_token>` | `200` | Run detail remained `status=success` | 2026-03-01T00:02:01Z | `evidence/api/test-15-rerun-postdeploy-06-run-detail-poll-2.*` |
| 6 | GET | `https://api.valensjewelry.com/api/remediation-runs/216b042f-ee97-4dd4-aeaf-51880e2260df/execution` (poll 2) | `Authorization: Bearer <admin_token>` | `200` | Execution payload remained stable (`source=run_fallback`, `current_step=completed`) | 2026-03-01T00:02:02Z | `evidence/api/test-15-rerun-postdeploy-07-run-execution-poll-2.*` |
| 7 | GET | `https://api.valensjewelry.com/api/remediation-runs/216b042f-ee97-4dd4-aeaf-51880e2260df` (poll 3) | `Authorization: Bearer <admin_token>` | `200` | Run detail remained `status=success` | 2026-03-01T00:02:05Z | `evidence/api/test-15-rerun-postdeploy-08-run-detail-poll-3.*` |
| 8 | GET | `https://api.valensjewelry.com/api/remediation-runs/216b042f-ee97-4dd4-aeaf-51880e2260df/execution` (poll 3) | `Authorization: Bearer <admin_token>` | `200` | Execution payload remained stable (`current_step=completed`, `progress_percent=100`) | 2026-03-01T00:02:06Z | `evidence/api/test-15-rerun-postdeploy-09-run-execution-poll-3.*` |
| 9 | N/A | Run-progress contract checks | N/A | N/A | Detail/execution keys stable across polls; execution status/current_step/progress stable across polls | 2026-03-01T00:02:15Z | `evidence/api/test-15-rerun-postdeploy-21-run-progress-contract-check.json`, `evidence/api/test-15-rerun-postdeploy-26-run-detail-audit-check.json` |
| 10 | GET | `https://api.valensjewelry.com/api/findings?limit=20&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Baseline findings shape confirmed (`items[]`,`total=391`) | 2026-03-01T00:02:06Z | `evidence/api/test-15-rerun-postdeploy-10-findings-baseline.*`, `evidence/api/test-15-rerun-postdeploy-22-filter-input-context.json` |
| 11 | GET | `https://api.valensjewelry.com/api/findings?severity=INFORMATIONAL&limit=20&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Severity filter returned matching items (`mismatch_count=0`) | 2026-03-01T00:02:07Z | `evidence/api/test-15-rerun-postdeploy-11-findings-filter-severity.*`, `evidence/api/test-15-rerun-postdeploy-23-findings-filter-value-check.json` |
| 12 | GET | `https://api.valensjewelry.com/api/findings?account_id=029037611564&limit=20&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Account filter returned matching items (`mismatch_count=0`) | 2026-03-01T00:02:07Z | `evidence/api/test-15-rerun-postdeploy-12-findings-filter-account.*`, `evidence/api/test-15-rerun-postdeploy-23-findings-filter-value-check.json` |
| 13 | GET | `https://api.valensjewelry.com/api/findings?status=RESOLVED&limit=20&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Status filter returned matching items (`mismatch_count=0`) | 2026-03-01T00:02:08Z | `evidence/api/test-15-rerun-postdeploy-13-findings-filter-status.*`, `evidence/api/test-15-rerun-postdeploy-23-findings-filter-value-check.json` |
| 14 | GET | `https://api.valensjewelry.com/api/findings?source=security_hub&limit=20&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Source filter returned matching items (`mismatch_count=0`) | 2026-03-01T00:02:09Z | `evidence/api/test-15-rerun-postdeploy-14-findings-filter-source.*`, `evidence/api/test-15-rerun-postdeploy-23-findings-filter-value-check.json` |
| 15 | GET | `https://api.valensjewelry.com/api/findings?severity=INFORMATIONAL&account_id=029037611564&status=RESOLVED&source=security_hub&limit=20&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Combined filter returned matching items (`mismatch_count=0`) | 2026-03-01T00:02:09Z | `evidence/api/test-15-rerun-postdeploy-15-findings-filter-combined.*`, `evidence/api/test-15-rerun-postdeploy-23-findings-filter-value-check.json` |
| 16 | GET | `https://api.valensjewelry.com/api/findings?severity=NOPE&limit=20&offset=0` | `Authorization: Bearer <admin_token>` | `400` | Validation error contract returned (`Invalid severity`, `invalid_values=["NOPE"]`) | 2026-03-01T00:02:10Z | `evidence/api/test-15-rerun-postdeploy-16-findings-filter-invalid-severity.*` |
| 17 | GET | `https://api.valensjewelry.com/api/findings?limit=20&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Pagination page 1 retrieved | 2026-03-01T00:02:10Z | `evidence/api/test-15-rerun-postdeploy-17-findings-pagination-page-1.*` |
| 18 | GET | `https://api.valensjewelry.com/api/findings?limit=20&offset=20` | `Authorization: Bearer <admin_token>` | `200` | Pagination page 2 retrieved | 2026-03-01T00:02:11Z | `evidence/api/test-15-rerun-postdeploy-18-findings-pagination-page-2.*` |
| 19 | N/A | Pagination duplicate-id check | N/A | N/A | Duplicate IDs across page1/page2 = `0` | 2026-03-01T00:02:15Z | `evidence/api/test-15-rerun-postdeploy-24-pagination-duplicate-check.json` |
| 20 | GET | `https://api.valensjewelry.com/api/findings?limit=5&offset=0` | No auth header | `401` | Unauthenticated findings access blocked | 2026-03-01T00:02:12Z | `evidence/api/test-15-rerun-postdeploy-19-findings-no-auth.*` |
| 21 | GET | `https://api.valensjewelry.com/api/findings?limit=5&offset=0` | `Authorization: Bearer invalid.token.value` | `401` | Invalid token findings access blocked | 2026-03-01T00:02:12Z | `evidence/api/test-15-rerun-postdeploy-20-findings-invalid-token.*` |
| 22 | N/A | Filter contract aggregate checks | N/A | N/A | HTTP/status/total summary consolidated for all filter/auth checks | 2026-03-01T00:02:15Z | `evidence/api/test-15-rerun-postdeploy-25-findings-filter-contract-check.json`, `evidence/api/test-15-rerun-postdeploy-99-context-summary.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/findings` (no auth session) | Route should render deterministically without crash | `200` HTML shell returned; no UI-visible defect observed in route probe | N/A (no UI defect requiring screenshot) |
| `GET https://dev.valensjewelry.com/remediation-runs/216b042f-ee97-4dd4-aeaf-51880e2260df` (no auth session) | Route should render deterministically without crash | `200` HTML shell returned; no UI-visible defect observed in route probe | N/A (no UI defect requiring screenshot) |

## Assertions

- Positive path: PASS for findings filter contract (`severity`, `account`, `status`, `source`, combined) and pagination shape (`items[]`,`total`) with matching-item checks (`mismatch_count=0`).
- Negative path: PASS for invalid findings filter input (`severity=NOPE` -> `400` with validation payload).
- Auth boundary: PASS for findings endpoints (`401` with no auth and invalid token).
- Contract shape: PASS. Run detail endpoint remained stable across retries (`200` + stable keys/status), and `/api/remediation-runs/{id}/execution` returned `200` on all three polls with stable pollable fields (`current_step`, `progress_percent`, `completed_steps`, `total_steps`).
- Idempotency/retry: PASS for repeated run-detail and run-execution polling (stable key sets and stable terminal status/current step across 3 polls) and repeated list/pagination checks (page1/page2 duplicate IDs = `0`).
- Auditability: PASS for run detail payload (includes `approved_by_user_id`, timestamps, `logs`, `outcome`, nested action metadata).

## Tracker Updates

- Primary tracker section/row: Section 2 row #10 and Section 6 row #5 (`/api/remediation-runs/{id}/execution` contract for Test 15)
- Tracker section hint: Sections 2 and 6
- Section 8 checkbox impact: Marked `T15` medium checklist item complete
- Section 9 changelog update needed: Yes (Wave 5 Test 15 post-deploy rerun closure)

## Notes

- Baseline live execution at `2026-02-28T23:17:35Z` showed `/execution` returning `404`.
- Post-deploy rerun at `2026-03-01T00:02:06Z` now returns `200` with stable progress contract fields, closing the Test 15 gap.
- Recheck rerun at `2026-03-01T00:12:42Z` (`evidence/api/test-15-rerun-recheck-20260301T001237Z-*`) reconfirmed PASS behavior: `/execution` remained `200` across three polls with stable progress fields, filter matrix remained `200/400/401`, and pagination duplicate count remained `0`.
