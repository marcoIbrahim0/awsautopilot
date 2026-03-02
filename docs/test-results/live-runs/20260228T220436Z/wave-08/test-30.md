# Test 30

- Wave: 08
- Focus: Login rate-limit and Retry-After contract checks
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity:
  - Dedicated rate-limit test identity: `wave8.test30.20260302T211956Z@example.com`
  - Control identity (existing tenant admin): `maromaher54@gmail.com`
- Tenant:
  - Dedicated identity tenant: `Wave8 Test30 20260302T211956Z` (`tenant_id=412941af-20e0-4fdb-90f6-2bfd363b9ff8`)
  - Control tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account (environment context): `029037611564`
- Region(s): `eu-north-1`
- Canonical evidence prefix: `test-30-live-20260302T211956Z-*`
- First throttle event: wrong-password attempt `#6` returned `429` with `retry-after: 895`

## Steps Executed

1. Created a dedicated identity and captured tenant preconditions (`signup` + `auth/me`).
2. Executed repeated wrong-password `POST /api/auth/login` attempts on the dedicated identity.
3. Verified transition pattern: `401` for attempts `1-5`, then `429` on attempt `6`.
4. Verified correct-password behavior while blocked (still `429`) and different-email key independence (`200` control login).
5. Ran abuse-path probes (alternate email wrong-first-try, spoofed `X-Forwarded-For`, invalid payload schema).
6. Waited the observed lockout window from response header (`895s`) and re-ran dedicated correct-password login.
7. Verified post-window success (`200`) and token usability via `GET /api/auth/me` (`200`).
8. Captured no-auth UI login-route probe.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/signup` | Dedicated identity signup payload | `201` | Dedicated identity/tenant created for isolated lockout checks. | 2026-03-02T21:19:57Z | `evidence/api/test-30-live-20260302T211956Z-01-signup-dedicated.*` |
| 2 | GET | `https://api.valensjewelry.com/api/auth/me` | Bearer dedicated token | `200` | Dedicated identity context confirmed (`tenant_id=412941af-20e0-4fdb-90f6-2bfd363b9ff8`). | 2026-03-02T21:19:58Z | `evidence/api/test-30-live-20260302T211956Z-02-auth-me-dedicated.*` |
| 3 | POST | `https://api.valensjewelry.com/api/auth/login` | Control admin valid credentials | `200` | Control login succeeds during dedicated lockout sequence. | 2026-03-02T21:19:59Z | `evidence/api/test-30-live-20260302T211956Z-03-login-admin-control.*` |
| 4 | POST | `https://api.valensjewelry.com/api/auth/login` | Dedicated email + wrong password (attempts 1-5) | `401` x5 | Invalid credentials rejected before threshold. | 2026-03-02T21:19:59Z to 2026-03-02T21:20:03Z | `evidence/api/test-30-live-20260302T211956Z-04-login-dedicated-wrong-attempt-01.*` ... `...-05.*` |
| 5 | POST | `https://api.valensjewelry.com/api/auth/login` | Dedicated email + wrong password (attempt 6) | `429` | Threshold transition observed with `retry-after: 895`. | 2026-03-02T21:20:04Z | `evidence/api/test-30-live-20260302T211956Z-04-login-dedicated-wrong-attempt-06.*` |
| 6 | POST | `https://api.valensjewelry.com/api/auth/login` | Dedicated email + correct password (while blocked) | `429` | Correct credentials remain blocked during active window (`retry-after: 895`). | 2026-03-02T21:20:04Z | `evidence/api/test-30-live-20260302T211956Z-05-login-dedicated-correct-while-blocked.*` |
| 7 | POST | `https://api.valensjewelry.com/api/auth/login` | Control admin valid credentials (repeat) | `200` | Different-email key remains unaffected. | 2026-03-02T21:20:05Z | `evidence/api/test-30-live-20260302T211956Z-06-login-admin-control-repeat.*` |
| 8 | POST | `https://api.valensjewelry.com/api/auth/login` | Alternate non-existent email + wrong password (first try) | `401` | Alternate email key starts with normal invalid-credential response. | 2026-03-02T21:20:05Z | `evidence/api/test-30-live-20260302T211956Z-07-login-alt-email-wrong-first-try.*` |
| 9 | POST | `https://api.valensjewelry.com/api/auth/login` | Dedicated email + wrong password + `X-Forwarded-For` override | `429` | Still throttled; spoofed client IP does not bypass lockout (`retry-after: 893`). | 2026-03-02T21:20:06Z | `evidence/api/test-30-live-20260302T211956Z-08-login-dedicated-wrong-spoofed-xff.*` |
| 10 | POST | `https://api.valensjewelry.com/api/auth/login` | Invalid payload (`email` format invalid) | `422` | Schema validation contract enforced. | 2026-03-02T21:20:06Z | `evidence/api/test-30-live-20260302T211956Z-09-login-invalid-payload.*` |
| 11 | Wait evidence | N/A | `retry-after=895` wait window | N/A | Waited full lockout window (`start_utc=2026-03-02T21:20:06Z`, `end_utc=2026-03-02T21:35:01Z`). | 2026-03-02T21:20:06Z to 2026-03-02T21:35:01Z | `evidence/api/test-30-live-20260302T211956Z-10-rate-limit-wait.txt` |
| 12 | POST + GET | `/api/auth/login` + `/api/auth/me` | Dedicated email correct password post-window + bearer token | `200 / 200` | Lockout cleared after wait; token is valid and usable. | 2026-03-02T21:35:03Z | `evidence/api/test-30-live-20260302T211956Z-11-login-dedicated-correct-after-window.*`, `...-12-auth-me-dedicated-after-window.*` |
| 13 | Summary | Final status digest | N/A | N/A | Consolidated transition/retry/window outcomes for quick validation. | 2026-03-02 | `evidence/api/test-30-live-20260302T211956Z-99-summary.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/login` (no auth) | Public login route renders without exposing tenant data | Returned `200` app route with standard security headers; API auth boundaries remained enforced. | `evidence/ui/test-30-live-20260302T211956Z-ui-01-login-route-no-auth.*` |

## Assertions

- Positive path: PASS. Dedicated identity login succeeded after full wait window (`200`), and `/api/auth/me` returned `200`.
- Negative path: PASS. Wrong-password attempts returned `401` until threshold and then `429`.
- Auth boundary: PASS. Correct credentials did not bypass active lockout (`429` while blocked).
- Contract shape: PASS. `429` responses include `retry-after`; invalid payload returns `422`.
- Idempotency/retry: PASS. Rate-limit countdown behavior observed and full-window recovery confirmed.
- Auditability: PASS. Full per-request artifacts captured plus summary output.

## Tracker Updates

- Primary tracker section/row:
  - Section 3 row #5 (`Login endpoint not rate-limited after N attempts`) -> ✅ FIXED (revalidated)
  - Section 3 row #6 (`No Retry-After header on 429 response`) -> ✅ FIXED (revalidated)
  - Section 7 row #5 (`Rate limit window duration unknown`) -> ✅ FIXED (revalidated)
- Section 8 checkbox impact:
  - `T30-5` remains checked (`[x]`)
- Section 9 changelog impact:
  - Added Wave 8 Test 30 rerun entry with canonical prefix `test-30-live-20260302T211956Z`.

## Notes

- Non-canonical attempt `test-30-live-20260302T211901Z-*` was retained as evidence but excluded from final assertions because its helper did not parse lowercase `retry-after` and therefore skipped the full wait.
- Canonical PASS assertions for this test are based on `test-30-live-20260302T211956Z-*`.
