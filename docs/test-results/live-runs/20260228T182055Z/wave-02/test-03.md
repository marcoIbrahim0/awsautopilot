# Test 03

- Wave: 02
- Focus: Login/session lifecycle, refresh, and logout invalidation
- Status: PASS
- Severity (if issue): ⚪ SKIP/NA

## Preconditions

- Identity: Existing admin test user `maromaher54@gmail.com` (credential source: `.cursor/notes/task_log.md`, Pre-live QA Test 04 entry)
- Tenant: `Valens` (confirmed from `GET /api/auth/me` after login)
- AWS account: 1 connected account visible to authenticated user (`GET /api/aws/accounts` returned array count `1`)
- Region(s): N/A for auth/session lifecycle checks
- Prerequisite IDs/tokens: Login-generated bearer token used as auth context for protected/refresh/logout checks

## Steps Executed

1. Executed `POST /api/auth/login` with correct email and wrong password to validate rejection path.
2. Executed `POST /api/auth/login` with valid credentials and captured auth payload.
3. Executed post-login protected checks (`GET /api/auth/me`, `GET /api/aws/accounts`) using returned bearer auth context.
4. Executed `POST /api/auth/refresh` with bearer auth context.
5. Executed `POST /api/auth/logout` with bearer auth context and captured status/body.
6. Executed post-logout `GET /api/auth/me` with pre-logout bearer token to validate invalidation behavior.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"<WRONG_PASSWORD>"}` | `401` | Invalid credentials rejected with `{"detail":"Invalid email or password"}` | 2026-02-28T20:15:32Z | `evidence/api/test-03-login-wrong.status`, `evidence/api/test-03-login-wrong.json` |
| 2 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"<REDACTED_VALID_PASSWORD>"}` | `200` | Login succeeded; response includes top-level `access_token`, `token_type`, `user`, and `tenant` | 2026-02-28T20:15:33Z | `evidence/api/test-03-login-valid.status`, `evidence/api/test-03-login-valid.json` |
| 3 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <access_token from step 2>` | `200` | Authenticated user profile returned (`user.email=maromaher54@gmail.com`, `user.role=admin`, `tenant.name=Valens`) | 2026-02-28T20:15:34Z | `evidence/api/test-03-auth-me-after-login.status`, `evidence/api/test-03-auth-me-after-login.json` |
| 4 | GET | `https://api.valensjewelry.com/api/aws/accounts` | `Authorization: Bearer <access_token from step 2>` | `200` | Protected accounts endpoint accessible post-login (array response, count `1`) | 2026-02-28T20:15:34Z | `evidence/api/test-03-accounts-after-login.status`, `evidence/api/test-03-accounts-after-login.json` |
| 5 | POST | `https://api.valensjewelry.com/api/auth/refresh` | `Authorization: Bearer <access_token from step 2>` | `200` | Refresh endpoint present; returned new auth payload with `access_token` and `token_type:"bearer"` | 2026-02-28T20:15:35Z | `evidence/api/test-03-refresh.status`, `evidence/api/test-03-refresh.json` |
| 6 | POST | `https://api.valensjewelry.com/api/auth/logout` | `Authorization: Bearer <access_token from step 2>` | `204` | Logout endpoint returned no-content success (empty response body) | 2026-02-28T20:15:35Z | `evidence/api/test-03-logout.status`, `evidence/api/test-03-logout.body` |
| 7 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <pre-logout access_token>` | `401` | Pre-logout bearer token invalidated after logout (`{"detail":"Invalid or expired token"}`) | 2026-02-28T20:15:36Z | `evidence/api/test-03-post-logout-auth-check.status`, `evidence/api/test-03-post-logout-auth-check.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| Login/session lifecycle | UI should rely on API auth contract; no direct UI interaction required for this run | N/A (API-driven execution only) | N/A |

## Assertions

- Positive path: PASS (valid login `200`; post-login protected checks `/api/auth/me` and `/api/aws/accounts` both `200`; refresh `200`; logout `204`)
- Negative path: PASS (wrong-password login rejected with `401`)
- Auth boundary: PASS (post-logout pre-logout bearer token correctly rejected with `401`)
- Contract shape: PASS (`/api/auth/refresh` returned expected `access_token` + `token_type`; login and `/me` response shapes were valid)
- Idempotency/retry: PARTIAL (single-run lifecycle executed; repeated login/logout retries were not executed in this test)
- Auditability: PASS (all required artifacts and session behavior notes captured under `evidence/api/`)

## Tracker Updates

- Primary tracker section/row: Section 1 row #2 (`/api/auth/refresh`), Section 3 row #13 (post-logout bearer invalidation), Section 4 row #1 (logout invalidation flow)
- Tracker section hint: Section 1, Section 3, Section 4
- Section 8 checkbox impact: `T03-1` is now satisfied from rerun evidence and should be marked complete.
- Section 9 changelog update needed: Yes (fixed behavior confirmed by live rerun evidence)

## Notes

- Credential source reused from existing project artifact history: `.cursor/notes/task_log.md` (`maromaher54@gmail.com / Maher730`).
- Session notes are stored in `evidence/api/test-03-session-notes.txt`.
- Auth context used for refresh/logout checks in this rerun: bearer token from valid login response.
