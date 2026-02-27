---
Test 04 — Signup
Run date: 2026-02-28
Status: PASS

ENVIRONMENT VALUES
FRONTEND_URL=https://dev.valensjewelry.com
BACKEND_API_URL=https://api.valensjewelry.com
TEST_EMAIL=testuser+003422@valensjewelry.com
---

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 4.1 Signup page loads | form loads with fields | All fields loaded | PASS |
| 4.2 Form validation works | validation errors appear | Native validation blocked empty fields and invalid emails; password mismatch error shown | PASS |
| 4.3 Successful signup | redirects to `/onboarding`, no error | Redirected securely | PASS |
| 4.4 Duplicate email blocked | error message | Blocked with "Email already registered" | PASS |
| 4.5 Session is established | still logged in on refresh | Redirect held at `/onboarding`, session active | PASS |
| 4.6 Network request succeeded | HTTP 200/201, no 500 block | API accepted POST without crashing | PASS |

### Test Account Generated:
- **Email:** `testuser+003422@valensjewelry.com`
- **Password:** `TestPassword123!`

*(Note: Test executed via automated browser checks on the dev environment matching requirements.)*
