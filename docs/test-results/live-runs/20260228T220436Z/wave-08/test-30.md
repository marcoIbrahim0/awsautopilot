# Test 30

- Wave: 08
- Focus: Login rate-limit and Retry-After contract checks
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity:
  - Dedicated rate-limit test identity: `wave8.test30.20260302T191232Z@example.com`
  - Control identity (existing tenant admin): `maromaher54@gmail.com`
- Tenant:
  - Dedicated identity tenant: `Wave8 Test30 20260302T191232Z` (`tenant_id=a4c06506-cd92-4e11-abb4-85c7dbe559d9`)
  - Control tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account (environment context): `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens:
  - Canonical evidence prefix: `test-30-live-20260302T191232Z-*`
  - First throttle event: wrong attempt `#6` returned `429` with `retry-after: 896`

## Steps Executed

1. Created a dedicated identity and captured tenant/token preconditions (`signup` + `auth/me`).
2. Executed repeated wrong-password `POST /api/auth/login` attempts for the dedicated identity until threshold behavior appeared.
3. Verified transition pattern for same identity/key: `401` (attempts 1-5) then `429` (attempt 6), with `retry-after` header present.
4. Verified correct-password behavior while blocked (still `429`) and verified different-email key behavior from same client (`200` control login, independent from dedicated lockout).
5. Ran abuse-path probes: alternate wrong-email first try (`401`), spoofed `X-Forwarded-For` attempt (`429`), invalid payload contract (`422`).
6. Probed before-window retry (correct password still `429` with decreasing `retry-after`).
7. Waited the observed rate-limit window (`896` seconds) and re-ran correct-password login for the dedicated identity.
8. Verified post-window success (`200`) and token usability via `GET /api/auth/me` (`200`); captured no-auth UI login-route probe.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/signup` | Dedicated identity signup payload | `201` | Dedicated admin identity/tenant created for isolated lockout checks. | 2026-03-02T19:12:33Z | `evidence/api/test-30-live-20260302T191232Z-01-signup-dedicated.*` |
| 2 | GET | `https://api.valensjewelry.com/api/auth/me` | Bearer dedicated token | `200` | Dedicated identity context confirmed (`tenant_id=a4c06506-...`). | 2026-03-02T19:12:34Z | `evidence/api/test-30-live-20260302T191232Z-02-auth-me-dedicated.*` |
| 3 | POST | `https://api.valensjewelry.com/api/auth/login` | Control admin valid credentials | `200` | Control login succeeds before/around dedicated lockout sequence. | 2026-03-02T19:12:34Z | `evidence/api/test-30-live-20260302T191232Z-03-login-admin-control.*` |
| 4 | POST | `https://api.valensjewelry.com/api/auth/login` | Dedicated email + wrong password (attempts 1-5) | `401` x5 | Invalid credentials rejected; throttle not triggered yet. | 2026-03-02T19:12:35Z to 2026-03-02T19:12:39Z | `evidence/api/test-30-live-20260302T191232Z-04-login-dedicated-wrong-attempt-01.*` ... `...-05.*` |
| 5 | POST | `https://api.valensjewelry.com/api/auth/login` | Dedicated email + wrong password (attempt 6) | `429` | Threshold transition observed; `retry-after: 896` present. | 2026-03-02T19:12:39Z | `evidence/api/test-30-live-20260302T191232Z-04-login-dedicated-wrong-attempt-06.*` |
| 6 | POST | `https://api.valensjewelry.com/api/auth/login` | Dedicated email + correct password (while blocked) | `429` | Correct credentials still blocked during active lockout; `retry-after: 895`. | 2026-03-02T19:12:39Z | `evidence/api/test-30-live-20260302T191232Z-05-login-dedicated-correct-while-blocked.*` |
| 7 | POST | `https://api.valensjewelry.com/api/auth/login` | Control admin valid credentials (repeat) | `200` | Different email key remains unaffected while dedicated key is locked. | 2026-03-02T19:12:40Z | `evidence/api/test-30-live-20260302T191232Z-06-login-admin-control-repeat.*` |
| 8 | POST | `https://api.valensjewelry.com/api/auth/login` | Alternate non-existent email + wrong password (first try) | `401` | Alternate email key starts with normal invalid-credential response (no inherited 429). | 2026-03-02T19:12:41Z | `evidence/api/test-30-live-20260302T191232Z-07-login-alt-email-wrong-first-try.*` |
| 9 | POST | `https://api.valensjewelry.com/api/auth/login` | Dedicated email + wrong password + `X-Forwarded-For` override | `429` | Still throttled; `retry-after: 894` (header spoof does not bypass lockout). | 2026-03-02T19:12:41Z | `evidence/api/test-30-live-20260302T191232Z-08-login-dedicated-wrong-spoofed-xff.*` |
| 10 | POST | `https://api.valensjewelry.com/api/auth/login` | Invalid payload (`email` format invalid) | `422` | Schema validation contract enforced. | 2026-03-02T19:12:41Z | `evidence/api/test-30-live-20260302T191232Z-09-login-invalid-payload.*` |
| 11 | POST | `https://api.valensjewelry.com/api/auth/login` | Dedicated email + correct password (early recheck) | `429` | Still within window before wait completion; `retry-after: 893`. | 2026-03-02T19:12:42Z | `evidence/api/test-30-live-20260302T191232Z-11-login-dedicated-correct-after-window.*` |
| 12 | N/A | Window wait evidence | `retry-after=896` sleep window | N/A | Waited observed lockout duration (`start=2026-03-02T19:13:39Z`, `end=2026-03-02T19:28:35Z`). | 2026-03-02T19:13:39Z to 2026-03-02T19:28:35Z | `evidence/api/test-30-live-20260302T191232Z-12-postwindow-wait.txt` |
| 13 | POST | `https://api.valensjewelry.com/api/auth/login` | Dedicated email + correct password (post-window) | `200` | Lockout cleared after window; token issued. | 2026-03-02T19:28:41Z | `evidence/api/test-30-live-20260302T191232Z-13-login-dedicated-correct-after-window.*` |
| 14 | GET | `https://api.valensjewelry.com/api/auth/me` | Bearer token from row #13 | `200` | Post-window token is valid and usable. | 2026-03-02T19:28:41Z | `evidence/api/test-30-live-20260302T191232Z-14-auth-me-dedicated-after-window.*` |
| 15 | Summary | Final status digest | N/A | N/A | Consolidated transition/retry/window outcomes for quick validation. | 2026-03-02T19:28:41Z | `evidence/api/test-30-live-20260302T191232Z-100-summary-final.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/login` (no auth) | Public login route renders without exposing tenant data | Returned `200` app route with standard security headers; no API auth bypass implied. | `evidence/ui/test-30-live-20260302T191232Z-ui-01-login-route-no-auth.*` |

