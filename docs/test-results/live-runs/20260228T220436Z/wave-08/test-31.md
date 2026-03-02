# Test 31

- Wave: 08
- Focus: Non-admin invite/delete authorization boundaries
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity:
  - Tenant A admin: `maromaher54@gmail.com`
  - Same-tenant member: `wave3acc+20260228T213251Z@example.com`
  - Wrong-tenant admin (created during run): `wave8.test31.wrongtenant.20260302T191352Z@example.com`
- Tenant A: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Canonical evidence prefix: `test-31-live-20260302T191352Z-*`
- Prerequisite IDs/tokens:
  - Admin login token captured from `01-login-admin`
  - Member login token captured from `03-login-member`
  - Wrong-tenant token captured from `16-signup-wrong-tenant-admin-with-company`

## Steps Executed

1. Logged in as tenant admin and same-tenant member; confirmed identities via `/api/auth/me` and captured `/api/aws/accounts` pre-state (`account_id=029037611564`).
2. With member token, executed:
   - `POST /api/users/invite` (expected `403`)
   - `DELETE /api/aws/accounts/{account_id}?cleanup_resources=false` (expected `403`)
3. With admin token, verified control path behavior:
   - `POST /api/users/invite` returned `201` (invite issued)
   - `DELETE /api/aws/accounts/000000000000?cleanup_resources=false` returned `404` (admin passed auth gate; non-existent account correctly rejected)
4. Executed no-token probes:
   - `POST /api/users/invite` -> `401`
   - `DELETE /api/aws/accounts/{account_id}?cleanup_resources=false` -> `401`
5. Executed wrong-tenant probes:
   - Initial signup attempt without `company_name` returned `422` (token not issued; follow-up delete observed `401`)
   - Corrected signup with `company_name` returned `201`, `/api/auth/me` returned `200`, then wrong-tenant delete probe returned `404`
6. Captured `/api/aws/accounts` post-state and confirmed target account remained present (no destructive mutation occurred). No restore action was required.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Admin token issued (`role=admin`, tenant `Valens`). | 2026-03-02T19:13:53Z | `evidence/api/test-31-live-20260302T191352Z-01-login-admin.*` |
| 2 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"wave3acc+20260228T213251Z@example.com","password":"***REDACTED***"}` | `200` | Member token issued (`role=member`, same tenant). | 2026-03-02T19:13:55Z | `evidence/api/test-31-live-20260302T191352Z-03-login-member.*` |
| 3 | GET | `https://api.valensjewelry.com/api/aws/accounts` (pre) | Bearer admin token | `200` | Target account row present (`029037611564`, `status=validated`). | 2026-03-02T19:13:55Z | `evidence/api/test-31-live-20260302T191352Z-05-accounts-pre.*` |
| 4 | POST | `https://api.valensjewelry.com/api/users/invite` | Member token + `{"email":"wave8.test31.member-probe.20260302T191352Z@example.com"}` | `403` | Member invite denied: `Only admins can invite users`. | 2026-03-02T19:13:57Z | `evidence/api/test-31-live-20260302T191352Z-08-invite-member-forbidden.*` |
| 5 | DELETE | `https://api.valensjewelry.com/api/aws/accounts/029037611564?cleanup_resources=false` | Member token | `403` | Member delete denied: `Only admins can delete AWS accounts`. | 2026-03-02T19:13:57Z | `evidence/api/test-31-live-20260302T191352Z-09-delete-account-member-forbidden.*` |
| 6 | POST | `https://api.valensjewelry.com/api/users/invite` | Admin token + `{"email":"wave8.test31.admin-control.20260302T191352Z@example.com"}` | `201` | Admin invite control path works (`Invitation sent ...`). | 2026-03-02T19:13:58Z | `evidence/api/test-31-live-20260302T191352Z-10-invite-admin-control.*` |
| 7 | DELETE | `https://api.valensjewelry.com/api/aws/accounts/000000000000?cleanup_resources=false` | Admin token | `404` | Admin auth gate passed; non-existent account rejected by resource lookup. | 2026-03-02T19:13:58Z | `evidence/api/test-31-live-20260302T191352Z-11-delete-account-admin-invalid-account.*` |
| 8 | POST | `https://api.valensjewelry.com/api/users/invite` | No token + same body as #4 | `401` | Unauthenticated invite request denied (`Not authenticated`). | 2026-03-02T19:13:59Z | `evidence/api/test-31-live-20260302T191352Z-12-invite-no-auth.*` |
| 9 | DELETE | `https://api.valensjewelry.com/api/aws/accounts/029037611564?cleanup_resources=false` | No token | `401` | Unauthenticated delete request denied (`Authentication required`). | 2026-03-02T19:14:00Z | `evidence/api/test-31-live-20260302T191352Z-13-delete-account-no-auth.*` |
| 10 | POST | `https://api.valensjewelry.com/api/auth/signup` | `{"email":"wave8.test31.20260302T191352Z@example.com",...}` (missing `company_name`) | `422` | Signup contract requires `company_name`; initial wrong-tenant token mint failed. | 2026-03-02T19:13:56Z | `evidence/api/test-31-live-20260302T191352Z-06-signup-wrong-tenant-admin.*` |
| 11 | POST + GET | `/api/auth/signup` + `/api/auth/me` | Corrected signup body with `company_name` | `201 / 200` | Wrong-tenant admin token successfully minted and validated. | 2026-03-02T19:14:54Z | `evidence/api/test-31-live-20260302T191352Z-16-signup-wrong-tenant-admin-with-company.*`, `...-17-auth-me-wrong-tenant.*` |
| 12 | DELETE | `https://api.valensjewelry.com/api/aws/accounts/029037611564?cleanup_resources=false` | Wrong-tenant admin token | `404` | Cross-tenant delete blocked (`AWS account ... not found for tenant`). | 2026-03-02T19:14:55Z | `evidence/api/test-31-live-20260302T191352Z-18-delete-account-wrong-tenant.*` |
| 13 | GET | `https://api.valensjewelry.com/api/aws/accounts` (post) | Bearer admin token | `200` | Target account still present; no destructive side effects observed. | 2026-03-02T19:14:01Z | `evidence/api/test-31-live-20260302T191352Z-15-accounts-post.*` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| API-only authorization boundary test | N/A | No UI-specific assertion required for this test case. | N/A |

## Assertions

- Positive path: PASS. Admin invite endpoint returned `201` with expected response shape.
- Negative path: PASS. Member invite/delete probes returned `403` with explicit admin-only messages.
- Auth boundary: PASS. No-token probes returned `401`; wrong-tenant delete probe returned `404`.
- Contract shape: PASS. Response body fields/messages were stable and consistent with prior RBAC hotfix intent.
- Idempotency/retry: Not exercised in this scope (single-attempt boundary regression probes).
- Auditability: PASS. Full per-call artifacts (`request`, `status`, `headers`, `json`, `timestamp`) captured under canonical prefix; summary at `...-99-context-summary.json`.

## Tracker Updates

- Primary tracker section/row:
  - Section 3 row #7 (`Non-admin can invite users`)
  - Section 3 row #8 (`Non-admin can delete accounts`)
- Tracker section hint: Section 3
- Section 8 checkbox impact:
  - `T31-7` marked complete
  - `T31-8` marked complete
- Section 9 changelog update: Added Wave 8 Test 31 PASS revalidation entry (`2026-03-02`).

## Notes

- No destructive call unexpectedly succeeded in this run (`restore_triggered=false`).
- Wrong-tenant probe required a corrected signup payload including `company_name`; initial `422` evidence is preserved and the final wrong-tenant delete assertion is based on the corrected-token path (`404`).
