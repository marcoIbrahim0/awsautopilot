# Test 21

- Wave: 06
- Focus: Export creation-to-download contract (download_url population)
- Status: PASS
- Severity (if issue): N/A

## Preconditions

- Identity: Tenant A admin `maromaher54@gmail.com` (fresh login token minted in this run and revalidated with `GET /api/auth/me`).
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`).
- AWS account: `029037611564`.
- Region(s): `eu-north-1`.
- Prerequisite IDs/tokens: Created export ID `9fd34942-be37-4149-be00-d80d7e9f2f27` in this run.

## Steps Executed

1. Authenticated as tenant admin and captured identity/account context.
2. Created export with `pack_type=evidence` and captured returned export ID.
3. Polled export detail until terminal state (`success`) with timeout guard.
4. Validated `download_url` absence/presence rules from pending and success responses.
5. Downloaded artifact from returned `download_url` (twice), validated ZIP integrity, and checked retry byte consistency.
6. Probed export detail without auth header to verify API boundary.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Login succeeded; bearer token issued. | 2026-03-01T01:11:28Z | `evidence/api/test-21-live-20260301T011127Z-01-login-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <admin_token>` | `200` | Admin context confirmed (`tenant=Valens`, `saas_account_id=029037611564`). | 2026-03-01T01:11:28Z | `evidence/api/test-21-live-20260301T011127Z-02-auth-me-admin.*` |
| 3 | POST | `https://api.valensjewelry.com/api/exports` | `{"pack_type":"evidence"}` + admin token | `202` | Export queued (`id=9fd34942-be37-4149-be00-d80d7e9f2f27`, `status=pending`). | 2026-03-01T01:11:28Z | `evidence/api/test-21-live-20260301T011127Z-03-export-create-evidence.*`, `...-03-export-id.txt` |
| 4 | GET | `https://api.valensjewelry.com/api/exports/9fd34942-be37-4149-be00-d80d7e9f2f27` (poll 1) | `Authorization: Bearer <admin_token>` | `200` | `status=pending`; `download_url=null`; `file_size_bytes=null`. | 2026-03-01T01:11:29Z | `evidence/api/test-21-live-20260301T011127Z-04-export-detail-poll-01.*` |
| 5 | GET | `https://api.valensjewelry.com/api/exports/9fd34942-be37-4149-be00-d80d7e9f2f27` (poll 2, terminal) | `Authorization: Bearer <admin_token>` | `200` | `status=success`; `download_url` present; `file_size_bytes=522980`; `completed_at` populated. | 2026-03-01T01:11:34Z | `evidence/api/test-21-live-20260301T011127Z-04-export-detail-poll-02.*` |
| 6 | GET | `https://api.valensjewelry.com/api/exports/9fd34942-be37-4149-be00-d80d7e9f2f27` | No auth header | `401` | Unauthorized export-detail access blocked. | 2026-03-01T01:11:35Z | `evidence/api/test-21-live-20260301T011127Z-05-export-detail-no-auth.*` |
| 7 | GET | `<download_url from poll 2>` | No auth header (presigned URL) | `200` | Export ZIP downloaded from S3 (`Content-Type: application/zip`, `Content-Length: 522980`). | 2026-03-01T01:11:37Z | `evidence/api/test-21-live-20260301T011127Z-06-export-download-first.*`, `...-06-export-download-first.zip` |
| 8 | GET | `<download_url from poll 2>` (repeat) | No auth header (presigned URL) | `200` | Repeat ZIP download succeeded; same SHA-256 as first download. | 2026-03-01T01:11:38Z | `evidence/api/test-21-live-20260301T011127Z-07-export-download-repeat.*`, `...-07-export-download-repeat.zip` |
| 9 | N/A | Contract summary | N/A | N/A | `download_url_absent_before_terminal_success=true`, `download_url_present_on_success=true`, `retry_raw_bytes_match=true`, `zip_integrity=pass`. | 2026-03-01T01:11:38Z | `evidence/api/test-21-live-20260301T011127Z-09-contract-check.json`, `...-08-export-zip-integrity.txt`, `...-99-context-summary.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/exports` (no auth session) | Route should respond deterministically without crash | `200` HTML shell response; no route-level UI defect observed | `evidence/ui/test-21-live-20260301T011127Z-ui-01-exports-route-no-auth.*` |

## Assertions

- Positive path: PASS. Export create (`202`) transitioned to terminal `success` via polling (`200`), and returned a downloadable artifact.
- Negative path: PASS. No failed terminal state observed; no contract regression detected in pending/success transitions.
- Auth boundary: PASS. `GET /api/exports/{id}` without auth returned `401`. Presigned `download_url` worked without app bearer token as expected for signed S3 URL.
- Contract shape: PASS. Pending detail response had `download_url=null`; success detail response had non-null `download_url` and populated completion/file-size fields.
- Idempotency/retry: PASS. Repeated download of the same `download_url` returned `200` both times and produced byte-identical ZIPs (matching SHA-256).
- Auditability: PASS. Full request/status/headers/body/timestamp artifacts were captured for all API checks plus UI route probe.

## Tracker Updates

- Primary tracker section/row: Section 6 row #3 (`/api/exports` partial implementation).
- Tracker section hint: Section 6
- Section 8 checkbox impact: `T21` marked complete.
- Section 9 changelog update needed: Yes (record Test 21 closure evidence and contract outcome).

## Notes

- Evidence prefix: `test-21-live-20260301T011127Z-*`.
- Poll count to terminal state: `2`.
- No product code changes were made during this live validation run.