## Assertions

- Positive path: PASS. Dedicated identity login succeeded with correct credentials after observed lockout window (`200`), and token was valid on `/api/auth/me` (`200`).
- Negative path: PASS. Wrong-password attempts returned `401` until threshold and then `429` with stable error body.
- Auth boundary: PASS. Correct credentials do not bypass active lockout; while blocked, dedicated identity remained `429`.
- Contract shape: PASS. `429` responses include `retry-after`; invalid payload returns `422`; success responses include access token and user/tenant context.
- Idempotency/retry: PASS. Retry-after countdown behavior observed (`896 -> 895 -> 894 -> 893`) and lockout cleared after full window wait.
- Auditability: PASS. Full request/headers/body artifacts saved for each probe, including pre-window and post-window checkpoints.

## Tracker Updates

- Primary tracker section/row:
  - Section 3 row #5 (`Login endpoint not rate-limited after N attempts`) -> ✅ FIXED
  - Section 3 row #6 (`No Retry-After header on 429 response`) -> ✅ FIXED
  - Section 7 row #5 (`Rate limit window duration unknown`) -> ✅ FIXED
- Tracker section hint: Section 3 and Section 7
- Section 8 checkbox impact:
  - `T30-5` -> checked (`[x]`)
- Section 9 changelog update needed:
  - Add Wave 8 Test 30 closure entry with `401 x5 -> 429` transition, `retry-after` evidence, and post-window `200` recovery

## Notes

- Initial run artifact `...-11-login-dedicated-correct-after-window.*` is a deliberate pre-window recheck and correctly remained `429`.
- Final closure assertions rely on post-window evidence `...-12-postwindow-wait.txt`, `...-13-login-dedicated-correct-after-window.*`, and `...-14-auth-me-dedicated-after-window.*`.
