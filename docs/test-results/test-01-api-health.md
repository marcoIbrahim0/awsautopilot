---
Test 01 — API Health and Connectivity
Run date: 2026-02-27
Status: FAIL

ENVIRONMENT VALUES (used by all subsequent tests)
FRONTEND_URL=https://dev.valensjewelry.com
BACKEND_API_URL=https://api.valensjewelry.com
TEST_EMAIL=maromaher54@gmail.com
TEST_PASSWORD=Maher730
ADMIN_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1N2U2NThkOS1kNWMxLTQ3OGEtODFmOC04Y2YwNDAwZDAwMWUiLCJ0ZW5hbnRfaWQiOiIxOWI4ZDdjNi0wMTAwLTQyMWEtYTA4NC1jOGIwNmQ0NjY4MzciLCJleHAiOjE3NzI4MzcwOTB9.XKImRpmOQ-dLZHD1UxSqTq5Kw2oL1z7fI-MovGfeo00
TOKEN_EXPIRES_AT=2026-03-06T22:44:50Z

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 1.1 Frontend reachable | 200 | HTTP 200 | PASS |
| 1.2 No redirect loop | 200 | HTTP 200, redirects=0 | PASS |
| 1.3 API root responds | not 500 | HTTP 200 at https://api.valensjewelry.com/ | PASS |
| 1.4 Health endpoint | 200 ok | HTTP 200, body={"status":"ok","app":"AWS Security Autopilot"} | PASS |
| 1.5 API docs | 200 | HTTP 200 at /docs | PASS |
| 1.6 CORS for frontend | header present | OPTIONS /api/auth/login returned HTTP 200 with Access-Control-Allow-Origin: https://dev.valensjewelry.com | PASS |
| 1.7 Security headers | all 3 present | HEAD /api/auth/login returned HTTP 405; X-Content-Type-Options missing, X-Frame-Options missing, Strict-Transport-Security missing | FAIL |
| 1.8 HTTPS enforced | 301/302 redirect | HTTP 200 on http://dev.valensjewelry.com (no redirect) | FAIL |
| 1.9 SSL valid | 200 no SSL error | HTTP 200 with --ssl-reqd and no SSL errors | PASS |
| 1.10 Login with credentials | 200 + token | HTTP 200 with bearer access_token returned | PASS |

Failed tests:
* 1.7 Security headers
* 1.8 HTTPS enforced

Blocking for go-live: yes
Notes: Backend URL discovered from frontend/runtime config (`frontend/.env`, `frontend/.env.local`, `config/.env.ops`) and deployment config/task logs; active API appears to be API Gateway custom domain (`https://api.valensjewelry.com`) with HTTPS (443) and no explicit port in URL. Response headers include `apigw-requestid`, indicating API Gateway fronting backend runtime.
---
