# Test 16

- Wave: 05
- Focus: Action detail/options/preview and recompute/reconcile endpoint behavior
- Status: PASS
- Severity (if issue): N/A

## Preconditions

- Identity: Tenant A admin token reused from `evidence/api/test-14-00-login-admin.json` and validated in this rerun via `GET /api/auth/me`; same-tenant member token reused from `docs/test-results/live-runs/20260228T182055Z/evidence/api/test-08-rerun-postdeploy-accept-invite-valid-token.json`.
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`); fresh Tenant B created for wrong-tenant probe (`wave5.test16.rerun.20260301T000355Z.27402@example.com`).
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens: Selected action `action_id=9c31f438-1ade-4cc7-91c8-b959870a615b` (`action_type=sg_restrict_public_ports`, `actions_total=158` from `GET /api/actions`); non-existent action probe ID `db75620c-3d43-44c1-8976-6e3929905b48`; compute/reconcile payload `{"account_id":"029037611564","region":"eu-north-1"}`; context summary in `evidence/api/test-16-rerun-postdeploy-26-context-summary.txt`.

## Steps Executed

1. Redeployed backend runtime with current toggles and reran full Test 16 live probes.
2. Re-validated action detail/options/preview sequence for a live action, including realistic preview mode from options (`mode=pr_only`).
3. Re-ran negative probes (invalid action ID format, non-existent action ID) and no-auth probes for detail/options/preview.
4. Executed wrong-tenant probe using a fresh Tenant B token against Tenant A action detail.
5. Re-ran recompute and reconcile write flows with first-call + immediate-retry + auth-boundary probes.
6. Captured contract and retry summary artifacts from live responses.
7. Re-ran UI no-auth route probes for `/actions` and `/actions/{id}`.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <admin_token>` | `200` | Admin tenant context confirmed (`tenant=Valens`) | 2026-03-01T00:03:51Z | `evidence/api/test-16-rerun-postdeploy-01-auth-me-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/aws/accounts` | `Authorization: Bearer <admin_token>` | `200` | Account/region context resolved (`029037611564`, `eu-north-1`) | 2026-03-01T00:03:51Z | `evidence/api/test-16-rerun-postdeploy-02-accounts-admin.*` |
| 3 | GET | `https://api.valensjewelry.com/api/actions?limit=50&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Actions list returned (`total=158`), selected `action_id=9c31f438-1ade-4cc7-91c8-b959870a615b` | 2026-03-01T00:03:52Z | `evidence/api/test-16-rerun-postdeploy-03-actions-list.*`, `evidence/api/test-16-rerun-postdeploy-26-context-summary.txt` |
| 4 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b` | `Authorization: Bearer <admin_token>` | `200` | Action detail returned with explanation fields (`what_is_wrong`, `what_the_fix_does`) | 2026-03-01T00:03:52Z | `evidence/api/test-16-rerun-postdeploy-04-action-detail-primary.*` |
| 5 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b` (repeat) | `Authorization: Bearer <admin_token>` | `200` | Repeat detail response byte-identical | 2026-03-01T00:03:52Z | `evidence/api/test-16-rerun-postdeploy-05-action-detail-primary-repeat.*`, `evidence/api/test-16-rerun-postdeploy-27-action-detail-consistency.*` |
| 6 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b/remediation-options` | `Authorization: Bearer <admin_token>` | `200` | Options returned (`mode_options=["pr_only"]`, `strategies=[]`) | 2026-03-01T00:03:53Z | `evidence/api/test-16-rerun-postdeploy-06-remediation-options-primary.*` |
| 7 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b/remediation-preview` | `Authorization: Bearer <admin_token>` | `200` | Default preview path returned direct-fix-not-supported message | 2026-03-01T00:03:53Z | `evidence/api/test-16-rerun-postdeploy-07-remediation-preview-default.*` |
| 8 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b/remediation-preview?mode=pr_only` | `Authorization: Bearer <admin_token>` | `200` | Realistic mode from options accepted (`pr_only`) with informational preview response | 2026-03-01T00:03:53Z | `evidence/api/test-16-rerun-postdeploy-08-remediation-preview-realistic.*` |
| 9 | GET | `https://api.valensjewelry.com/api/actions/not-a-uuid` | `Authorization: Bearer <admin_token>` | `400` | Invalid ID format rejected (`Invalid action_id`) | 2026-03-01T00:03:54Z | `evidence/api/test-16-rerun-postdeploy-09-action-detail-invalid-format.*` |
| 10 | GET | `https://api.valensjewelry.com/api/actions/db75620c-3d43-44c1-8976-6e3929905b48` | `Authorization: Bearer <admin_token>` | `404` | Non-existent action ID rejected (`Action not found`) | 2026-03-01T00:03:54Z | `evidence/api/test-16-rerun-postdeploy-10-action-detail-non-existent.*`, `evidence/api/test-16-rerun-postdeploy-09-non-existent-id.txt` |
| 11 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b` | No auth header | `401` | Unauthenticated action detail access blocked | 2026-03-01T00:03:55Z | `evidence/api/test-16-rerun-postdeploy-11-action-detail-no-auth.*` |
| 12 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b/remediation-options` | No auth header | `401` | Unauthenticated options access blocked | 2026-03-01T00:03:55Z | `evidence/api/test-16-rerun-postdeploy-12-remediation-options-no-auth.*` |
| 13 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b/remediation-preview` | No auth header | `401` | Unauthenticated preview access blocked | 2026-03-01T00:03:55Z | `evidence/api/test-16-rerun-postdeploy-13-remediation-preview-no-auth.*` |
| 14 | POST | `https://api.valensjewelry.com/api/auth/signup` | Fresh Tenant B signup payload (`password` present in raw request artifact) | `201` | Tenant B token issued for wrong-tenant probe | 2026-03-01T00:03:56Z | `evidence/api/test-16-rerun-postdeploy-14-signup-tenantb.*` |
| 15 | GET | `https://api.valensjewelry.com/api/actions/9c31f438-1ade-4cc7-91c8-b959870a615b` | `Authorization: Bearer <tenant_b_token>` | `404` | Wrong-tenant action detail access blocked (`Action not found`) | 2026-03-01T00:03:56Z | `evidence/api/test-16-rerun-postdeploy-15-action-detail-wrong-tenant.*` |
| 16 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <member_token>` | `200` | Same-tenant member context confirmed (`role=member`) | 2026-03-01T00:03:57Z | `evidence/api/test-16-rerun-postdeploy-16-auth-me-member.*` |
| 17 | POST | `https://api.valensjewelry.com/api/actions/compute` | `{"account_id":"029037611564","region":"eu-north-1"}` + admin token | `202` | Recompute job queued with stable contract (`message`, `tenant_id`, `scope`) | 2026-03-01T00:03:57Z | `evidence/api/test-16-rerun-postdeploy-17-actions-compute-first.*` |
| 18 | POST | `https://api.valensjewelry.com/api/actions/compute` (immediate retry) | Same payload as #17 | `202` | Immediate retry returned same status/body | 2026-03-01T00:03:58Z | `evidence/api/test-16-rerun-postdeploy-18-actions-compute-retry-immediate.*`, `evidence/api/test-16-rerun-postdeploy-25-retry-check.json` |
| 19 | POST | `https://api.valensjewelry.com/api/actions/compute` | Same payload + member token | `202` | Member-role call accepted and queued | 2026-03-01T00:03:58Z | `evidence/api/test-16-rerun-postdeploy-19-actions-compute-member-role.*` |
| 20 | POST | `https://api.valensjewelry.com/api/actions/compute` | Same payload, no auth header | `401` | Unauthenticated compute call blocked | 2026-03-01T00:03:58Z | `evidence/api/test-16-rerun-postdeploy-20-actions-compute-no-auth.*` |
| 21 | POST | `https://api.valensjewelry.com/api/actions/reconcile` | `{"account_id":"029037611564","region":"eu-north-1"}` + admin token | `202` | Reconcile write path accepted; response includes `message`, `tenant_id`, `scope`, `enqueued_jobs=10` | 2026-03-01T00:03:59Z | `evidence/api/test-16-rerun-postdeploy-21-actions-reconcile-first.*` |
| 22 | POST | `https://api.valensjewelry.com/api/actions/reconcile` (immediate retry) | Same payload as #21 | `202` | Immediate retry returned same status/body | 2026-03-01T00:03:59Z | `evidence/api/test-16-rerun-postdeploy-22-actions-reconcile-retry-immediate.*`, `evidence/api/test-16-rerun-postdeploy-25-retry-check.json` |
| 23 | POST | `https://api.valensjewelry.com/api/actions/reconcile` | Same payload, no auth header | `401` | Unauthenticated reconcile write call blocked | 2026-03-01T00:04:00Z | `evidence/api/test-16-rerun-postdeploy-23-actions-reconcile-no-auth.*` |
| 24 | N/A | Contract shape checks (`jq`) | N/A | N/A | Required fields and mode compatibility checks pass for detail/options/preview/compute/reconcile | 2026-03-01T00:04:00Z | `evidence/api/test-16-rerun-postdeploy-24-contract-check.json` |
| 25 | N/A | Retry consistency checks (`jq`) | N/A | N/A | `compute` first/retry = `202/202`; `reconcile` first/retry = `202/202` | 2026-03-01T00:04:00Z | `evidence/api/test-16-rerun-postdeploy-25-retry-check.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/actions` (no auth session) | Deterministic route behavior without crash | `307` redirect to `/findings`; no UI-visible defect in route probe | N/A (no UI defect requiring screenshot) |
| `GET https://dev.valensjewelry.com/actions/9c31f438-1ade-4cc7-91c8-b959870a615b` (no auth session) | Deterministic route behavior without crash | `307` redirect to `/findings`; no UI-visible defect in route probe | N/A (no UI defect requiring screenshot) |

