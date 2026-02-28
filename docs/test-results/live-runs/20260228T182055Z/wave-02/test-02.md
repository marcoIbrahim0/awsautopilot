# Test 02

- Wave: 02
- Focus: Signup flow and initial tenant creation contract
- Status: PASS
- Severity (if issue): ⚪ SKIP/NA

## Preconditions

- Identity: New first-time signup user created during this test (`live.test02.rerun.20260228T201419Z.861@example.com`)
- Tenant: New tenant created during signup (`Live E2E Test02 Rerun 20260228T201419Z 861`)
- AWS account: N/A for signup/auth contract checks
- Region(s): N/A for signup/auth contract checks
- Prerequisite IDs/tokens: Bearer token returned by successful signup (`test-02-signup-valid.json`)

## Steps Executed

1. Sent `POST /api/auth/signup` with missing required fields (`{}`) to validate request-body enforcement.
2. Sent `POST /api/auth/signup` with a new unique `company_name`/`email`/`name`/`password` payload and captured the success contract.
3. Re-sent the exact same signup payload to verify duplicate-email handling/idempotency behavior.
4. Used the returned signup `access_token` as Bearer auth for immediate `GET /api/auth/me` verification.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/signup` | `{}` | `422` | Validation error with required-field details for `company_name`, `email`, `name`, `password` | 2026-02-28T20:14:38Z | `evidence/api/test-02-signup-missing-fields.status`, `evidence/api/test-02-signup-missing-fields.json` |
| 2 | POST | `https://api.valensjewelry.com/api/auth/signup` | `{"company_name":"Live E2E Test02 Rerun 20260228T201419Z 861","email":"live.test02.rerun.20260228T201419Z.861@example.com","name":"Live Test02 Rerun 20260228T201419Z","password":"<REDACTED>"}` | `201` | Signup succeeded; response contains top-level `access_token`, `token_type:"bearer"`, `user.role:"admin"`, and tenant object | 2026-02-28T20:14:40Z | `evidence/api/test-02-signup-valid.status`, `evidence/api/test-02-signup-valid.json` |
| 3 | POST | `https://api.valensjewelry.com/api/auth/signup` | Same payload as step 2 | `409` | Duplicate email correctly rejected with `{"detail":"Email already registered"}` | 2026-02-28T20:14:41Z | `evidence/api/test-02-signup-duplicate.status`, `evidence/api/test-02-signup-duplicate.json` |
| 4 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <access_token from step 2>` | `200` | Authenticated profile/tenant contract valid immediately after signup; user email and tenant name match created identity | 2026-02-28T20:14:41Z | `evidence/api/test-02-post-signup-auth-check.status`, `evidence/api/test-02-post-signup-auth-check.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| Signup flow rendering | Signup and post-signup session should be UI-compatible | N/A (API-only execution for this test pass) | N/A |

## Assertions

- Positive path: PASS (`POST /api/auth/signup` returned `201`; immediate authenticated `GET /api/auth/me` returned `200`)
- Negative path: PASS (missing-fields request returned `422`; duplicate-email retry returned `409`)
- Auth boundary: PASS (new signup token granted authenticated access to tenant-scoped `/api/auth/me`)
- Contract shape: PASS (top-level `access_token` present; `user` includes `role`; `tenant` includes `id`, `name`, `external_id`)
- Idempotency/retry: PASS (retrying identical signup request does not create another user; returns `409`)
- Auditability: PASS (all required artifacts saved under `evidence/api/`, including created identity metadata)

## Tracker Updates

- Primary tracker section/row: Section 2 row #1 remains validated as fixed from live evidence.
- Tracker section hint: Section 2 and Section 4.
- Section 8 checkbox impact: None.
- Section 9 changelog update needed: No new issue introduced by Test 02 rerun.

## Notes

- Generated test identity details are stored in `evidence/api/test-02-created-user.txt`.
- No response/field-shape mismatch affecting signup wiring was observed in this rerun.
- No duplicate-handling bug was observed; backend returned expected conflict status on replay.
