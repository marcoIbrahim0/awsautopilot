# Test 13

- Wave: 05
- Focus: Action/finding detail content completeness
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity: Tenant A admin `maromaher54@gmail.com`; same-tenant member token probe (`role=member`) from prior captured invite acceptance artifact
- Tenant: Tenant A `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`); fresh Tenant B for auth-boundary probe (`tenant_id=3e0f7573-58e9-465c-86cf-129b63932d72`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens: Admin bearer token from `POST /api/auth/login`; action IDs selected from live list: `9c31f438-1ade-4cc7-91c8-b959870a615b`, `f1e6ea20-740e-4ffc-9f1b-24b2e37502db`

## Steps Executed

1. Deployed fix runtime image `20260228T224546Z` to dev SaaS.
2. Logged in as Tenant A admin and captured tenant/account context via `/api/auth/me` and `/api/aws/accounts`.
3. Queried `/api/actions?limit=10&offset=0`, selected two valid action IDs, and executed action-detail calls for both.
4. Repeated action-detail request for the same ID to verify consistency.
5. Executed negative/auth checks: invalid UUID, no token, wrong-tenant token (fresh Tenant B), and same-tenant member-role token.
6. Ran contract assertion against detail payload and verified `what_is_wrong` + `what_the_fix_does` are present and non-empty.
7. Executed minimal UI route checks (`/actions/{id}`, `/actions`) to confirm unauthenticated route behavior is unchanged.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Admin login succeeded | 2026-02-28T22:49:08Z | `evidence/api/test-13-rerun-postdeploy-00-login-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <admin_token>` | `200` | Tenant/user context resolved (`tenant=Valens`, `role=admin`) | 2026-02-28T22:49:23Z | `evidence/api/test-13-rerun-postdeploy-01-auth-me-admin.*` |
| 3 | GET | `https://api.valensjewelry.com/api/aws/accounts` | `Authorization: Bearer <admin_token>` | `200` | Connected account context resolved (`account_id=029037611564`, region `eu-north-1`) | 2026-02-28T22:49:23Z | `evidence/api/test-13-rerun-postdeploy-02-accounts-admin.*` |
| 4 | GET | `https://api.valensjewelry.com/api/actions?limit=10&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Action list returned paginated payload (`total=158`) and valid IDs | 2026-02-28T22:49:24Z | `evidence/api/test-13-rerun-postdeploy-03-actions-list.*` |
| 5 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b` | `Authorization: Bearer <admin_token>` | `200` | Detail now includes `what_is_wrong` and `what_the_fix_does` plus core fields | 2026-02-28T22:49:24Z | `evidence/api/test-13-rerun-postdeploy-04-action-detail-valid-1.*` |
| 6 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b` (repeat) | `Authorization: Bearer <admin_token>` | `200` | Repeat read returned identical payload | 2026-02-28T22:49:25Z | `evidence/api/test-13-rerun-postdeploy-05-action-detail-valid-1-repeat.*`, `evidence/api/test-13-rerun-postdeploy-13-action-detail-consistency.*` |
| 7 | GET | `https://api.valensjewelry.com/api/actions/f1e6ea20-740e-4ffc-9f1b-24b2e37502db` | `Authorization: Bearer <admin_token>` | `200` | Second valid action detail returned complete contract shape | 2026-02-28T22:49:25Z | `evidence/api/test-13-rerun-postdeploy-06-action-detail-valid-2.*` |
| 8 | GET | `https://api.valensjewelry.com/api/actions/3889572a-74e0-452e-a2e9-0633ad75b039` | `Authorization: Bearer <admin_token>` | `404` | Non-existent ID correctly rejected (`Action not found`) | 2026-02-28T22:49:25Z | `evidence/api/test-13-rerun-postdeploy-07-invalid-id.txt`, `evidence/api/test-13-rerun-postdeploy-07-action-detail-invalid-id.*` |
| 9 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b` | No auth header | `401` | Unauthenticated request blocked | 2026-02-28T22:49:26Z | `evidence/api/test-13-rerun-postdeploy-08-action-detail-no-auth.*` |
| 10 | POST | `https://api.valensjewelry.com/api/auth/signup` | Fresh Tenant B signup payload (`password` redacted) | `201` | Tenant B created and token issued for wrong-tenant probe | 2026-02-28T22:49:26Z | `evidence/api/test-13-rerun-postdeploy-09-signup-tenantb.*` |
| 11 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b` | `Authorization: Bearer <tenant_b_token>` | `404` | Cross-tenant action detail access blocked | 2026-02-28T22:49:27Z | `evidence/api/test-13-rerun-postdeploy-10-action-detail-wrong-tenant.*` |
| 12 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <member_token_from_prior_evidence>` | `200` | Same-tenant member token valid (`role=member`) | 2026-02-28T22:49:27Z | `evidence/api/test-13-rerun-postdeploy-11-member-token-source.txt`, `evidence/api/test-13-rerun-postdeploy-11a-auth-me-member.*` |
| 13 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b` | `Authorization: Bearer <member_token_from_prior_evidence>` | `200` | Same-tenant member role can read action detail | 2026-02-28T22:49:28Z | `evidence/api/test-13-rerun-postdeploy-11b-action-detail-member-role-probe.*` |
| 14 | N/A | Contract check (`jq` against action detail response) | N/A | N/A | `what_is_wrong_present=true`, `what_the_fix_does_present=true`; core fields present | 2026-02-28T22:49:28Z | `evidence/api/test-13-rerun-postdeploy-12-action-detail-contract-check.json`, `evidence/api/test-13-rerun-postdeploy-15-context-summary.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/actions/9c31f438-1ade-4cc7-91c8-b959870a615b` (no auth session) | Deterministic unauthenticated route behavior captured | `307` redirect to `/findings` | N/A (API-centric test; no UI-visible defect screenshot produced) |
| `GET https://dev.valensjewelry.com/actions` (no auth session) | Deterministic unauthenticated route behavior captured | `307` redirect to `/findings` | N/A (API-centric test; no UI-visible defect screenshot produced) |

## Assertions

- Positive path: PASS (`GET /api/actions/{id}` returned `200` for both selected valid IDs, including `what_is_wrong` and `what_the_fix_does`).
- Negative path: PASS (random non-existent action ID returned `404` with `Action not found` contract).
- Auth boundary: PASS (`401` no-token, `404` wrong-tenant, and same-tenant `member` role returned `200` for read access).
- Contract shape: PASS (required core contract plus explanation fields present and non-empty).
- Idempotency/retry: PASS (repeat read of same action detail response is byte-identical).
- Auditability: PASS (detail payload includes stable IDs, control/resource linkage, timestamps, and linked findings metadata).

## Tracker Updates

- Primary tracker section/row: Section 2 rows #8 and #9 (`what_is_wrong`, `what_the_fix_does`) marked fixed in post-deploy rerun
- Tracker section hint: Section 2
- Section 8 checkbox impact: `T13` can be marked complete
- Section 9 changelog update needed: Yes (Wave 5 Test 13 fix + rerun verification)

## Notes

- Baseline run at `2026-02-28T22:34:05Z` failed on missing explanation fields; post-deploy rerun at `2026-02-28T22:49:28Z` confirms closure.
- Recheck rerun at `2026-03-01T01:11:19Z` (`evidence/api/test-13-rerun-recheck-20260301T011119Z-*`) reconfirmed PASS behavior: action detail remained `200` with explanation fields present, invalid/non-existent ID remained `404`, no-auth stayed `401`, wrong-tenant stayed `404`, member same-tenant read stayed `200`, and unauthenticated UI route probes remained `307` redirects to `/findings`.
