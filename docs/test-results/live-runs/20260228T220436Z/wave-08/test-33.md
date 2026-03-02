# Test 33

- Wave: 08
- Focus: PR proof artifact completeness (C2/C5 evidence fields)
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity:
  - Tenant A admin: `maromaher54@gmail.com`
  - Wrong-tenant admin (created during run): `wave8.test33.20260302T214046Z@example.com`
- Tenant A: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Canonical evidence prefix: `test-33-live-20260302T214032Z-*`
- Selected non-root target:
  - `action_id=232870db-8f7d-49ee-8361-8ad1bd79eff2`
  - `control_id=S3.2`
  - `resource_id=arn:aws:s3:::arch1-bucket-website-a1-029037611564-eu-north-1`
  - `strategy_id=s3_bucket_block_public_access_standard`
- Remediation run id: `4361b8d2-5600-48ad-b2b4-2cac683f721a`

## Steps Executed

1. Logged in as Valens admin and captured tenant/account/action context.
2. Queried open actions/remediation-options and selected a fresh non-root `pr_only` target in preferred family (`S3.2`).
3. Created remediation run with selected strategy (`risk_acknowledged=true`) and polled run detail to terminal `success`.
4. Captured execution context (`/execution`) and downloaded PR bundle via authorized path.
5. Captured ZIP auth-boundary probes (`401` no-auth, `404` wrong-tenant).
6. Extracted bundle artifacts and validated README C2/C5 fields (`terraform_plan_timestamp_utc`, `preserved_configuration_statement`).
7. Validated proof consistency against run metadata/apply context (`c2_within_run_window_5min=true`, strategy match true, apply-step commands present).

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Admin token issued. | 2026-03-02T21:40:33Z | `evidence/api/test-33-live-20260302T214032Z-01-login-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/auth/me` | Bearer admin token | `200` | Tenant resolved as `Valens`, role=`admin`. | 2026-03-02T21:40:33Z | `evidence/api/test-33-live-20260302T214032Z-02-auth-me-admin.*` |
| 3 | GET | `https://api.valensjewelry.com/api/actions?status=open&limit=200` + remediation-options fanout | Bearer admin token | `200` | Open-action pool queried and target-selection recorded for S3.2 action `232870db-...`. | 2026-03-02T21:40:36Z to 2026-03-02T21:40:39Z | `evidence/api/test-33-live-20260302T214032Z-04-actions-open-preferred.*`, `...-10-remediation-options-232870db-8f7d-49ee-8361-8ad1bd79eff2.*`, `...-05-target-selection.txt` |
| 4 | POST | `https://api.valensjewelry.com/api/remediation-runs` | `{"action_id":"232870db-...","mode":"pr_only","strategy_id":"s3_bucket_block_public_access_standard","risk_acknowledged":true}` | `201` | Run created (`id=4361b8d2-5600-48ad-b2b4-2cac683f721a`, `status=pending`). | 2026-03-02T21:40:42Z | `evidence/api/test-33-live-20260302T214032Z-20-create-run-pr.*`, `...-21-run-id.txt` |
| 5 | GET (poll loop) | `https://api.valensjewelry.com/api/remediation-runs/4361b8d2-5600-48ad-b2b4-2cac683f721a` | Bearer admin token | `200` series | Run reached terminal `success` by poll `2`; final status recorded. | 2026-03-02T21:40:42Z to 2026-03-02T21:40:45Z | `evidence/api/test-33-live-20260302T214032Z-22-run-detail-poll-1.*`, `...-23-run-detail-poll-2.*`, `...-62-run-final-status.txt` |
| 6 | GET | `https://api.valensjewelry.com/api/remediation-runs/4361b8d2-5600-48ad-b2b4-2cac683f721a/execution` | Bearer admin token | `200` | Execution contract returned `status=success`. | 2026-03-02T21:40:46Z | `evidence/api/test-33-live-20260302T214032Z-63-run-execution.*` |
| 7 | GET | `https://api.valensjewelry.com/api/remediation-runs/4361b8d2-5600-48ad-b2b4-2cac683f721a/pr-bundle.zip` | Bearer admin token | `200` | Authorized bundle download succeeded. | 2026-03-02T21:40:46Z | `evidence/api/test-33-live-20260302T214032Z-64-pr-bundle-download-authorized.*`, `evidence/aws/test-33-live-20260302T214032Z-64-pr-bundle.zip` |
| 8 | GET | same as #7 | No auth header | `401` | Unauthenticated bundle download denied. | 2026-03-02T21:40:46Z | `evidence/api/test-33-live-20260302T214032Z-65-pr-bundle-download-no-auth.*` |
| 9 | POST + GET | `/api/auth/signup` + `/api/remediation-runs/{id}/pr-bundle.zip` | Wrong-tenant token | `201` + `404` | Separate-tenant user created; cross-tenant bundle access denied (`Remediation run not found`). | 2026-03-02T21:40:47Z to 2026-03-02T21:40:48Z | `evidence/api/test-33-live-20260302T214032Z-66-wrong-tenant-signup.*`, `...-67-pr-bundle-download-wrong-tenant.*` |
| 10 | Local artifact extraction | `unzip` + README checks | N/A | `0` | Bundle extracted and proof fields found in README. | 2026-03-02 | `evidence/aws/test-33-live-20260302T214032Z-70-unzip-pr-bundle.*`, `...-71-bundle-file-tree.*`, `...-72-readme.txt`, `...-73-c2-line.*`, `...-74-c5-line.*` |
| 11 | Consistency check | README vs run metadata + apply context | N/A | N/A | All proof checks passed (`c2_present=true`, `c5_present=true`, `c2_within_run_window_5min=true`, `strategy_matches_create_payload=true`, `apply_context_has_init_plan_apply_steps=true`). | 2026-03-02 | `evidence/aws/test-33-live-20260302T214032Z-75-proof-consistency.json`, `...-75-proof-consistency.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/pr-bundles` (no auth) | Deterministic no-auth route behavior without exposing API data | Route returned `200` app shell; API bundle endpoint remained token/tenant protected (`200/401/404` matrix above). | `evidence/ui/test-33-live-20260302T214032Z-ui-01-pr-bundles-route-no-auth.*` |

## Assertions

- Positive path: PASS. Fresh non-root PR-only run was created and completed `success`; authorized bundle download returned `200`.
- Negative path: PASS. No-auth bundle download returned `401`; wrong-tenant bundle download returned `404`.
- Auth boundary: PASS. ZIP remains tenant-scoped and token-protected.
- Contract shape: PASS. Run detail and execution payloads include expected terminal-state fields.
- C2/C5 completeness: PASS.
  - C2 present (`terraform_plan_timestamp_utc: 2026-03-02T21:40:44+00:00`).
  - C5 present (`preserved_configuration_statement: The generated IaC is scoped...`).
- Metadata/apply-context consistency: PASS (`c2_within_run_window_5min=true`, strategy match true, apply commands present).

## Tracker Updates

- Primary tracker section/row:
  - Section 4 row #12 (Test 33 C2) -> ✅ FIXED (revalidated)
  - Section 4 row #13 (Test 33 C5) -> ✅ FIXED (revalidated)
- Section 8 checkbox impact:
  - `T33` Terraform plan timestamp checkbox remains checked
  - `T33` preservation statement checkbox remains checked
- Section 9 changelog impact:
  - Added Wave 8 Test 33 rerun entry with canonical prefix `test-33-live-20260302T214032Z`.

## Notes

- Canonical assertion prefix is `test-33-live-20260302T214032Z-*`.
- This run used current signup contract fields for wrong-tenant boundary validation (`name`, `company_name`).
