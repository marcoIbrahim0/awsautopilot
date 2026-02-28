# Test 08

- Wave: 03
- Focus: Invite endpoint contract coverage and invite-token lifecycle enforcement
- Status: PASS
- Severity (if issue): ⚪ SKIP/NA

## Preconditions

- Identity: Existing admin test user `maromaher54@gmail.com`
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens: Admin bearer token from `POST /api/auth/login`; lifecycle invite tokens obtained from DB evidence files:
  - Valid token: `51a4fa58-1439-4a11-a92f-ef36f378544d`
  - Expired token: `13a1d138-d1b7-414f-b980-8fcac843f091`

## Steps Executed

1. Executed invite auth-boundary checks (`POST /api/users/invite` with and without auth).
2. Executed invalid-token-format checks on `GET /api/users/invite-info`, `GET /api/users/accept-invite`, and `POST /api/users/accept-invite`.
3. Ran valid-token lifecycle: created invite, confirmed invite-info payload, and accepted invite successfully once.
4. Replayed consumed valid token on invite-info and accept-invite endpoints.
5. Ran expired-token lifecycle: created invite, forced expiry via DB update evidence, then tested invite-info and accept-invite expired behavior.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/users/invite` | `Authorization: Bearer <admin_token>`, `{"email":"wave3auth+20260228T214336Z@example.com"}` | `201` | Authenticated invite creation succeeded | 2026-02-28T21:45:24Z | `evidence/api/test-08-rerun-20260228T214336Z-invite-auth.status`, `evidence/api/test-08-rerun-20260228T214336Z-invite-auth.json`, `evidence/api/test-08-rerun-20260228T214336Z-invite-auth.request.txt` |
| 2 | POST | `https://api.valensjewelry.com/api/users/invite` | No auth header, `{"email":"wave3auth+20260228T214336Z@example.com"}` | `401` | Unauthenticated invite creation rejected (`Not authenticated`) | 2026-02-28T21:45:24Z | `evidence/api/test-08-rerun-20260228T214336Z-invite-no-auth.status`, `evidence/api/test-08-rerun-20260228T214336Z-invite-no-auth.json`, `evidence/api/test-08-rerun-20260228T214336Z-invite-no-auth.request.txt` |
| 3 | GET | `https://api.valensjewelry.com/api/users/invite-info?token=not-a-uuid` | None | `400` | Invalid token format rejected by invite-info alias | 2026-02-28T21:45:22Z | `evidence/api/test-08-rerun-20260228T214336Z-invite-info-invalid-token-format.status`, `evidence/api/test-08-rerun-20260228T214336Z-invite-info-invalid-token-format.json`, `evidence/api/test-08-rerun-20260228T214336Z-invite-info-invalid-token-format.request.txt` |
| 4 | GET | `https://api.valensjewelry.com/api/users/accept-invite?token=not-a-uuid` | None | `400` | Canonical GET accept-invite invalid format rejected | 2026-02-28T21:45:22Z | `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-get-invalid-token-format.status`, `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-get-invalid-token-format.json`, `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-get-invalid-token-format.request.txt` |
| 5 | POST | `https://api.valensjewelry.com/api/users/accept-invite` | `{"token":"not-a-uuid","password":"TempPass123!","name":"Wave3 Invalid"}` | `400` | Canonical POST accept-invite invalid format rejected | 2026-02-28T21:45:24Z | `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-post-invalid-token-format.status`, `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-post-invalid-token-format.json`, `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-post-invalid-token-format.request.txt` |
| 6 | POST | `https://api.valensjewelry.com/api/users/invite` | `Authorization: Bearer <admin_token>`, `{"email":"wave3valid+20260228T214336Z@example.com"}` | `201` | Valid-lifecycle invite seed created | 2026-02-28T21:45:25Z | `evidence/api/test-08-rerun-20260228T214336Z-invite-auth-valid-lifecycle.status`, `evidence/api/test-08-rerun-20260228T214336Z-invite-auth-valid-lifecycle.json`, `evidence/api/test-08-rerun-20260228T214336Z-invite-auth-valid-lifecycle.request.txt` |
| 7 | GET | `https://api.valensjewelry.com/api/users/invite-info?token=51a4fa58-1439-4a11-a92f-ef36f378544d` | None | `200` | Invite-info returned expected invite metadata (`email`, `tenant_name`, `inviter_name`) | 2026-02-28T21:46:37Z | `evidence/api/test-08-rerun-20260228T214336Z-invite-info-valid-token.status`, `evidence/api/test-08-rerun-20260228T214336Z-invite-info-valid-token.json`, `evidence/api/test-08-rerun-20260228T214336Z-invite-info-valid-token.request.txt` |
| 8 | POST | `https://api.valensjewelry.com/api/users/accept-invite` | `{"token":"51a4fa58-1439-4a11-a92f-ef36f378544d","password":"Wave3TempPass123!","name":"Wave3 Valid User"}` | `200` | Invite accepted once; auth payload returned for new member user | 2026-02-28T21:46:38Z | `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-valid-token.status`, `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-valid-token.json`, `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-valid-token.request.txt` |
| 9 | GET | `https://api.valensjewelry.com/api/users/invite-info?token=51a4fa58-1439-4a11-a92f-ef36f378544d` | None | `404` | Reused consumed token rejected (`Invite not found or expired`) | 2026-02-28T21:46:38Z | `evidence/api/test-08-rerun-20260228T214336Z-invite-info-reused-token.status`, `evidence/api/test-08-rerun-20260228T214336Z-invite-info-reused-token.json`, `evidence/api/test-08-rerun-20260228T214336Z-invite-info-reused-token.request.txt` |
| 10 | POST | `https://api.valensjewelry.com/api/users/accept-invite` | Replayed consumed token payload | `404` | Reused consumed token rejected on accept-invite | 2026-02-28T21:46:38Z | `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-reused-token.status`, `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-reused-token.json`, `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-reused-token.request.txt` |
| 11 | POST | `https://api.valensjewelry.com/api/users/invite` | `Authorization: Bearer <admin_token>`, `{"email":"wave3exp+20260228T214336Z@example.com"}` | `201` | Expired-lifecycle invite seed created | 2026-02-28T21:45:25Z | `evidence/api/test-08-rerun-20260228T214336Z-invite-auth-expired-lifecycle.status`, `evidence/api/test-08-rerun-20260228T214336Z-invite-auth-expired-lifecycle.json`, `evidence/api/test-08-rerun-20260228T214336Z-invite-auth-expired-lifecycle.request.txt` |
| 12 | GET | `https://api.valensjewelry.com/api/users/invite-info?token=13a1d138-d1b7-414f-b980-8fcac843f091` | None | `410` | Expired token rejected (`This invite has expired`) | 2026-02-28T21:46:39Z | `evidence/api/test-08-rerun-20260228T214336Z-invite-info-expired-token.status`, `evidence/api/test-08-rerun-20260228T214336Z-invite-info-expired-token.json`, `evidence/api/test-08-rerun-20260228T214336Z-invite-info-expired-token.request.txt` |
| 13 | POST | `https://api.valensjewelry.com/api/users/accept-invite` | `{"token":"13a1d138-d1b7-414f-b980-8fcac843f091","password":"Wave3ExpiredPass123!","name":"Wave3 Expired User"}` | `410` | Expired token rejected on accept-invite | 2026-02-28T21:46:39Z | `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-expired-token.status`, `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-expired-token.json`, `evidence/api/test-08-rerun-20260228T214336Z-accept-invite-expired-token.request.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| Invite contract and token lifecycle checks | Invite-info alias should resolve, valid invite should be single-use, replay/expired tokens should be rejected | Observed `200` on valid pre-accept lookup, `404` on replay, and `410` on expired token across invite-info and accept-invite paths | N/A (`evidence/ui/test-08-rerun-20260228T214336Z-ui-notes.txt`) |

## Assertions

- Positive path: PASS (authenticated invite creation and first-time valid token acceptance succeeded)
- Negative path: PASS (invalid token format rejected with `400`; expired token rejected with `410`)
- Auth boundary: PASS (`POST /api/users/invite` without auth rejected with `401`)
- Contract shape: PASS (`GET /api/users/invite-info` alias and canonical accept-invite endpoints returned expected payload/error contracts)
- Idempotency/retry: PASS (replayed consumed token rejected with `404` on both invite-info and accept-invite paths)
- Auditability: PASS (full API artifact set plus DB token query/update artifacts captured)

## Tracker Updates

- Primary tracker section/row: Section 1 row #3 and Section 3 row #10
- Tracker section hint: Section 1 and Section 3
- Section 8 checkbox impact: `T08-10` remains satisfied from observed replay/expiry rejection behavior
- Section 9 changelog update needed: No additional entry (fix retest already logged in changelog)

## Notes

- DB-backed lifecycle evidence artifacts:
  - `evidence/api/test-08-rerun-20260228T214336Z-valid-token-db-query.txt`
  - `evidence/api/test-08-rerun-20260228T214336Z-expired-token-db-query.txt`
  - `evidence/api/test-08-rerun-20260228T214336Z-expired-token-db-update.txt`
