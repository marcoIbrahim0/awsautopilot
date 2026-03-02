# Test 33

- Wave: 08
- Focus: PR proof artifact completeness (C2/C5 evidence fields)
- Status: PASS
- Severity (if issue): —

## Preconditions

- Identity:
  - Tenant A admin: `maromaher54@gmail.com`
  - Wrong-tenant admin (created during run): `wave8.test33.20260302T191647Z@example.com`
- Tenant A: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`)
- AWS account: `029037611564`
- Region(s): `eu-north-1`
- Canonical evidence prefix: `test-33-live-20260302T191537Z-*`
- Selected non-root target:
  - `action_id=232870db-8f7d-49ee-8361-8ad1bd79eff2`
  - `control_id=S3.2`
  - `resource_id=arn:aws:s3:::arch1-bucket-website-a1-029037611564-eu-north-1`
  - `strategy_id=s3_bucket_block_public_access_standard`
- Remediation run id: `b9e50351-02a0-4784-a2f1-473929da696e`

## Steps Executed

1. Logged in as Valens admin and captured tenant/account/action context.
2. Selected a fresh non-root `pr_only` target in preferred control family (`S3.2`) and captured remediation-options payload.
3. Created remediation run with selected strategy (`risk_acknowledged=true` due dependency warning) and polled run detail to terminal `success`.
4. Captured execution context (`/execution`) and downloaded PR bundle via authorized path.
5. Captured ZIP auth-boundary probes (`401` no-auth, `404` wrong-tenant).
6. Extracted bundle artifacts and validated README C2/C5 fields (`terraform_plan_timestamp_utc`, `preserved_configuration_statement`).
7. Validated proof consistency against run metadata/apply context (`c2_within_run_window_5min=true`, strategy match true, apply-step commands present).

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***REDACTED***"}` | `200` | Admin token issued. | 2026-03-02T19:15:38Z | `evidence/api/test-33-live-20260302T191537Z-01-login-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/auth/me` | Bearer admin token | `200` | Tenant resolved as `Valens`, role=`admin`. | 2026-03-02T19:15:38Z | `evidence/api/test-33-live-20260302T191537Z-02-auth-me-admin.*` |
| 3 | GET | `https://api.valensjewelry.com/api/actions?status=open&limit=200` | Bearer admin token | `200` | Open-action pool captured; selected action/strategy recorded for S3.2. | 2026-03-02T19:15:40Z | `evidence/api/test-33-live-20260302T191537Z-04-actions-open-preferred.*`, `...-05-target-selection.*` |
| 4 | GET | `https://api.valensjewelry.com/api/actions/232870db-8f7d-49ee-8361-8ad1bd79eff2/remediation-options` | Bearer admin token | `200` | PR-only strategies returned; selected `s3_bucket_block_public_access_standard`. | 2026-03-02T19:15:43Z | `evidence/api/test-33-live-20260302T191537Z-10-remediation-options-232870db-8f7d-49ee-8361-8ad1bd79eff2.*` |
| 5 | POST | `https://api.valensjewelry.com/api/remediation-runs` | `{"action_id":"232870db-...","mode":"pr_only","strategy_id":"s3_bucket_block_public_access_standard","risk_acknowledged":true}` | `201` | Run created (`id=b9e50351-02a0-4784-a2f1-473929da696e`, `status=pending`). | 2026-03-02T19:15:43Z | `evidence/api/test-33-live-20260302T191537Z-20-create-run-pr.*`, `...-21-run-id.*` |
| 6 | GET | `https://api.valensjewelry.com/api/remediation-runs/b9e50351-02a0-4784-a2f1-473929da696e` | Bearer admin token | `200` | Run reached terminal `success`; `pr_bundle` artifact present. | 2026-03-02T19:15:44Z | `evidence/api/test-33-live-20260302T191537Z-22-run-detail-poll-1.*`, `...-62-run-final-status.*` |
| 7 | GET | `https://api.valensjewelry.com/api/remediation-runs/b9e50351-02a0-4784-a2f1-473929da696e/execution` | Bearer admin token | `200` | Execution contract returned `phase=apply`, `status=success`, `current_step=completed`, `progress_percent=100`. | 2026-03-02T19:15:44Z | `evidence/api/test-33-live-20260302T191537Z-63-run-execution.*` |
| 8 | GET | `https://api.valensjewelry.com/api/remediation-runs/b9e50351-02a0-4784-a2f1-473929da696e/pr-bundle.zip` | Bearer admin token | `200` | Authorized bundle download succeeded. | 2026-03-02T19:15:45Z | `evidence/api/test-33-live-20260302T191537Z-64-pr-bundle-download-authorized.*`, `evidence/aws/test-33-live-20260302T191537Z-64-pr-bundle.zip` |
| 9 | GET | same as #8 | No auth header | `401` | Unauthenticated bundle download denied. | 2026-03-02T19:15:45Z | `evidence/api/test-33-live-20260302T191537Z-65-pr-bundle-download-no-auth.*` |
| 10 | POST + GET | `/api/auth/signup` + `/api/remediation-runs/{id}/pr-bundle.zip` | Wrong-tenant token | `201` + `404` | Separate-tenant user created; cross-tenant bundle access denied (`Remediation run not found`). | 2026-03-02T19:16:49Z | `evidence/api/test-33-live-20260302T191537Z-66-wrong-tenant-signup.*`, `...-67-pr-bundle-download-wrong-tenant.*` |
| 11 | Local artifact extraction | `unzip` + bundle inventory + README field grep | N/A | `0` | Bundle extracted (`providers.tf`, `s3_bucket_block_public_access.tf`, `README.txt`); C2/C5 lines present. | 2026-03-02T19:15:46Z | `evidence/aws/test-33-live-20260302T191537Z-70-unzip-pr-bundle.*`, `...-71-bundle-file-tree.*`, `...-72-readme.txt`, `...-73-c2-line.*`, `...-74-c5-line.*` |
| 12 | Consistency check | README vs run metadata + apply context | N/A | N/A | All proof checks passed: `c2_present=true`, `c5_present=true`, `c2_within_run_window_5min=true`, `strategy_matches_create_payload=true`, `apply_context_has_init_plan_apply_steps=true`. | 2026-03-02T19:15:46Z | `evidence/aws/test-33-live-20260302T191537Z-75-proof-consistency.json`, `...-75-proof-consistency.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/pr-bundles` (no auth) | Deterministic no-auth route behavior without exposing API data | Route returned `200` app shell; API bundle endpoint still enforced auth (`401/404` probes above). | `evidence/ui/test-33-live-20260302T191537Z-ui-01-pr-bundles-route-no-auth.*` |

