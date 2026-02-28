# Test 10

- Wave: 04
- Focus: RBAC boundaries for protected operations
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity: Tenant A admin + same-tenant member token
- Tenant: `Valens`
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens: Admin user id and account id resolved from live API; member token validated with `/api/auth/me`

## Steps Executed

1. Verified unauthenticated access rejection on core protected endpoints.
2. Verified member-role denial on user/account destructive endpoints.
3. Probed `/api/internal/weekly-digest` auth guard before and after fix.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/findings` (no auth) | none | `401` | Unauthenticated blocked | 2026-02-28T22:16:33Z | `evidence/api/test-10-rerun-postdeploy-findings-no-auth.status`, `.json`, `.headers` |
| 2 | GET | `/api/aws/accounts` (no auth) | none | `401` | Unauthenticated blocked | 2026-02-28T22:16:33Z | `evidence/api/test-10-rerun-postdeploy-accounts-no-auth.status`, `.json`, `.headers` |
| 3 | GET | `/api/remediation-runs` (no auth) | none | `401` | Unauthenticated blocked | 2026-02-28T22:16:34Z | `evidence/api/test-10-rerun-postdeploy-runs-no-auth.status`, `.json`, `.headers` |
| 4 | DELETE | `/api/users/{admin_user_id}` (member token) | `Authorization: Bearer <member_token>` | `403` | Member cannot delete users | 2026-02-28T22:16:34Z | `evidence/api/test-10-rerun-postdeploy-delete-admin-user-member.status`, `.json`, `.headers` |
| 5 | DELETE | `/api/aws/accounts/{account_id}?cleanup_resources=false` (member token) | `Authorization: Bearer <member_token>` | `403` | Member cannot delete AWS accounts | 2026-02-28T22:16:34Z | `evidence/api/test-10-rerun-postdeploy-delete-account-member.status`, `.json`, `.headers` |
| 6 | POST | `/api/internal/weekly-digest` (baseline) | `Authorization: Bearer <member_token>` | `503` | Previously leaked config-state (`DIGEST_CRON_SECRET unset`) | 2026-02-28T22:06:35Z | `evidence/api/test-10-08-weekly-digest-member-bearer.status`, `.json`, `.headers` |
| 7 | POST | `/api/internal/weekly-digest` (post-fix, member bearer) | `Authorization: Bearer <member_token>` | `403` | Now consistently denied with auth-guard error contract | 2026-02-28T22:16:34Z | `evidence/api/test-10-rerun-postdeploy-weekly-digest-member-bearer.status`, `.json`, `.headers` |
| 8 | POST | `/api/internal/weekly-digest` (post-fix, wrong secret) | `X-Digest-Cron-Secret: wrong-secret` | `403` | Invalid secret correctly denied | 2026-02-28T22:16:34Z | `evidence/api/test-10-rerun-postdeploy-weekly-digest-wrong-secret.status`, `.json`, `.headers` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| N/A (API-only Wave 4 run) | RBAC/auth boundary confirmed from API contracts | Confirmed from rerun evidence | N/A |

## Assertions

- Positive path: PASS (member token itself is valid: `/api/auth/me` returned `200`).
- Negative path: PASS (unauthenticated requests blocked with `401`; member destructive actions blocked with `403`).
- Auth boundary: PASS (`/api/internal/weekly-digest` now returns `403` for unauthorized calls).
- Contract shape: PASS (internal auth error normalized to `{"detail":"Invalid or missing X-Digest-Cron-Secret."}`).
- Idempotency/retry: PASS (repeated unauthorized calls remain denied deterministically).
- Auditability: PASS (baseline and rerun artifacts both retained).

## Tracker Updates

- Primary tracker section/row: Section 4 row #9 (`/api/internal/*` auth guard)
- Tracker section hint: Section 2 and Section 3
- Section 8 checkbox impact: `T20-9` can be marked complete
- Section 9 changelog update needed: Yes (Wave 4 Test 10 rerun fix)

## Notes

- Invite endpoint does not return invite token in response (expected behavior); member-role checks used a validated same-tenant member token from prior captured evidence (`test-08` postdeploy accept-invite artifact).
