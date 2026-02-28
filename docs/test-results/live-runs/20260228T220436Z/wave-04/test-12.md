# Test 12

- Wave: 04
- Focus: Cross-tenant access and ingestion trigger isolation
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity: Tenant A admin + fresh Tenant B token
- Tenant: Tenant A (`Valens`) and isolated Tenant B (`Wave4 Rerun TenantB ...`)
- AWS account: Tenant A connected account `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens: Tenant A finding/action/account IDs captured from rerun setup

## Steps Executed

1. Attempted direct Tenant A resource reads (`finding`, `action`) using Tenant B token.
2. Attempted Tenant A ingest trigger endpoints using Tenant B token.
3. Verified Tenant B account listing remains isolated and empty.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/findings/{tenant_a_finding_id}` (Tenant B) | `Authorization: Bearer <tenant_b_token>` | `404` | Cross-tenant finding read blocked | 2026-02-28T22:16:39Z | `evidence/api/test-12-rerun-postdeploy-finding-cross-tenant.status`, `.json`, `.headers` |
| 2 | GET | `/api/actions/{tenant_a_action_id}` (Tenant B) | `Authorization: Bearer <tenant_b_token>` | `404` | Cross-tenant action read blocked | 2026-02-28T22:16:39Z | `evidence/api/test-12-rerun-postdeploy-action-cross-tenant.status`, `.json`, `.headers` |
| 3 | GET | `/api/aws/accounts` (Tenant B) | `Authorization: Bearer <tenant_b_token>` | `200` | Isolated account list `[]` | 2026-02-28T22:16:40Z | `evidence/api/test-12-rerun-postdeploy-accounts-tenantB.status`, `.json`, `.headers` |
| 4 | POST | `/api/aws/accounts/{tenant_a_account_id}/ingest` (Tenant B) | `Authorization: Bearer <tenant_b_token>` | `404` | Cross-tenant ingest trigger blocked | 2026-02-28T22:16:40Z | `evidence/api/test-12-rerun-postdeploy-ingest-cross-tenant.status`, `.json`, `.headers` |
| 5 | POST | `/api/aws/accounts/{tenant_a_account_id}/ingest-access-analyzer` (Tenant B) | `Authorization: Bearer <tenant_b_token>` | `404` | Cross-tenant AA ingest blocked | 2026-02-28T22:16:40Z | `evidence/api/test-12-rerun-postdeploy-ingest-aa-cross-tenant.status`, `.json`, `.headers` |
| 6 | POST | `/api/aws/accounts/{tenant_a_account_id}/ingest-inspector` (Tenant B) | `Authorization: Bearer <tenant_b_token>` | `404` | Cross-tenant Inspector ingest blocked | 2026-02-28T22:16:40Z | `evidence/api/test-12-rerun-postdeploy-ingest-inspector-cross-tenant.status`, `.json`, `.headers` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| N/A (API-only Wave 4 run) | Cross-tenant access blocked | Confirmed from API evidence | N/A |

## Assertions

- Positive path: PASS (Tenant B account listing is isolated/empty).
- Negative path: PASS (Tenant B direct reads of Tenant A resource IDs are blocked).
- Auth boundary: PASS (cross-tenant ingest triggers consistently denied with `404`).
- Contract shape: PASS (error responses remain deterministic/not `200`).
- Idempotency/retry: PASS (repeat cross-tenant probes remained blocked).
- Auditability: PASS (all cross-tenant checks mapped to artifacts).

## Tracker Updates

- Primary tracker section/row: Section 3 row #1/#2/#3 (cross-tenant findings/accounts/ingest)
- Tracker section hint: Section 3
- Section 8 checkbox impact: `T12-1` and `T12-3` can be marked complete
- Section 9 changelog update needed: Yes (Wave 4 Test 12 rerun confirmation)

## Notes

- No cross-tenant `200` responses observed in rerun coverage.
