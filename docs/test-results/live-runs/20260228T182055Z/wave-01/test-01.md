# Test 01

- Wave: 01
- Focus: Platform/API health and baseline connectivity
- Status: FAIL
- Severity (if issue): 🟠 HIGH

## Preconditions

- Identity: Unauthenticated checks + synthetic invalid-login user (`nonexistent@example.com`)
- Tenant: N/A for health/connectivity checks
- AWS account: N/A for health/connectivity checks
- Region(s): N/A (public service endpoints only)
- Prerequisite IDs/tokens: None

## Steps Executed

1. Verified frontend and backend endpoint availability over HTTPS (`/`, `/health`, `/ready`, `/docs`).
2. Executed CORS preflight for `POST /api/auth/login` from frontend origin.
3. Executed invalid-credential login attempt and protocol/security-header checks.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | GET | `https://dev.valensjewelry.com/` | None | `200` | Frontend root reachable over HTTPS | 2026-02-28T18:26:57Z | `evidence/api/test-01-frontend-https-headers.txt` |
| 2 | GET | `https://api.valensjewelry.com/health` | None | `200` | `{"status":"ok","app":"AWS Security Autopilot"}` | 2026-02-28T18:26:57Z | `evidence/api/test-01-api-health.json` |
| 3 | GET | `https://api.valensjewelry.com/ready` | None | `503` | Ready state degraded (`ready=false`) with SQS AccessDenied details | 2026-02-28T18:27:57Z | `evidence/api/test-01-api-ready.json` |
| 4 | GET | `https://api.valensjewelry.com/docs` | None | `200` | Swagger UI page served | 2026-02-28T18:27:57Z | `evidence/api/test-01-api-docs.html` |
| 5 | OPTIONS | `https://api.valensjewelry.com/api/auth/login` | Origin + preflight headers | `200` | CORS allows origin `https://dev.valensjewelry.com` and methods `DELETE,GET,OPTIONS,PATCH,POST,PUT` | 2026-02-28T18:26:42Z | `evidence/api/test-01-cors-preflight.txt` |
| 6 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"nonexistent@example.com","password":"wrongpass"}` | `401` | Invalid credentials correctly rejected with `{"detail":"Invalid email or password"}` | 2026-02-28T18:26:53Z | `evidence/api/test-01-login-invalid.status`, `evidence/api/test-01-login-invalid.json` |
| 7 | GET | `http://dev.valensjewelry.com/` | None | `200` | HTTP frontend endpoint responds directly; no redirect to HTTPS | 2026-02-28T18:27:57Z | `evidence/api/test-01-frontend-http-check.txt` |
| 8 | GET | `http://api.valensjewelry.com/health` | None | `000` (curl connection failure) | Port 80 unreachable for API endpoint | 2026-02-28T18:28:00Z | `evidence/api/test-01-api-http-check.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| Frontend load | Root page loads over HTTPS | Loaded successfully (HTTP headers captured) | N/A (API-driven run; no browser screenshot) |
| API docs accessibility | Swagger docs page available | Swagger UI title present | N/A (saved HTML artifact) |

## Assertions

- Positive path: PASS (`/`, `/health`, `/docs` reachable on HTTPS)
- Negative path: PASS (invalid login returns `401`)
- Auth boundary: PASS (unauthorized login attempt rejected correctly)
- Contract shape: PASS for tested endpoints (`/health` and login error shape)
- Idempotency/retry: N/A for Test 01 scope (non-mutating checks only)
- Auditability: PASS (all command outputs captured under `evidence/api/`)

## Tracker Updates

- Primary tracker section/row: Section 7 (`Test 01` environment/protocol note) + Quick Status Board (Wave 1)
- Tracker section hint: Section 7 (environment) and Quick Status Board
- Section 8 checkbox impact: No direct checkbox update from this single test
- Section 9 changelog update needed: No (no fix retest in this test)

## Notes

- Frontend HTTPS response includes strong headers (`HSTS`, `CSP`, `X-Frame-Options`, `X-Content-Type-Options`).
- API `/ready` currently degraded due SQS permission/access errors in runtime role; this is an environment readiness signal to address before go-live.
- Frontend HTTP endpoint returning `200` without redirect should be reviewed against strict HTTPS enforcement expectations.
