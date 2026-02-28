---
Test 06 — Auth Tokens and JWT Expiry
Run date: 2026-02-28
Status: FAIL

ENVIRONMENT VALUES
BACKEND_API_URL=https://api.valensjewelry.com
ADMIN_TOKEN_SOURCE=docs/test-results/test-01-api-health.md
ADMIN_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1N2U2NThkOS1kNWMxLTQ3OGEtODFmOC04Y2YwNDAwZDAwMWUiLCJ0ZW5hbnRfaWQiOiIxOWI4ZDdjNi0wMTAwLTQyMWEtYTA4NC1jOGIwNmQ0NjY4MzciLCJleHAiOjE3NzI4MzcwOTB9.XKImRpmOQ-dLZHD1UxSqTq5Kw2oL1z7fI-MovGfeo00

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 6.1 Token expiry is 60 minutes or less | `TTL <= 3600` seconds based on `exp - iat` | Decoded ADMIN token payload: `{\"exp\":1772837090,\"iat\":null}` so `TTL` cannot be computed from `iat`. Fresh live login token check showed `TTL_FROM_NOW_SECONDS=608400` (`10140` minutes), which exceeds 60 minutes | FAIL |
| 6.2 JWT_SECRET has no insecure default | No `secret`/`changeme` and no hardcoded fallback | Grep scan showed no `JWT_SECRET=\"secret\"` or `JWT_SECRET=\"changeme\"`, but code has hardcoded fallback `backend/config.py` -> `default=\"change-me-in-production-do-not-use-in-prod\"` | FAIL |
| 6.3 Refresh endpoint exists | HTTP `200` on `POST /api/auth/refresh` | HTTP `404` | FAIL (MISSING) |
| 6.4 Refresh returns new token | Non-empty token in `.token` or `.access_token` | Empty token returned (`length=0`) because refresh endpoint returned 404/not implemented | FAIL |
| 6.5 Invalid token rejected by protected endpoint | HTTP `401` | HTTP `401` | PASS |
| 6.6 Missing token rejected | HTTP `401` | HTTP `401` | PASS |
| 6.7 Malformed Authorization header rejected | HTTP `401` | HTTP `401` | PASS |

Failed tests:
* 6.1 Token expiry is 60 minutes or less
* 6.2 JWT_SECRET has no insecure default
* 6.3 Refresh endpoint exists
* 6.4 Refresh returns new token

Blocking for go-live: yes
Notes: Requested source file `docs/test-results/test-01-environment.md` was not present in the repository; test inputs were read from `docs/test-results/test-01-api-health.md` (which is marked as the environment source for downstream tests).
---