## Assertions

- Positive path: PASS for action detail/options/default preview, realistic preview mode compatibility, recompute queueing, and reconcile queueing (`GET detail/options/preview` -> `200`; `POST /api/actions/compute` -> `202`; `POST /api/actions/reconcile` -> `202`).
- Negative path: PASS. Invalid ID format and non-existent ID handling remained correct (`400`/`404`).
- Auth boundary: PASS. Detail/options/preview no-auth probes returned `401`, wrong-tenant action detail returned `404`, compute no-auth probe returned `401`, and reconcile no-auth probe returned `401`.
- Contract shape: PASS. Required keys are present and validated in `test-16-rerun-postdeploy-24-contract-check.json` for detail/options/preview/compute/reconcile.
- Idempotency/retry: PASS. Immediate retries returned stable statuses for both write endpoints (`compute` and `reconcile` both `202` first/retry).
- Auditability: PASS for observed write contracts and complete raw artifacts (`request`, `status`, `headers`, `json/body`, `timestamp`) across API/UI captures.

## Tracker Updates

- Primary tracker section/row: Section 4 rows #16 and #17 moved to ✅ FIXED from post-deploy rerun evidence.
- Tracker section hint: Section 1 row #10 moved from ⚪ SKIP/NA to ✅ FIXED.
- Section 8 checkbox impact: `T16-preview` and `T16-reconcile` checked complete.
- Section 9 changelog update needed: Yes (Test 16 closure entry for preview compatibility + reconcile write path).

## Notes

- Observed mode compatibility now matches live options contract: `mode_options=["pr_only"]` and `GET remediation-preview?mode=pr_only` returns `200`.
- `POST /api/actions/reconcile` is now an authenticated write path (`202` for admin, `401` without auth) and no longer returns `405 Allow: GET`.
- Recheck rerun at `2026-03-01T00:12:59Z` (`evidence/api/test-16-rerun-recheck-20260301T001237Z-*`) reconfirmed PASS behavior: realistic preview mode stayed `200`, compute/reconcile stayed `202` on first + immediate retry, and no-auth probes stayed `401`.
