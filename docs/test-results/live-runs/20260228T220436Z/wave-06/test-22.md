# Test 22

- Wave: 06
- Focus: Baseline report generation, viewer endpoint, and throttling
- Status: PASS
- Severity (if issue): N/A

## Preconditions

- Runtime: Post-deploy serverless runtime updated with image tag `20260301T020503Z` before executing this rerun.
- Identity: Fresh tenant admin created during this rerun via signup endpoint (artifact `test-22-rerun-postdeploy-20260301T021102Z-00-signup-tenant-admin.*`).
- Tenant: `Wave6 Test22 20260301T021102Z` (`tenant_id=265f39f3-a5cc-4f24-8485-61dce510309d`).
- Region(s): `eu-north-1`.
- Prerequisite IDs/tokens: Baseline report ID created during rerun: `c9c47df8-5688-48ba-bf19-1a498466920e`.

## Steps Executed

1. Created a fresh tenant admin and revalidated auth context via `GET /api/auth/me`.
2. Captured baseline-report pre-state list for the fresh tenant.
3. Created baseline report (`POST /api/baseline-report`) and immediately repeated request twice to validate throttle/rate-limit behavior.
4. Polled report detail from `pending` to `success`, then captured final detail snapshot.
5. Validated auth boundaries on detail and viewer/data endpoints (`401` for no-auth probes).
6. Validated viewer/data endpoint behavior on authenticated path (`GET /api/baseline-report/{id}/data`), then captured post-state list and UI route probe.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 0 | POST | `https://api.valensjewelry.com/api/auth/signup` | Fresh unique email + company_name + password | `201` | Tenant/admin created; access token issued. | 2026-03-01T02:11:04Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-00-signup-tenant-admin.*` |
| 1 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <tenant_admin_token>` | `200` | Tenant-scoped admin identity confirmed. | 2026-03-01T02:11:05Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-01-auth-me-tenant-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/baseline-report?limit=20&offset=0` | `Authorization: Bearer <tenant_admin_token>` | `200` | Pre-state list empty (`items=[]`, `total=0`). | 2026-03-01T02:11:05Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-02-baseline-list-before.*` |
| 3 | POST | `https://api.valensjewelry.com/api/baseline-report` | `{}` + tenant admin token | `201` | Report created with `status=pending`, `id=c9c47df8-5688-48ba-bf19-1a498466920e`. | 2026-03-01T02:11:06Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-03-create-baseline-first.*`, `...-03-report-id.txt` |
| 4 | POST | `https://api.valensjewelry.com/api/baseline-report` | `{}` + tenant admin token (immediate repeat) | `429` | Rate limit enforced; `Retry-After: 86399`. | 2026-03-01T02:11:06Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-04-create-baseline-repeat-1.*` |
| 5 | POST | `https://api.valensjewelry.com/api/baseline-report` | `{}` + tenant admin token (second immediate repeat) | `429` | Rate limit still enforced; `Retry-After: 86399`. | 2026-03-01T02:11:06Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-05-create-baseline-repeat-2.*` |
| 6 | GET | `https://api.valensjewelry.com/api/baseline-report/c9c47df8-5688-48ba-bf19-1a498466920e` | `Authorization: Bearer <tenant_admin_token>` | `200` | Poll snapshot observed `status=pending`, `download_url=null`. | 2026-03-01T02:11:07Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-06-report-detail-poll-01.*` |
| 7 | GET | `https://api.valensjewelry.com/api/baseline-report/c9c47df8-5688-48ba-bf19-1a498466920e` | `Authorization: Bearer <tenant_admin_token>` | `200` | Final snapshot observed `status=success`, non-null `download_url`, `file_size_bytes=1931`. | 2026-03-01T02:11:17Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-90-report-detail-final.*` |
| 8 | GET | `https://api.valensjewelry.com/api/baseline-report/c9c47df8-5688-48ba-bf19-1a498466920e` | No auth header | `401` | Auth boundary enforced (`{"detail":"Not authenticated"}`). | 2026-03-01T02:11:18Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-91-report-detail-no-auth.*` |
| 9 | GET | `https://api.valensjewelry.com/api/baseline-report/c9c47df8-5688-48ba-bf19-1a498466920e/data` | `Authorization: Bearer <tenant_admin_token>` | `200` | Viewer/data payload returned (`summary`, `top_risks`, `recommendations`, `tenant_name`). | 2026-03-01T02:11:18Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-92-report-data-auth.*` |
| 10 | GET | `https://api.valensjewelry.com/api/baseline-report/c9c47df8-5688-48ba-bf19-1a498466920e/data` | No auth header | `401` | Auth boundary enforced (`{"detail":"Not authenticated"}`). | 2026-03-01T02:11:18Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-93-report-data-no-auth.*` |
| 11 | GET | `https://api.valensjewelry.com/api/baseline-report?limit=20&offset=0` | `Authorization: Bearer <tenant_admin_token>` | `200` | Post-state list includes created report (`total=1`, status `success`). | 2026-03-01T02:11:19Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-94-baseline-list-after.*` |
| 12 | N/A | Contract summaries | N/A | N/A | Contract and throttle checks both pass (`create_pass=true`, `throttle_pass=true`, `data_auth_pass=true`, `data_no_auth_pass=true`). | 2026-03-01T02:11:19Z | `evidence/api/test-22-rerun-postdeploy-20260301T021102Z-95-contract-check.json`, `...-96-throttle-check.json`, `...-99-context-summary.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/baseline-report` (no-auth route probe) | Route responds deterministically without crash | `200` HTML shell returned; no route-level crash observed in probe | N/A (`evidence/ui/test-22-rerun-postdeploy-20260301T021102Z-ui-01-baseline-report-no-auth.*`) |

## Assertions

- Positive path: PASS. Report creation returned `201` (`pending`) and detail progressed `pending -> success` with populated `download_url`.
- Viewer endpoint: PASS. `GET /api/baseline-report/{id}/data` returned `200` with structured viewer payload.
- Auth boundary: PASS. No-auth probes returned `401` on both `GET /api/baseline-report/{id}` and `GET /api/baseline-report/{id}/data`.
- Throttling/rate-limit: PASS. Immediate repeated creates returned `429` with `Retry-After: 86399`.
- Contract shape: PASS. Detail/list/data responses matched expected fields for create, progression, and viewer rendering.
- Auditability: PASS. Full request/status/headers/body/timestamp artifacts captured for each API/UI probe.

## Tracker Updates

- Primary tracker section/row: Section 1 row #7 moved to ✅ FIXED; Section 6 row #4 moved to ✅ FIXED.
- Tracker section hint: Section 1, Section 4, Section 6, and Section 9.
- Section 8 checkbox impact: `T22` remains checked.
- Section 9 changelog update: Added post-deploy closure row for Test 22 viewer endpoint and full contract revalidation.

## Notes

- Previous Test 22 PARTIAL outcome is now closed by post-deploy rerun evidence (`test-22-rerun-postdeploy-20260301T021102Z-*`).
- Rerun used a fresh tenant to avoid prior-tenant 24h rate-limit carryover and to produce full create/progression/throttle/viewer evidence in one run.
