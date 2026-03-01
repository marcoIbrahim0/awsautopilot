# Test 14

- Wave: 05
- Focus: Findings API contracts and duplicate-run guard behavior
- Status: PASS
- Severity (if issue): N/A

## Preconditions

- Identity: Tenant A admin `maromaher54@gmail.com` (bearer token sourced from prior successful live login artifact `evidence/api/test-20-live-20260301T011449Z-01-login-admin.json`); fresh Tenant B admin token for cross-tenant probe from `POST /api/auth/signup`
- Tenant: Tenant A `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`); Tenant B created fresh in post-deploy rerun (`2026-03-01T01:34:46Z`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens: `finding_id=16c83cc5-4c33-4f8b-ab10-4508aa3c77c5`; selected `action_id=9c31f438-1ade-4cc7-91c8-b959870a615b`; create payload `{"action_id":"9c31f438-1ade-4cc7-91c8-b959870a615b","mode":"pr_only"}` (no strategy required per remediation-options response)

## Steps Executed

1. Authenticated as Tenant A admin and captured tenant/account context from `/api/auth/me` and `/api/aws/accounts`.
2. Executed findings contract checks: `GET /api/findings`, valid detail lookup, invalid/non-existent detail lookup, and no-auth lookup.
3. Executed findings auth-boundary check using a fresh Tenant B token against Tenant A finding detail.
4. Executed duplicate-run guard flow: selected valid action from `/api/actions`, confirmed no pending runs, fetched `/api/actions/{id}/remediation-options`, created one remediation run, then immediately repeated the same create request.
5. Captured UI route probes for findings pages and recorded no UI-visible breakage requiring screenshots.
6. Re-ran full duplicate-run guard flow post-deploy (`test-14-rerun-postdeploy-20260301T013443Z-*`) and verified immediate retries return `409` with `reason=duplicate_active_run`.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Admin login succeeded; bearer token issued | 2026-02-28T23:03:42Z | `evidence/api/test-14-00-login-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <admin_token>` | `200` | Tenant/user context resolved (`tenant=Valens`, `role=admin`) | 2026-02-28T23:03:43Z | `evidence/api/test-14-01-auth-me-admin.*` |
| 3 | GET | `https://api.valensjewelry.com/api/aws/accounts` | `Authorization: Bearer <admin_token>` | `200` | Account context resolved (`account_id=029037611564`, `regions=["eu-north-1"]`) | 2026-02-28T23:03:43Z | `evidence/api/test-14-02-accounts-admin.*` |
| 4 | GET | `https://api.valensjewelry.com/api/findings?limit=10&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Paginated findings contract returned (`items[]`, `total=391`) | 2026-02-28T23:03:43Z | `evidence/api/test-14-03-findings-list.*` |
| 5 | N/A | Findings contract check (`jq`) | N/A | N/A | Frontend-required list shape/fields present (`id`, `finding_id`, `tenant_id`, `account_id`, `region`, `severity_label`, `severity_normalized`, `status`, `title`, `created_at`, `updated_at_db`) | 2026-02-28T23:03:43Z | `evidence/api/test-14-03b-findings-contract-check.json` |
| 6 | GET | `https://api.valensjewelry.com/api/findings/16c83cc5-4c33-4f8b-ab10-4508aa3c77c5` | `Authorization: Bearer <admin_token>` | `200` | Valid finding detail returned | 2026-02-28T23:03:44Z | `evidence/api/test-14-04-finding-detail-valid.*` |
| 7 | GET | `https://api.valensjewelry.com/api/findings/c15f405b-e8dc-42fd-b9d9-1e1181af7c38` | `Authorization: Bearer <admin_token>` | `404` | Invalid/non-existent finding ID rejected (`Finding not found`) | 2026-02-28T23:03:44Z | `evidence/api/test-14-05-invalid-finding-id.txt`, `evidence/api/test-14-05-finding-detail-invalid.*` |
| 8 | GET | `https://api.valensjewelry.com/api/findings?limit=5&offset=0` | No auth header | `401` | Unauthenticated findings access blocked | 2026-02-28T23:03:45Z | `evidence/api/test-14-06-findings-no-auth.*` |
| 9 | POST | `https://api.valensjewelry.com/api/auth/signup` | Fresh Tenant B signup payload (`password` redacted) | `201` | Tenant B created and token issued for cross-tenant probe | 2026-02-28T23:03:46Z | `evidence/api/test-14-07-signup-tenantb.*` |
| 10 | GET | `https://api.valensjewelry.com/api/findings/16c83cc5-4c33-4f8b-ab10-4508aa3c77c5` | `Authorization: Bearer <tenant_b_token>` | `404` | Cross-tenant finding detail access blocked | 2026-02-28T23:03:46Z | `evidence/api/test-14-08-finding-detail-wrong-tenant.*` |
| 11 | GET | `https://api.valensjewelry.com/api/actions?limit=50&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Action list returned (`total=158`), valid action selected | 2026-02-28T23:03:46Z | `evidence/api/test-14-09-actions-list.*` |
| 12 | GET | `https://api.valensjewelry.com/api/remediation-runs?status=pending&limit=200&offset=0` | `Authorization: Bearer <admin_token>` | `200` | No pre-existing pending runs (`total=0`) before duplicate guard check | 2026-02-28T23:03:47Z | `evidence/api/test-14-10-remediation-runs-pending.*`, `evidence/api/test-14-10-pending-action-ids.txt`, `evidence/api/test-14-10-selected-action-id.txt` |
| 13 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b/remediation-options` | `Authorization: Bearer <admin_token>` | `200` | Options returned with `mode_options=["pr_only"]`, `strategies=[]` (no strategy required) | 2026-02-28T23:03:47Z | `evidence/api/test-14-11-remediation-options.*`, `evidence/api/test-14-11b-create-payload.json` |
| 14 | POST | `https://api.valensjewelry.com/api/remediation-runs` | `{"action_id":"9c31f438-1ade-4cc7-91c8-b959870a615b","mode":"pr_only"}` | `201` | First remediation run created (`id=216b042f-ee97-4dd4-aeaf-51880e2260df`, `status=pending`) | 2026-02-28T23:03:48Z | `evidence/api/test-14-12-create-run-first.*`, `evidence/api/test-14-12-first-run-id.txt` |
| 15 | POST | `https://api.valensjewelry.com/api/remediation-runs` (immediate repeat) | Same payload as step 14 | `409` | Duplicate pending run blocked (`error="Duplicate pending run"`) | 2026-02-28T23:03:48Z | `evidence/api/test-14-13-create-run-second-immediate.*` |
| 16 | GET | `https://api.valensjewelry.com/api/remediation-runs/216b042f-ee97-4dd4-aeaf-51880e2260df` | `Authorization: Bearer <admin_token>` | `200` | Run detail confirms audit fields (`approved_by_user_id`, `created_at`, `action` summary) and `pending` status | 2026-02-28T23:03:48Z | `evidence/api/test-14-14-run-detail-first.*`, `evidence/api/test-14-15-context-summary.txt` |
| 17 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <admin_token>` | `200` | Post-deploy admin token validated; tenant context unchanged (`Valens`) | 2026-03-01T01:34:44Z | `evidence/api/test-14-rerun-postdeploy-20260301T013443Z-01-auth-me-admin.*` |
| 18 | POST | `https://api.valensjewelry.com/api/remediation-runs` | `{"action_id":"9c31f438-1ade-4cc7-91c8-b959870a615b","mode":"pr_only"}` | `201` | First post-deploy run created (`id=e9287ff2-f260-472b-a547-0cd5895744dc`) | 2026-03-01T01:34:49Z | `evidence/api/test-14-rerun-postdeploy-20260301T013443Z-12-create-run-first.*` |
| 19 | POST | `https://api.valensjewelry.com/api/remediation-runs` (immediate repeat) | Same payload as row 18 | `409` | Duplicate blocked with structured conflict (`reason=duplicate_active_run`, `existing_run_id=e9287ff2-f260-472b-a547-0cd5895744dc`) | 2026-03-01T01:34:49Z | `evidence/api/test-14-rerun-postdeploy-20260301T013443Z-13-create-run-second-immediate.*` |
| 20 | POST | `https://api.valensjewelry.com/api/remediation-runs` (third immediate repeat) | Same payload as row 18 | `409` | Repeated immediate retry also blocked with same `existing_run_id` | 2026-03-01T01:34:50Z | `evidence/api/test-14-rerun-postdeploy-20260301T013443Z-14-create-run-third-immediate.*`, `evidence/api/test-14-rerun-postdeploy-20260301T013443Z-16-duplicate-guard-check.json`, `evidence/api/test-14-rerun-postdeploy-20260301T013443Z-99-context-summary.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/findings/16c83cc5-4c33-4f8b-ab10-4508aa3c77c5` (no auth session) | Route should render deterministically without crash | `200` HTML returned; page shell rendered (tenant-id gate visible), no breakage observed | N/A (no UI defect requiring screenshot) |
| `GET https://dev.valensjewelry.com/findings` (no auth session) | Route should render deterministically without crash | `200` HTML returned; page shell rendered, no breakage observed | N/A (no UI defect requiring screenshot) |

## Assertions

- Positive path: PASS (`GET /api/findings` and `GET /api/findings/{valid_id}` returned `200`; first remediation-run create returned `201` with `status=pending`).
- Negative path: PASS (invalid/non-existent finding ID returned `404` with explicit `Finding not found` contract).
- Auth boundary: PASS (`401` for no-auth findings list; `404` for cross-tenant finding detail with Tenant B token).
- Contract shape: PASS (list shape is paginated object with `items[]` + `total`; required frontend finding fields verified present in sampled item via contract-check artifact).
- Idempotency/retry: PASS in latest post-deploy rerun (`POST /api/remediation-runs` statuses `201/409/409` for first + two immediate identical retries; conflict payload includes stable `existing_run_id` and `reason=duplicate_active_run`).
- Auditability: PASS (run detail includes stable run/action IDs, timestamps, status, `approved_by_user_id`, and action summary metadata).

## Tracker Updates

- Primary tracker section/row: Section 4 row #5 (`Test 14 Duplicate run guard`) closed by latest post-deploy rerun (`201` then `409` on immediate duplicate create)
- Tracker section hint: Section 4
- Section 8 checkbox impact: `T14-5` should be checked from post-deploy evidence
- Section 9 changelog update needed: Add fixed-and-retested closure entry for Test 14 duplicate-run guard

## Notes

- Historical post-deploy run (`2026-02-28T23:03:48Z`) showed duplicate-run guard behavior (`201` then immediate `409`) on identical payload.
- Evidence set captured under `evidence/api/test-14-*` and `evidence/ui/test-14-ui-*`; no UI-visible regressions observed during this API-focused test.
- Recheck rerun at `2026-03-01T01:11:19Z` (`evidence/api/test-14-rerun-recheck-20260301T011119Z-*`) observed duplicate-run guard regression: first create `201` (`run_id=4916da70-8c66-4cde-873a-fb08a16f11be`), immediate identical retry `201` (`run_id=2bbcbd12-10e9-479e-a379-5da31b50e790`), and third immediate retry `201` (`run_id=4a108d82-bfa0-4797-a324-4dfb7ad589be`) for the same `action_id=9c31f438-1ade-4cc7-91c8-b959870a615b`.
- Additional recheck artifact `evidence/api/test-14-rerun-recheck-20260301T011119Z-16-duplicate-guard-recheck.json` records retry statuses (`201/201/201`) and run IDs from observed evidence.
- Closure rerun at `2026-03-01T01:34:43Z` (`evidence/api/test-14-rerun-postdeploy-20260301T013443Z-*`) confirms fix on live runtime: first create `201` (`run_id=e9287ff2-f260-472b-a547-0cd5895744dc`), immediate retry `409`, and third immediate retry `409` with stable duplicate metadata (`reason=duplicate_active_run`, `existing_run_id=e9287ff2-f260-472b-a547-0cd5895744dc`).
