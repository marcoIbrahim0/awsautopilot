# Test 07

- Wave: 03
- Focus: AWS account registration validation, auth boundary, and duplicate handling
- Status: PASS
- Severity (if issue): ⚪ SKIP/NA

## Preconditions

- Identity: Existing admin test user `maromaher54@gmail.com`
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account: `029037611564` (already connected)
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens: Admin bearer token from `POST /api/auth/login`; known connected account and role ARNs from `GET /api/aws/accounts`

## Steps Executed

1. Confirmed authenticated account-list baseline for the connected account.
2. Ran schema/validation negatives on registration payload (empty body, invalid account id, malformed role ARN).
3. Executed auth-boundary probes on account registration (no auth with known tenant id, no auth with random tenant id, invalid bearer token).
4. Executed authenticated duplicate registration probe for the already connected account.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | GET | `https://api.valensjewelry.com/api/aws/accounts` | `Authorization: Bearer <admin_token>` | `200` | Connected account list returned account `029037611564` with role ARNs and region | 2026-02-28T21:44:59Z | `evidence/api/test-07-rerun-20260228T214336Z-accounts-list-auth.status`, `evidence/api/test-07-rerun-20260228T214336Z-accounts-list-auth.json`, `evidence/api/test-07-rerun-20260228T214336Z-accounts-list-auth.request.txt` |
| 2 | POST | `https://api.valensjewelry.com/api/aws/accounts` | `{}` with auth | `422` | Required fields validation triggered for `account_id`, `role_read_arn`, and `tenant_id` | 2026-02-28T21:44:59Z | `evidence/api/test-07-rerun-20260228T214336Z-register-empty-body-auth.status`, `evidence/api/test-07-rerun-20260228T214336Z-register-empty-body-auth.json`, `evidence/api/test-07-rerun-20260228T214336Z-register-empty-body-auth.request.txt` |
| 3 | POST | `https://api.valensjewelry.com/api/aws/accounts` | Invalid account id (`"account_id":"abc"`) with auth | `422` | Account id format validation rejected non-12-digit value | 2026-02-28T21:45:00Z | `evidence/api/test-07-rerun-20260228T214336Z-register-invalid-account-auth.status`, `evidence/api/test-07-rerun-20260228T214336Z-register-invalid-account-auth.json`, `evidence/api/test-07-rerun-20260228T214336Z-register-invalid-account-auth.request.txt` |
| 4 | POST | `https://api.valensjewelry.com/api/aws/accounts` | Malformed `role_read_arn` (`"bad-arn"`) with auth | `422` | IAM role ARN validation rejected malformed ARN | 2026-02-28T21:45:00Z | `evidence/api/test-07-rerun-20260228T214336Z-register-bad-arn-auth.status`, `evidence/api/test-07-rerun-20260228T214336Z-register-bad-arn-auth.json`, `evidence/api/test-07-rerun-20260228T214336Z-register-bad-arn-auth.request.txt` |
| 5 | POST | `https://api.valensjewelry.com/api/aws/accounts` | Known tenant id payload, no auth header | `401` | Unauthenticated registration rejected (`Authentication required`) | 2026-02-28T21:45:00Z | `evidence/api/test-07-rerun-20260228T214336Z-register-no-auth-known-tenant.status`, `evidence/api/test-07-rerun-20260228T214336Z-register-no-auth-known-tenant.json`, `evidence/api/test-07-rerun-20260228T214336Z-register-no-auth-known-tenant.request.txt` |
| 6 | POST | `https://api.valensjewelry.com/api/aws/accounts` | Random tenant id payload, no auth header | `401` | Unauthenticated random-tenant probe also rejected (`Authentication required`) | 2026-02-28T21:45:01Z | `evidence/api/test-07-rerun-20260228T214336Z-register-no-auth-random-tenant.status`, `evidence/api/test-07-rerun-20260228T214336Z-register-no-auth-random-tenant.json`, `evidence/api/test-07-rerun-20260228T214336Z-register-no-auth-random-tenant.request.txt` |
| 7 | POST | `https://api.valensjewelry.com/api/aws/accounts` | Valid payload with invalid bearer token | `401` | Invalid token rejected (`Authentication required`) | 2026-02-28T21:45:01Z | `evidence/api/test-07-rerun-20260228T214336Z-register-invalid-token.status`, `evidence/api/test-07-rerun-20260228T214336Z-register-invalid-token.json`, `evidence/api/test-07-rerun-20260228T214336Z-register-invalid-token.request.txt` |
| 8 | POST | `https://api.valensjewelry.com/api/aws/accounts` | Duplicate connected account payload with auth | `409` | Deterministic conflict returned: `detail.error=Account already connected` | 2026-02-28T21:45:01Z | `evidence/api/test-07-rerun-20260228T214336Z-register-duplicate-auth.status`, `evidence/api/test-07-rerun-20260228T214336Z-register-duplicate-auth.json`, `evidence/api/test-07-rerun-20260228T214336Z-register-duplicate-auth.request.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| Account registration contract check | Registration should enforce auth and reject duplicate re-registration deterministically | No-auth probes rejected (`401`), duplicate authenticated registration returned `409` conflict | N/A (`evidence/ui/test-07-rerun-20260228T214336Z-ui-notes.txt`) |

## Assertions

- Positive path: PASS (authenticated account-list baseline available for connected account)
- Negative path: PASS (payload validation errors returned `422` for empty body, bad account id, and bad ARN)
- Auth boundary: PASS (known-tenant, random-tenant, and invalid-token registration attempts all rejected with `401`)
- Contract shape: PASS (duplicate response includes explicit conflict payload in `detail.error`/`detail.detail`)
- Idempotency/retry: PASS (duplicate mutation attempt returned deterministic conflict `409`, preventing unintended re-create behavior)
- Auditability: PASS (all request/status/body artifacts captured for positive/negative/auth checks)

## Tracker Updates

- Primary tracker section/row: Section 3 row #14 and Section 4 row #15
- Tracker section hint: Section 3 and Section 4
- Section 8 checkbox impact: `T07-14` remains satisfied from this rerun evidence
- Section 9 changelog update needed: No additional entry (fix retest already logged in changelog)

## Notes

- This rerun confirms no tenant-enumeration signal from no-auth registration probes because both known and random tenant ids returned the same `401` result.
