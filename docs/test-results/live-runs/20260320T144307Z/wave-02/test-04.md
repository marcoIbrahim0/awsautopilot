# Test 04

- Wave: 02
- Focus: Password management and forgot-password behavior
- Status: PASS
- Severity (if issue): ✅ FIXED

## Preconditions

- Identity: `marco.ibrahim@ocypheris.com` admin user
- Tenant: `Valens` (`9f7616d8-af04-43ca-99cd-713625357b70`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens:
  - current password at start of passing run: account restored to the dotted password variant by the end of the run
  - temporary verification password used during test: reverted before completion

## Steps Executed

1. Verified `Forgot password?` opens the reset dialog on the live login page and that `POST /api/auth/forgot-password` returns the generic `200` response.
2. Opened the password-change dialog in live `/settings` and exercised the wrong-current-password case.
3. Changed the password to a temporary value, verified login with that new password in both API and browser flows, then reverted the account to its original current password and verified login again.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `POST` | `/api/auth/forgot-password` | `{email}` | `200` | Generic success body: account existence not disclosed | `2026-03-20T15:05:19Z` | `docs/test-results/live-runs/20260320T144307Z/evidence/api/test-04-forgot-password-headers.txt` |
| 2 | `PUT` | `/api/auth/password` | wrong `old_password` + valid new password | `400` | `Old password is incorrect` | `2026-03-20T17:05:21Z` | `docs/test-results/live-runs/20260320T144307Z/evidence/api/test-04-password-wrong-old-headers.txt` |
| 3 | `PUT` | `/api/auth/password` | correct current password + temporary new password | `204` | Password changed; new token lineage issued with `token_version=2` | `2026-03-20T17:06:13Z` | `docs/test-results/live-runs/20260320T144307Z/evidence/api/test-04-password-success-headers.txt` |
| 4 | `POST` | `/api/auth/login` | temporary password | `200` | Temporary password accepted; login token carries `token_version=2` | `2026-03-20T17:06:55Z` | `docs/test-results/live-runs/20260320T144307Z/evidence/api/test-04-login-temp-headers.txt` |
| 5 | `PUT` | `/api/auth/password` | temporary password + original current password | `204` | Password reverted; new token lineage issued with `token_version=3` | `2026-03-20T17:07:31Z` | `docs/test-results/live-runs/20260320T144307Z/evidence/api/test-04-password-revert-headers.txt` |
| 6 | `POST` | `/api/auth/login` | restored current password | `200` | Final login succeeds after revert; account left in original state | `2026-03-20T17:07:52Z` | `docs/test-results/live-runs/20260320T144307Z/evidence/api/test-04-login-reverted-headers.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| Forgot-password entry point | Reset dialog opens from login | Dialog opened with email field and disabled submit until input | `docs/test-results/live-runs/20260320T144307Z/evidence/ui/forgot-password-dialog.png` |
| Password settings surface | Logged-in settings should expose password change | Account tab shows `Security` section and `Change Password` action | `docs/test-results/live-runs/20260320T144307Z/evidence/ui/settings-page-authenticated.png` |
| Change Password dialog | Current/new/confirm fields present | Modal rendered with all required fields and `Forgot Password?` shortcut | `docs/test-results/live-runs/20260320T144307Z/evidence/ui/change-password-dialog.png` |
| Post-change login | New temporary password should reach authenticated shell | Browser login with temporary password landed on `/findings` | `docs/test-results/live-runs/20260320T144307Z/evidence/ui/findings-after-temp-login.png` |

## Assertions

- Positive path: Forgot-password, password change, new-password login, and password revert all succeeded live.
- Negative path: Wrong-current-password attempt returned `400 Old password is incorrect` and did not change credentials.
- Auth boundary: Password change rotated token lineage on each successful change (`token_version` advanced from `1` to `2` to `3`).
- Contract shape: `PUT /api/auth/password` returned the expected `204` on success and `400` on wrong-old-password; forgot-password remained generic `200`.
- Idempotency/retry: A wrong-old-password attempt left the account unchanged; successful changes issued new cookies/tokens tied to the updated lineage.
- Auditability: Full API headers/bodies plus live screenshots are retained under this run folder.

## Tracker Updates

- Primary tracker section/row: Section 9 changelog only
- Tracker section hint: Section 1, Section 4, and Section 6
- Section 8 checkbox impact: No checkbox change; `T04-2` remained satisfied.
- Section 9 changelog update needed: Added 2026-03-20 auth-session/password-management rerun note.

## Notes

- The account was restored to its starting password state before the run ended.
- The browser was redirected to `/session-expired` after the successful change because I intentionally captured a parallel authenticated API proof for the same password-rotation event; the subsequent browser/API login with the temporary password confirmed the actual credential change succeeded.
