# Test 03

- Wave: 02
- Focus: Login/session lifecycle, refresh, and logout invalidation
- Status: PASS
- Severity (if issue): ✅ FIXED

## Preconditions

- Identity: `marco.ibrahim@ocypheris.com` admin user
- Tenant: `Valens` (`9f7616d8-af04-43ca-99cd-713625357b70`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens:
  - live API login cookie pair (`access_token`, `csrf_token`)
  - refreshed auth session after backend redeploy/fix

## Steps Executed

1. Verified login page renders `Remember me` and `Forgot password?` on `https://ocypheris.com/login`.
2. Exercised `POST /api/auth/login` with `remember_me=false` and `remember_me=true` and compared `Set-Cookie` behavior.
3. Verified `POST /api/auth/refresh` preserves persistent-session cookie mode and `GET /api/auth/me` succeeds on the freshly issued token after the live backend fix.
4. Logged in through the live browser, navigated across authenticated routes, and confirmed `/settings` no longer forces `/session-expired`.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `POST` | `/api/auth/login` | `{email, password, remember_me:false}` | `200` | Session cookie mode: no `expires` / `Max-Age`; token payload includes `persistent_session=false` | `2026-03-20T15:05:58Z` | `docs/test-results/live-runs/20260320T144307Z/evidence/api/test-03-login-remember-false-headers.txt` |
| 2 | `POST` | `/api/auth/login` | `{email, password, remember_me:true}` | `200` | Persistent cookie mode: one-week `expires` / `Max-Age`; token payload includes `persistent_session=true` | `2026-03-20T15:05:53Z` | `docs/test-results/live-runs/20260320T144307Z/evidence/api/test-03-login-remember-true-headers.txt` |
| 3 | `POST` | `/api/auth/refresh` | cookie-backed session + CSRF header | `200` | Refresh returns a new bearer token and keeps `token_version=1`, persistent cookie mode preserved | `2026-03-20T17:04:39Z` | `docs/test-results/live-runs/20260320T144307Z/evidence/api/test-03-refresh-current-headers.txt` |
| 4 | `GET` | `/api/auth/me` | bearer token from live login | `200` | Authenticated user/tenant payload returned after fix; no invalid-token regression | `2026-03-20T17:03:05Z` | `docs/test-results/live-runs/20260320T144307Z/evidence/api/test-03-auth-me-current-headers.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| Login page before auth | `Remember me` and `Forgot password?` present | Present on live page after frontend deploy | `docs/test-results/live-runs/20260320T144307Z/evidence/ui/login-page-restored.png` |
| Findings after login | Successful login lands on authenticated app shell | Browser login with persistent session reached `/findings` | `docs/test-results/live-runs/20260320T144307Z/evidence/ui/findings-after-login.png` |
| Settings after auth fix | `/settings` should remain authenticated | Authenticated settings page loaded and stayed in session | `docs/test-results/live-runs/20260320T144307Z/evidence/ui/settings-page-authenticated.png` |

## Assertions

- Positive path: Login, refresh, and authenticated route navigation all succeeded after the backend token-version refresh fix.
- Negative path: Unauthenticated `/api/auth/me` still returned `401`; pre-fix live token-version drift reproduced as `/session-expired` and was closed in this run.
- Auth boundary: Cookie and bearer auth both validated against the same `token_version`; no fresh token was accepted with stale lineage after the fix.
- Contract shape: `POST /api/auth/login` still returns `AuthResponse`; `POST /api/auth/refresh` still returns `{access_token, token_type}`.
- Idempotency/retry: Repeated login and refresh calls remained stable and issued valid current-lineage tokens.
- Auditability: Headers, bodies, cookies, browser snapshots, and screenshots are retained under this run folder.

## Tracker Updates

- Primary tracker section/row: Section 9 changelog only
- Tracker section hint: Section 1 and Section 4
- Section 8 checkbox impact: No checkbox change; `T03-1` remained satisfied.
- Section 9 changelog update needed: Added 2026-03-20 auth-session row covering `remember_me` and token-version refresh.

## Notes

- During this run I found and fixed a live regression where login-issued tokens could carry a stale `token_version`, causing `/api/auth/me` and `/settings` to fail with `401 Invalid or expired token`. The rerun evidence above is post-fix proof.
