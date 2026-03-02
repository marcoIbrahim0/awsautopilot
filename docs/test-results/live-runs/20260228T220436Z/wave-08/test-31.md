# Test 31

- Wave: 08
- Focus: Non-admin invite/delete authorization boundaries
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity:
  - Tenant A admin: `maromaher54@gmail.com`
  - Same-tenant member: `wave3acc+20260228T213251Z@example.com`
  - Wrong-tenant admin (created during run): `wave8.test31.wrongtenant.20260302T213603Z@example.com`
- Tenant A: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Canonical evidence prefix: `test-31-live-20260302T213603Z-*`
- Prerequisite IDs/tokens:
  - Admin token captured from `01-login-admin`
  - Member token captured from `03-login-member`
  - Wrong-tenant token captured from `12-signup-wrong-tenant-admin`

## Steps Executed

1. Logged in as tenant admin and same-tenant member; confirmed identities and captured `/api/aws/accounts` pre-state.
2. With member token, executed:
   - `POST /api/users/invite` (expected `403`)
   - `DELETE /api/aws/accounts/{account_id}?cleanup_resources=false` (expected `403`)
3. With admin token, verified control-path behavior:
   - `POST /api/users/invite` returned `201` (invite issued)
   - `DELETE /api/aws/accounts/000000000000?cleanup_resources=false` returned `404` (auth passed; resource not found)
4. Executed no-token probes:
   - `POST /api/users/invite` -> `401`
   - `DELETE /api/aws/accounts/{account_id}?cleanup_resources=false` -> `401`
5. Created a wrong-tenant admin identity and validated:
   - wrong-tenant `GET /api/auth/me` -> `200`
   - wrong-tenant delete probe -> `404`
6. Captured `/api/aws/accounts` post-state and confirmed target account remained present.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Admin token issued (`role=admin`, tenant `Valens`). | 2026-03-02T21:36:03Z | `evidence/api/test-31-live-20260302T213603Z-01-login-admin.*` |
| 2 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"wave3acc+20260228T213251Z@example.com","password":"***REDACTED***"}` | `200` | Member token issued (`role=member`, same tenant). | 2026-03-02T21:36:05Z | `evidence/api/test-31-live-20260302T213603Z-03-login-member.*` |
| 3 | GET | `https://api.valensjewelry.com/api/aws/accounts` (pre) | Bearer admin token | `200` | Target account row present (`029037611564`, `status=validated`). | 2026-03-02T21:36:06Z | `evidence/api/test-31-live-20260302T213603Z-05-accounts-pre.*` |
| 4 | POST | `https://api.valensjewelry.com/api/users/invite` | Member token + member-probe email | `403` | Member invite denied: `Only admins can invite users`. | 2026-03-02T21:36:07Z | `evidence/api/test-31-live-20260302T213603Z-06-invite-member-forbidden.*` |
| 5 | DELETE | `https://api.valensjewelry.com/api/aws/accounts/029037611564?cleanup_resources=false` | Member token | `403` | Member delete denied: `Only admins can delete AWS accounts`. | 2026-03-02T21:36:07Z | `evidence/api/test-31-live-20260302T213603Z-07-delete-account-member-forbidden.*` |
| 6 | POST | `https://api.valensjewelry.com/api/users/invite` | Admin token + admin-control invite email | `201` | Admin invite control path works. | 2026-03-02T21:36:07Z | `evidence/api/test-31-live-20260302T213603Z-08-invite-admin-control.*` |
| 7 | DELETE | `https://api.valensjewelry.com/api/aws/accounts/000000000000?cleanup_resources=false` | Admin token | `404` | Admin auth gate passed; non-existent account rejected by lookup. | 2026-03-02T21:36:08Z | `evidence/api/test-31-live-20260302T213603Z-09-delete-account-admin-invalid-account.*` |
| 8 | POST | `https://api.valensjewelry.com/api/users/invite` | No token + same invite body | `401` | Unauthenticated invite request denied (`Not authenticated`). | 2026-03-02T21:36:08Z | `evidence/api/test-31-live-20260302T213603Z-10-invite-no-auth.*` |
| 9 | DELETE | `https://api.valensjewelry.com/api/aws/accounts/029037611564?cleanup_resources=false` | No token | `401` | Unauthenticated delete request denied. | 2026-03-02T21:36:08Z | `evidence/api/test-31-live-20260302T213603Z-11-delete-account-no-auth.*` |
| 10 | POST + GET + DELETE | `/api/auth/signup` + `/api/auth/me` + `/api/aws/accounts/{id}?cleanup_resources=false` | Wrong-tenant signup/auth/delete chain | `201 / 200 / 404` | Wrong-tenant identity created successfully; cross-tenant delete blocked (`404`). | 2026-03-02T21:36:09Z to 2026-03-02T21:36:10Z | `evidence/api/test-31-live-20260302T213603Z-12-signup-wrong-tenant-admin.*`, `...-13-auth-me-wrong-tenant.*`, `...-14-delete-account-wrong-tenant.*` |
| 11 | GET | `https://api.valensjewelry.com/api/aws/accounts` (post) | Bearer admin token | `200` | Target account still present; no destructive side effects observed. | 2026-03-02T21:36:10Z | `evidence/api/test-31-live-20260302T213603Z-15-accounts-post.*` |
| 12 | Summary | Context digest | N/A | N/A | Consolidated run metadata and key status codes. | 2026-03-02 | `evidence/api/test-31-live-20260302T213603Z-99-context-summary.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| API-only authorization boundary test | N/A | No UI-specific assertion required for this test scope. | N/A |

## Assertions

- Positive path: PASS. Admin invite endpoint returned `201`.
- Negative path: PASS. Member invite/delete probes both returned `403` with explicit admin-only messaging.
- Auth boundary: PASS. No-token probes returned `401`; wrong-tenant delete probe returned `404`.
- Contract shape: PASS. Response fields/messages are stable and consistent with RBAC requirements.
- Auditability: PASS. Full per-call artifacts captured under canonical prefix.

## Tracker Updates

- Primary tracker section/row:
  - Section 3 row #7 (`Non-admin can invite users`) -> ✅ FIXED (revalidated)
  - Section 3 row #8 (`Non-admin can delete accounts`) -> ✅ FIXED (revalidated)
- Section 8 checkbox impact:
  - `T31-7` remains checked
  - `T31-8` remains checked
- Section 9 changelog impact:
  - Added Wave 8 Test 31 rerun entry with canonical prefix `test-31-live-20260302T213603Z`.

## Notes

- No destructive call unexpectedly succeeded in this run.
- Canonical PASS assertions for this test are based on `test-31-live-20260302T213603Z-*`.
