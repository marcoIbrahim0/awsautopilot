# Test 11

- Wave: 04
- Focus: Findings filtering correctness and pagination stability
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity: Tenant A admin
- Tenant: `Valens`
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Prerequisite IDs/tokens: Admin bearer token from live login

## Steps Executed

1. Verified multi-severity filtering contract with `severity=CRITICAL,HIGH`.
2. Probed invalid severity handling (`severity=NOPE`) baseline vs post-fix.
3. Verified pagination stability (`limit=50` page 1 vs page 2 duplicate-ID check).

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/findings?severity=CRITICAL,HIGH&limit=100&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Returned only `CRITICAL`/`HIGH` severities (`total=39`) | 2026-02-28T22:16:36Z | `evidence/api/test-11-rerun-postdeploy-severity-multi.status`, `.json`, `.headers` |
| 2 | GET | `/api/findings?severity=NOPE&limit=20&offset=0` (baseline) | `Authorization: Bearer <admin_token>` | `200` | Previously returned empty dataset (`{"items":[],"total":0}`) | 2026-02-28T22:07:07Z | `evidence/api/test-11-02-findings-severity-invalid.status`, `.json`, `.headers` |
| 3 | GET | `/api/findings?severity=NOPE&limit=20&offset=0` (post-fix) | `Authorization: Bearer <admin_token>` | `400` | Invalid severity now rejected with explicit validation error | 2026-02-28T22:16:36Z | `evidence/api/test-11-rerun-postdeploy-severity-invalid.status`, `.json`, `.headers` |
| 4 | GET | `/api/findings?limit=50&offset=0` | `Authorization: Bearer <admin_token>` | `200` | Page 1 returned 50 records | 2026-02-28T22:16:36Z | `evidence/api/test-11-rerun-postdeploy-page1.status`, `.json`, `.headers` |
| 5 | GET | `/api/findings?limit=50&offset=50` | `Authorization: Bearer <admin_token>` | `200` | Page 2 returned 50 records; cross-page duplicate IDs = `0` | 2026-02-28T22:16:37Z | `evidence/api/test-11-rerun-postdeploy-page2.status`, `.json`, `.headers` |
| 6 | GET | `/api/findings/grouped?limit=20&offset=0` (twice) | `Authorization: Bearer <admin_token>` | `200` | First 20 group keys stable across repeated calls | 2026-02-28T22:16:37Z | `evidence/api/test-11-rerun-postdeploy-grouped-a.status`, `...grouped-b.status`, corresponding `.json/.headers` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| N/A (API-only Wave 4 run) | Filter/pagination contracts validated via API | Confirmed from rerun artifacts | N/A |

## Assertions

- Positive path: PASS (multi-severity filter and grouped endpoint behave correctly).
- Negative path: PASS (invalid severity now returns `400` validation error).
- Auth boundary: PASS (authenticated path as expected; no unexpected auth bypass observed).
- Contract shape: PASS (invalid filter emits explicit `detail.error="Invalid severity"`).
- Idempotency/retry: PASS (grouped response top slice stable across repeated calls).
- Auditability: PASS (diagnostic summary and raw payload artifacts present).

## Tracker Updates

- Primary tracker section/row: Section 4 row #3 (multi-value filter) and row #4 (pagination duplicates)
- Tracker section hint: Section 4
- Section 8 checkbox impact: `T11-3` and `T11-4` can be marked complete
- Section 9 changelog update needed: Yes (Wave 4 Test 11 rerun fixes)

## Notes

- Post-fix invalid-severity error body: `{"detail":{"error":"Invalid severity", ...}}`.
