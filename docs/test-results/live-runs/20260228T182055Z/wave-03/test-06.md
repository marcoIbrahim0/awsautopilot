# Test 06

- Wave: 03
- Focus: Service readiness and onboarding account-scoped endpoint contracts
- Status: PASS
- Severity (if issue): ⚪ SKIP/NA

## Preconditions

- Identity: Existing admin test user `maromaher54@gmail.com`
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens: Admin bearer token from `POST /api/auth/login`; known connected account from `GET /api/aws/accounts`

## Steps Executed

1. Called account-scoped service readiness endpoint with auth and captured contract fields.
2. Called account-scoped control-plane readiness endpoint with auth.
3. Triggered account-scoped onboarding fast-path endpoint with auth.
4. Probed ingest-progress endpoint without required `started_after` query parameter.
5. Recalled ingest-progress with explicit `started_after` value.
6. Executed auth-boundary probes (no auth and invalid token) for service-readiness.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/aws/accounts/029037611564/service-readiness` | `Authorization: Bearer <admin_token>` | `200` | Response includes aggregate readiness (`overall_ready`, `all_*_enabled`) and per-region service booleans/errors | 2026-02-28T21:44:23Z | `evidence/api/test-06-rerun-20260228T214336Z-service-readiness-auth.status`, `evidence/api/test-06-rerun-20260228T214336Z-service-readiness-auth.json`, `evidence/api/test-06-rerun-20260228T214336Z-service-readiness-auth.request.txt` |
| 2 | GET | `https://api.valensjewelry.com/api/aws/accounts/029037611564/control-plane-readiness?stale_after_minutes=30` | `Authorization: Bearer <admin_token>` | `200` | Endpoint returned control-plane freshness contract with `regions[]`, `is_recent`, `age_minutes`, and `overall_ready` | 2026-02-28T21:44:23Z | `evidence/api/test-06-rerun-20260228T214336Z-control-plane-readiness-auth.status`, `evidence/api/test-06-rerun-20260228T214336Z-control-plane-readiness-auth.json`, `evidence/api/test-06-rerun-20260228T214336Z-control-plane-readiness-auth.request.txt` |
| 3 | POST | `https://api.valensjewelry.com/api/aws/accounts/029037611564/onboarding-fast-path` | `Authorization: Bearer <admin_token>` | `200` | Fast-path trigger responded with `fast_path_triggered=true`, queued ingest IDs, and pending gate details | 2026-02-28T21:44:25Z | `evidence/api/test-06-rerun-20260228T214336Z-onboarding-fast-path-auth.status`, `evidence/api/test-06-rerun-20260228T214336Z-onboarding-fast-path-auth.json`, `evidence/api/test-06-rerun-20260228T214336Z-onboarding-fast-path-auth.request.txt` |
| 4 | GET | `https://api.valensjewelry.com/api/aws/accounts/029037611564/ingest-progress` | `Authorization: Bearer <admin_token>` (no `started_after`) | `422` | Validation error confirmed required query field `started_after` | 2026-02-28T21:44:25Z | `evidence/api/test-06-rerun-20260228T214336Z-ingest-progress-missing-started-after.status`, `evidence/api/test-06-rerun-20260228T214336Z-ingest-progress-missing-started-after.json`, `evidence/api/test-06-rerun-20260228T214336Z-ingest-progress-missing-started-after.request.txt` |
| 5 | GET | `https://api.valensjewelry.com/api/aws/accounts/029037611564/ingest-progress?started_after=2026-02-28T00:00:00Z` | `Authorization: Bearer <admin_token>` | `200` | Progress contract returned `status=completed`, `progress=100`, and updated findings metadata | 2026-02-28T21:44:25Z | `evidence/api/test-06-rerun-20260228T214336Z-ingest-progress-with-started-after.status`, `evidence/api/test-06-rerun-20260228T214336Z-ingest-progress-with-started-after.json`, `evidence/api/test-06-rerun-20260228T214336Z-ingest-progress-with-started-after.request.txt` |
| 6 | POST | `https://api.valensjewelry.com/api/aws/accounts/029037611564/service-readiness` | No auth header | `401` | Unauthenticated readiness request rejected | 2026-02-28T21:44:26Z | `evidence/api/test-06-rerun-20260228T214336Z-service-readiness-no-auth.status`, `evidence/api/test-06-rerun-20260228T214336Z-service-readiness-no-auth.json`, `evidence/api/test-06-rerun-20260228T214336Z-service-readiness-no-auth.request.txt` |
| 7 | POST | `https://api.valensjewelry.com/api/aws/accounts/029037611564/service-readiness` | `Authorization: Bearer invalid.token.value` | `401` | Invalid bearer token rejected | 2026-02-28T21:44:26Z | `evidence/api/test-06-rerun-20260228T214336Z-service-readiness-invalid-token.status`, `evidence/api/test-06-rerun-20260228T214336Z-service-readiness-invalid-token.json`, `evidence/api/test-06-rerun-20260228T214336Z-service-readiness-invalid-token.request.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| Onboarding/service-readiness contract check | Response shape should include service-level readiness fields needed by onboarding UI | Observed aggregate `all_*_enabled` fields and `regions[].*_enabled` with per-service error slots | N/A (`evidence/ui/test-06-rerun-20260228T214336Z-ui-notes.txt`) |

## Assertions

- Positive path: PASS (account-scoped readiness and onboarding endpoints returned `200` and expected contract fields)
- Negative path: PASS (`ingest-progress` without `started_after` correctly rejected with `422`)
- Auth boundary: PASS (readiness endpoint rejected no-auth and invalid-token calls with `401`)
- Contract shape: PASS (service-readiness includes aggregate and per-region service status fields used by onboarding)
- Idempotency/retry: PARTIAL (single fast-path trigger execution only; no repeat-trigger dedupe assertion in this run)
- Auditability: PASS (complete request/status/body artifacts plus UI note artifact)

## Tracker Updates

- Primary tracker section/row: Section 1 row #12 and row #13; Section 2 row #3; Section 6 row #1
- Tracker section hint: Section 1, Section 2, Section 6
- Section 8 checkbox impact: `T06` remains satisfied from observed service-readiness shape
- Section 9 changelog update needed: No additional entry (fixed rows already logged in tracker changelog)

## Notes

- `service-readiness` reported `all_access_analyzer_enabled=false` with `missing_access_analyzer_regions=["eu-north-1"]`; endpoint behavior itself matched expected contract.
- `control-plane-readiness` reported stale region state (`overall_ready=false`) but endpoint availability/shape checks passed.