## Assertions

- Positive path: PASS. Fresh non-root PR-only run was created and completed `success`; authorized bundle download returned `200`.
- Negative path: PASS. No-auth bundle download returned `401`; wrong-tenant bundle download returned `404`.
- Auth boundary: PASS. ZIP remains tenant-scoped and token-protected on live SaaS.
- Contract shape: PASS. Run detail and execution payloads include expected run/execution fields and terminal-state metadata.
- Idempotency/retry: N/A in this test scope (no duplicate create retry path executed).
- Auditability: PASS. Full artifact chain captured (selection -> create -> run success -> zip -> extract -> C2/C5 grep -> consistency JSON).
- C2/C5 completeness: PASS.
  - C2 present (`terraform_plan_timestamp_utc: 2026-03-02T19:15:43+00:00`).
  - C5 present (`preserved_configuration_statement: The generated IaC is scoped...`).
- Metadata/apply-context consistency: PASS (`c2_within_run_window_5min=true`, strategy match true, apply commands present in bundle steps).

## Tracker Updates

- Primary tracker section/row:
  - Section 4 row #12 (Test 33 C2)
  - Section 4 row #13 (Test 33 C5)
- Tracker section hint: Section 4
- Section 8 checkbox impact:
  - `T33` Terraform plan timestamp checkbox -> checked
  - `T33` preservation statement checkbox -> checked
- Section 9 changelog update needed: yes (added entry for Section 4 #12/#13 + Section 8 T33 closure)

## Notes

- Canonical assertion prefix is `test-33-live-20260302T191537Z-*`.
- Earlier non-canonical attempts (`...191323Z`, `...191349Z`, `...191410Z`) were setup/selection retries and are excluded from final assertions.
