# Test 18

- Wave: 06
- Focus: PR bundle download auth and artifact correctness
- Status: PASS
- Severity (if issue): N/A

## Preconditions

- Identity: Tenant A admin token reused from `evidence/api/test-13-rerun-postdeploy-00-login-admin.json` and revalidated via `GET /api/auth/me`; fresh Tenant B token minted for wrong-tenant auth probe.
- Tenant: Tenant A `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`); Tenant B created during run.
- AWS account: `029037611564`.
- Region(s): `eu-north-1`.
- Prerequisite IDs/tokens: Reused post-deploy Test 17 grouped run artifact `run_id=0b91ccbd-1c39-4cb3-8791-4e3a363c0fcb`.

## Steps Executed

1. Confirmed auth context and loaded Test 17 post-deploy run detail.
2. Executed authorized PR bundle ZIP download and repeat authorized download.
3. Executed no-token, invalid-token, and wrong-tenant token download probes.
4. Validated ZIP contract against run artifacts and scanned IaC files for unresolved placeholders.
5. Verified retry consistency and UI route behavior.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <admin_token>` | `200` | Admin context confirmed. | 2026-03-01T01:01:40Z | `evidence/api/test-18-rerun-postdeploy-20260301T010114Z-01-auth-me-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/remediation-runs/0b91ccbd-1c39-4cb3-8791-4e3a363c0fcb` | `Authorization: Bearer <admin_token>` | `200` | Source run confirmed `status=success`, `outcome="Group PR bundle generated (25 actions; 1 skipped)`, `artifacts.pr_bundle.files=78`. | 2026-03-01T01:01:40Z | `evidence/api/test-18-rerun-postdeploy-20260301T010114Z-02-run-detail-source-test17.*` |
| 3 | POST | `https://api.valensjewelry.com/api/auth/signup` | Fresh Tenant B signup payload (`company_name` included) | `201` | Tenant B token issued for wrong-tenant probe. | 2026-03-01T01:01:41Z | `evidence/api/test-18-rerun-postdeploy-20260301T010114Z-03-signup-tenantb.*` |
| 4 | GET | `https://api.valensjewelry.com/api/remediation-runs/0b91ccbd-1c39-4cb3-8791-4e3a363c0fcb/pr-bundle.zip` | `Authorization: Bearer <admin_token>` | `200` | Authorized ZIP download succeeded (`application/zip`, attachment header present). | 2026-03-01T01:01:41Z | `evidence/api/test-18-rerun-postdeploy-20260301T010114Z-04-pr-bundle-download-auth-first.*` |
| 5 | GET | same as #4 | No auth header | `401` | Unauthenticated download blocked. | 2026-03-01T01:01:41Z | `evidence/api/test-18-rerun-postdeploy-20260301T010114Z-05-pr-bundle-download-no-auth.*` |
| 6 | GET | same as #4 | `Authorization: Bearer invalid.token.value` | `401` | Invalid-token download blocked. | 2026-03-01T01:01:41Z | `evidence/api/test-18-rerun-postdeploy-20260301T010114Z-06-pr-bundle-download-invalid-token.*` |
| 7 | GET | same as #4 | `Authorization: Bearer <tenant_b_token>` | `404` | Wrong-tenant access blocked (`Remediation run not found`). | 2026-03-01T01:01:41Z | `evidence/api/test-18-rerun-postdeploy-20260301T010114Z-07-pr-bundle-download-wrong-tenant.*` |
| 8 | GET | same as #4 (repeat) | `Authorization: Bearer <admin_token>` | `200` | Repeat authorized download succeeded. | 2026-03-01T01:01:41Z | `evidence/api/test-18-rerun-postdeploy-20260301T010114Z-08-pr-bundle-download-auth-repeat.*` |
| 9 | N/A | ZIP contract validation | N/A | N/A | Expected file count `78`, actual file count `78`, missing `0`, unexpected `0`, `placeholder_hits=[]`, `all_pass=true`. | 2026-03-01T01:03:31Z | `evidence/api/test-18-rerun-postdeploy-20260301T010114Z-09-zip-contract-check.json`, `...-09-zip-file-list.txt` |
| 10 | N/A | Retry consistency check | N/A | N/A | Raw ZIP bytes now deterministic (`raw_zip_bytes_match=true`); semantic match true. | 2026-03-01T01:03:31Z | `evidence/api/test-18-rerun-postdeploy-20260301T010114Z-10-download-retry-consistency.json`, `...-99-context-summary.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/pr-bundles` (no auth session) | Route responds deterministically without crash | `200` HTML shell response; no UI defect observed | N/A |

## Assertions

- Positive path: PASS. Authorized download succeeded with expected ZIP headers and body.
- Auth boundary: PASS. No-auth `401`, invalid-token `401`, wrong-tenant `404`.
- Artifact correctness: PASS. ZIP contents exactly matched run artifact contract and contained no unresolved placeholder tokens in IaC files.
- Retry/determinism: PASS. Repeated downloads are byte-identical and semantically identical.
- Auditability: PASS. Full request/status/headers/body/timestamp artifacts captured for all probes.

## Tracker Updates

- Primary tracker section/row: Section 4 row #8.
- Tracker section hint: Section 4.
- Section 8 checkbox impact: `T18-8` remains complete.
- Section 9 changelog update needed: Yes (close Section 4 row #8 using post-deploy rerun evidence).

## Notes

- Post-deploy rerun evidence prefix: `test-18-rerun-postdeploy-20260301T010114Z-*`.
- Bundle generation recorded `25` generated actions and `1` skipped action in run metadata; downloaded ZIP contract remained internally consistent and passed artifact checks.
- No product code changes were made during this live validation run.
