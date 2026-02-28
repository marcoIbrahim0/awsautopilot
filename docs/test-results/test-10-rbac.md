---
Test 10 — RBAC and Protected Endpoint Access
Run date: 2026-02-28
Status: FAIL

ENVIRONMENT VALUES
BACKEND_API_URL=https://api.valensjewelry.com
ADMIN_TOKEN_SOURCE=docs/test-results/test-01-api-health.md
NON_ADMIN_TOKEN_SOURCE=member user created via /api/users/invite + /api/users/accept-invite (Test 04 signup user is role=admin)
NON_ADMIN_USER_EMAIL=rbac-member-1772236566@valensjewelry.com
NON_ADMIN_ROLE=member
---

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 10.1 Unauthenticated findings rejected | `401` | `GET /api/findings` without auth -> HTTP `401` | PASS |
| 10.2 Unauthenticated accounts rejected | `401` | `GET /api/aws/accounts` without auth -> HTTP `401` | PASS |
| 10.3 Unauthenticated remediation rejected | `401` | `GET /api/remediation-runs` without auth -> HTTP `401` | PASS |
| 10.4 Non-admin cannot delete another user | `403` | `DELETE /api/users/{admin_user_id}` with member token -> HTTP `403` | PASS |
| 10.5 Non-admin cannot delete AWS account (as provided script) | `403` | Using provided selector (`ACCOUNT_ID=.[0].id`) produced UUID path input and returned HTTP `422` while account existed; final pass skipped because no account rows remained | FAIL |
| 10.6 Internal endpoint rejects user token | `401` or `403` | `POST /api/internal/weekly-digest` with `Authorization: Bearer $ADMIN_TOKEN` -> HTTP `503` | FAIL |
| 10.7 Internal endpoint accepts correct secret | `200` or `202` | `INTERNAL_SECRET` not found in `backend/.env*`; test as written could not execute | SKIPPED |

### Additional Security Validation (critical)

| Check | Expected | Actual | Severity |
|------|---------|--------|----------|
| Non-admin delete AWS account with valid account-id path | `403` | `DELETE /api/aws/accounts/029037611564` with member token returned HTTP `204` (successful delete) when account existed | **CRITICAL SECURITY BLOCKER** |
| Post-delete onboarding role presence | Read/Write roles should still exist unless an authorized admin intentionally removes them | Immediate post-check via `aws iam get-role` for `SecurityAutopilotReadRole` and `SecurityAutopilotWriteRole` returned `NoSuchEntity` | **CRITICAL SECURITY BLOCKER** |

Failed tests:
* 10.5 Non-admin cannot delete AWS account (as-provided command returned `422` instead of RBAC `403`)
* 10.6 Internal endpoint rejects user token (`503`)

Critical blockers:
* Non-admin user can successfully execute admin-impacting account deletion (`HTTP 204`) when using valid 12-digit `account_id` path.

Blocking for go-live: yes

Notes:
- No protected endpoint returned `200` without authentication in tests 10.1-10.3.
- Test 04 signup user is `role=admin`, so it is not suitable as a non-admin RBAC token source.
- Internal weekly digest endpoint is guarded by `X-Digest-Cron-Secret`/`DIGEST_CRON_SECRET` in current backend code; the test script's `INTERNAL_SECRET` + `X-Internal-Secret` assumptions do not match implementation.
- During critical check reproduction, account deletion succeeded and removed the connected account from `/api/aws/accounts` for the tested tenant.
- Post-check confirmed onboarding IAM roles were removed (`SecurityAutopilotReadRole`, `SecurityAutopilotWriteRole`), indicating destructive cleanup executed under a non-admin token path.
