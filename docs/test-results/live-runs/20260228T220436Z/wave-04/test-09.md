# Test 09

- Wave: 04
- Focus: Tenant isolation across findings/accounts/resources
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity: Tenant A admin (`maromaher54@gmail.com`) + fresh Tenant B user created via signup
- Tenant: Tenant A (`Valens`) and isolated Tenant B (`Wave4 Rerun TenantB ...`)
- AWS account: Tenant A connected account `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens: Tenant A action/run/export IDs captured in API evidence

## Steps Executed

1. Logged in as Tenant A admin and created Tenant B user/tenant.
2. Verified Tenant B cannot read Tenant A findings/accounts/resources by list and direct-ID probes.
3. Probed ingest-progress contract before and after fix (`percent_complete`, `estimated_time_remaining`).

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/findings?limit=20&offset=0` (Tenant B) | `Authorization: Bearer <tenant_b_token>` | `200` | Tenant B isolated view with `total=0` | 2026-02-28T22:16:30Z | `evidence/api/test-09-rerun-postdeploy-findings-tenantB.status`, `.json`, `.headers` |
| 2 | GET | `/api/aws/accounts` (Tenant B) | `Authorization: Bearer <tenant_b_token>` | `200` | Empty array `[]` (no Tenant A account leakage) | 2026-02-28T22:16:30Z | `evidence/api/test-09-rerun-postdeploy-accounts-tenantB.status`, `.json`, `.headers` |
| 3 | GET | `/api/actions/{tenant_a_action_id}` (Tenant B) | `Authorization: Bearer <tenant_b_token>` | `404` | Cross-tenant action read blocked | 2026-02-28T22:16:31Z | `evidence/api/test-09-rerun-postdeploy-action-cross-tenant.status`, `.json`, `.headers` |
| 4 | GET | `/api/remediation-runs/{tenant_a_run_id}` (Tenant B) | `Authorization: Bearer <tenant_b_token>` | `404` | Cross-tenant run read blocked | 2026-02-28T22:16:31Z | `evidence/api/test-09-rerun-postdeploy-run-cross-tenant.status`, `.json`, `.headers` |
| 5 | GET | `/api/exports/{tenant_a_export_id}` (Tenant B) | `Authorization: Bearer <tenant_b_token>` | `404` | Cross-tenant export read blocked | 2026-02-28T22:16:31Z | `evidence/api/test-09-rerun-postdeploy-export-cross-tenant.status`, `.json`, `.headers` |
| 6 | GET | `/api/aws/accounts/{account_id}/ingest-progress?started_after=...` (baseline) | `Authorization: Bearer <admin_token>` | `200` | `percent_complete` and `estimated_time_remaining` were `null` | 2026-02-28T22:07:58Z | `evidence/api/test-09-11-ingest-progress-with-started-after.status`, `.json`, `.headers` |
| 7 | GET | `/api/aws/accounts/{account_id}/ingest-progress?started_after=...` (post-fix) | `Authorization: Bearer <admin_token>` | `200` | Contract now includes `percent_complete=100`, `estimated_time_remaining=0` | 2026-02-28T22:16:31Z | `evidence/api/test-09-rerun-postdeploy-ingest-progress-with-started-after.status`, `.json`, `.headers` |
| 8 | GET | `/api/aws/accounts/{account_id}/ingest-progress` | `Authorization: Bearer <admin_token>` | `422` | Missing `started_after` still correctly rejected | 2026-02-28T22:16:31Z | `evidence/api/test-09-rerun-postdeploy-ingest-progress-missing-started-after.status`, `.json`, `.headers` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| N/A (API-only Wave 4 run) | API contracts verified with raw artifacts | Verified from API evidence set | N/A |

## Assertions

- Positive path: PASS (`ingest-progress` with `started_after` returns `200` with compatibility fields populated).
- Negative path: PASS (`ingest-progress` without `started_after` returns `422`).
- Auth boundary: PASS (Tenant B cannot access Tenant A action/run/export IDs).
- Contract shape: PASS (`percent_complete` and `estimated_time_remaining` now present and coherent with `progress`).
- Idempotency/retry: PASS (cross-tenant probes remained deterministic `404` across rerun).
- Auditability: PASS (full baseline + postdeploy artifacts retained in run folder).

## Tracker Updates

- Primary tracker section/row: Section 2 row #4 and row #5 (`percent_complete`, `estimated_time_remaining`)
- Tracker section hint: Section 2 and Section 3
- Section 8 checkbox impact: `T09` can be marked complete
- Section 9 changelog update needed: Yes (Wave 4 Test 09 rerun fix)

## Notes

- Tenant A totals in rerun: findings `391`; Tenant B findings `0`; Tenant B accounts `0`.
