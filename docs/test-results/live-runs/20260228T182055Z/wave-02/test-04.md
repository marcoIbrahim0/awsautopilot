# Test 04

- Wave: 02
- Focus: Password management and forgot-password behavior
- Status: PASS
- Severity (if issue): ⚪ SKIP/NA

## Preconditions

- Identity: Existing admin test user `maromaher54@gmail.com` (credential source: `.cursor/notes/task_log.md`, Pre-live QA Test 04 entry)
- Tenant: `Valens` (confirmed from profile load response)
- AWS account: N/A for password/security endpoint checks
- Region(s): N/A for password/security endpoint checks
- Prerequisite IDs/tokens: Valid login performed inline to obtain bearer token for profile/password-change checks

## Steps Executed

1. Loaded current auth-context profile endpoint (`GET /api/auth/me`, as used by `frontend/src/contexts/AuthContext.tsx`) to confirm authenticated profile contract.
2. Attempted password change via `PUT /api/auth/password` using wrong current password.
3. Attempted password change via `PUT /api/auth/password` using correct current password.
4. Tried login with the proposed new password.
5. Reverted password back to original credential after successful change/new-password-login preconditions.
6. Triggered forgot-password request (`POST /api/auth/forgot-password`) for existing account.
7. Performed non-existing-email forgot-password probe to check account-existence leakage behavior.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <valid token>` | `200` | Profile loaded successfully (`user.email=maromaher54@gmail.com`, `user.role=admin`, `tenant.name=Valens`) | 2026-02-28T20:14:50Z | `evidence/api/test-04-profile-load.status`, `evidence/api/test-04-profile-load.json` |
| 2 | PUT | `https://api.valensjewelry.com/api/auth/password` | `{"old_password":"DefinitelyWrong!","new_password":"<REDACTED_NEW_PASSWORD>"}` | `400` | Wrong current password correctly rejected (`{"detail":"Old password is incorrect"}`) | 2026-02-28T20:14:50Z | `evidence/api/test-04-password-change-wrong.status`, `evidence/api/test-04-password-change-wrong.json` |
| 3 | PUT | `https://api.valensjewelry.com/api/auth/password` | `{"old_password":"<REDACTED_ORIGINAL_PASSWORD>","new_password":"<REDACTED_NEW_PASSWORD>"}` | `204` | Password change succeeded (no-content response) | 2026-02-28T20:14:52Z | `evidence/api/test-04-password-change-correct.status`, `evidence/api/test-04-password-change-correct.json` |
| 4 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"<REDACTED_NEW_PASSWORD>"}` | `200` | New-password login succeeded with auth payload (`access_token`, `user`, `tenant`) | 2026-02-28T20:14:53Z | `evidence/api/test-04-login-new-password.status`, `evidence/api/test-04-login-new-password.json` |
| 5 | PUT | `https://api.valensjewelry.com/api/auth/password` | `{"old_password":"<REDACTED_NEW_PASSWORD>","new_password":"<REDACTED_ORIGINAL_PASSWORD>"}` | `204` | Password revert succeeded (no-content response) | 2026-02-28T20:14:54Z | `evidence/api/test-04-password-revert.status`, `evidence/api/test-04-password-revert.json` |
| 6 | POST | `https://api.valensjewelry.com/api/auth/forgot-password` | `{"email":"maromaher54@gmail.com"}` | `200` | Forgot-password endpoint returned generic message | 2026-02-28T20:14:55Z | `evidence/api/test-04-forgot-password.status`, `evidence/api/test-04-forgot-password.json` |
| 7 | POST | `https://api.valensjewelry.com/api/auth/forgot-password` | `{"email":"no-user-test04-rerun-1772309688@example.com"}` | `200` | Existing and non-existing probes returned same generic response (`no_diff_observed`) | 2026-02-28T20:14:55Z | `evidence/api/test-04-security-notes.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| Password/security lifecycle | Validate API behavior backing settings-security UX | N/A (API-driven execution only) | N/A |

## Assertions

- Positive path: PASS (profile load `200`; password change correct path `204`; login with new password `200`; revert `204`; forgot-password `200`)
- Negative path: PASS (wrong-current-password path returns expected `400` validation error)
- Auth boundary: PASS (password change requires authenticated context; post-change login contract works and revert completed)
- Contract shape: PASS (`PUT /api/auth/password` and `POST /api/auth/forgot-password` are implemented and returned expected response contracts)
- Idempotency/retry: PARTIAL (single full change/revert cycle executed; repeated multi-cycle retries were not run)
- Auditability: PASS (all required artifacts and security notes captured)

## Tracker Updates

- Primary tracker section/row: Section 1 row #1 (`/api/auth/password`) and row #15 (`/api/auth/forgot-password`) now fixed; Section 4 row #2 (password change flow) and row #14 (forgot-password flow) now fixed; Section 6 row #6 now fixed.
- Tracker section hint: Section 1, Section 4, Section 6
- Section 8 checkbox impact: `T04-2` is now satisfied from rerun evidence and should be marked complete.
- Section 9 changelog update needed: Yes (fixed behavior confirmed by live rerun evidence)

## Notes

- Credentials used: `maromaher54@gmail.com / Maher730` (source documented in `.cursor/notes/task_log.md`).
- Auth-context profile endpoint selection is based on current frontend source (`frontend/src/contexts/AuthContext.tsx` uses `GET /api/auth/me`).
- Forgot-password non-leak check result is recorded in `evidence/api/test-04-security-notes.txt` (`forgot_password_account_enumeration_signal=no_diff_observed`).
