# Test 28

- Wave: 07
- Focus: Adversarial IAM inline+managed policy preservation checks
- Status: BLOCKED
- Severity (if issue): 🟠 HIGH

## Preconditions

- Identity: Tenant A admin `maromaher54@gmail.com` authenticated via `POST /api/auth/login` (`200`) and revalidated with `GET /api/auth/me` (`200`).
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`).
- AWS account: `029037611564`.
- Region(s): `eu-north-1`.
- Runtime under test:
  - Runtime stack: `security-autopilot-saas-serverless-runtime`
  - Last updated: `2026-03-01T20:57:44.397000+00:00`
  - API image: `.../security-autopilot-dev-saas-api:20260301T205539Z`
  - Worker image: `.../security-autopilot-dev-saas-worker:20260301T205539Z`
- Prerequisite resources/IDs:
  - B3 role: `arch2_mixed_policy_role_b3`
  - B3 inline policy: `arch2_mixed_policy_role_b3-inline-wildcard`
  - B3 required managed policy: `arn:aws:iam::aws:policy/ReadOnlyAccess`
  - Target action ID: `c8201c18-5054-42ee-99c6-815ea082f2c9`
  - Target finding ID: `fe935ab6-1117-4475-a5fb-edbdf8cc8a4b`
  - Target remediation run: `5444d836-037c-40be-979e-d5f2d28d8689`

## Steps Executed

1. Created/confirmed adversarial IAM B3 inline+managed state for `arch2_mixed_policy_role_b3`: trust policy reset to EC2 assume-role, inline wildcard policy enforced, and required managed policy attachment (`ReadOnlyAccess`) preserved.
2. Verified related IAM.4 action/finding state appears OPEN/NEW in live SaaS.
3. Created remediation run in PR mode for the target IAM.4 action (`risk_acknowledged=true`).
4. Downloaded generated PR bundle and captured authorized/no-auth access evidence.
5. Executed downloaded remediation files in AWS test account (`terraform init/plan/show/apply`) and captured outputs.
6. Triggered post-apply refresh via ingest/compute/reconcile APIs.
7. Polled refresh/status endpoints until processing finished.
8. Verified target action/finding remained `open`/`NEW` after refresh.
9. Verified policy preservation pass: required B3 inline+managed permissions remained unchanged pre/post apply.
10. Saved complete API/UI/AWS evidence under canonical prefix.
11. Updated Wave 7 tracker state and this test file from observed evidence only.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | AWS CLI | `sts get-caller-identity` + B3 IAM pre/reset/confirm chain | N/A | `0` series | B3 adversarial inline+managed state confirmed (`adversarial_state_confirmed=true`). | 2026-03-01T21:55:26Z to 2026-03-01T21:55:49Z | `evidence/api/test-28-closure-20260301T215524Z-01-*.json` to `...-16-adversarial-state-summary.json` |
| 2 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***"}` | `200` | Fresh admin bearer token issued. | 2026-03-01T21:55:50Z | `...-30-login-admin.*` |
| 3 | POST + POST + POST | `/api/aws/accounts/029037611564/ingest`, `/api/actions/compute`, `/api/actions/reconcile` | account/region payloads | `202 / 202 / 202` | Pre-refresh ingest/compute/reconcile accepted. | 2026-03-01T21:55:52Z to 2026-03-01T21:55:53Z | `...-33-trigger-ingest-pre.*`, `...-34-trigger-actions-compute-pre.*`, `...-35-trigger-actions-reconcile-pre.*` |
| 4 | GET + GET | `/api/actions?...control_id=IAM.4&status=open`, `/api/findings?...control_id=IAM.4&status=NEW` | Bearer token | `200 / 200` | Target action/finding confirmed open/new pre-run. | 2026-03-01T21:55:53Z to 2026-03-01T21:55:54Z | `...-36-actions-open-iam4-poll-1.*`, `...-37-target-action-id.txt`, `...-39-findings-new-iam4-pre.*`, `...-40-target-finding-id.txt` |
| 5 | GET | `/api/actions/{action_id}/remediation-options` | Bearer token / no-auth | `200 / 401` | `mode_options=["pr_only"]`; root-credential warning strategies returned; no-auth denied. | 2026-03-01T21:55:54Z | `...-42-remediation-options-target.*`, `...-43-remediation-options-target-noauth.*`, `...-44-target-strategy-id.txt` |
| 6 | POST | `/api/remediation-runs` | no-auth/no-ack/ack payloads | `401 / 400 / 201` | No-auth denied; no-ack rejected; ack run created (`run_id=5444d836-037c-40be-979e-d5f2d28d8689`). | 2026-03-01T21:55:54Z to 2026-03-01T21:55:55Z | `...-45-create-run-pr-noauth.*`, `...-46-create-run-pr-noack.*`, `...-47-create-run-pr-ack.*`, `...-48-remediation-run-id.txt` |
| 7 | GET | `/api/remediation-runs/{id}` + `/execution` (poll) | Bearer token | `200` | Run reached terminal `success`; execution reached `completed` with full progress. | 2026-03-01T21:55:55Z to 2026-03-01T21:55:56Z | `...-49-run-detail-poll-*.json`, `...-50-run-execution-poll-*.json`, `...-51-run-detail-final.json`, `...-53-run-final-status.txt` |
| 8 | GET | `/api/remediation-runs/{id}/pr-bundle.zip` | Bearer token / no-auth | `200 / 401` | Authorized bundle downloaded; no-auth download denied. | 2026-03-01T21:55:57Z | `...-54-pr-bundle-download-authorized.*`, `evidence/aws/test-28-closure-20260301T215524Z-54-pr-bundle.zip`, `...-55-pr-bundle-download-noauth.*` |
| 9 | Terraform | Bundle execution (`init`, `plan`, `show`, `apply`) | Bundle Terraform files | `0 / 0 / 0 / 1` | Apply failed at explicit root-principal gate (`ERROR: root credentials are required to disable root access keys.`). | 2026-03-01T21:55:57Z to 2026-03-01T21:57:51Z | `evidence/aws/test-28-closure-20260301T215524Z-70-terraform-init.*` to `...-73-terraform-apply.*` |
| 10 | AWS CLI + summary | B3 policy-preservation checks pre/post apply | N/A | `0` series | Trust/inline/managed policy sets unchanged; required managed policy preserved (`required_safe_permissions_unchanged=true`). | 2026-03-01T21:56:07Z to 2026-03-01T21:57:51Z | `...-59-*.json` to `...-77-*.json`, `evidence/aws/test-28-closure-20260301T215524Z-78-policy-preservation-summary.json` |
| 11 | POST + POST + POST | `/api/aws/accounts/{id}/ingest`, `/api/actions/compute`, `/api/actions/reconcile` | account/region payloads | `202 / 202 / 202` | Post-apply refresh triggers accepted. | 2026-03-01T21:57:52Z | `...-91-trigger-ingest-post-apply.*`, `...-92-trigger-actions-compute-post-apply.*`, `...-93-trigger-actions-reconcile-post-apply.*` |
| 12 | Poll loop (2) | ingest progress + target action/finding status queries | Bearer token | `200` series | Refresh reached `completed` by poll-2; target remained unresolved (`action=open`, `finding=NEW`). | 2026-03-01T21:57:53Z to 2026-03-01T21:58:27Z | `...-94-ingest-progress-poll-*.json`, `...-95-*.json`, `...-96-*.json`, `...-97-*.json`, `...-98-*.json`, `...-99-*.json` |
| 13 | GET (final) | target action/finding + open/resolved lists | Bearer token | `200` series | Final state remained `open/NEW`; target stayed in open/new lists and absent from resolved lists. | 2026-03-01T21:58:28Z | `...-102-target-action-detail-final.json`, `...-103-actions-open-iam4-final.json`, `...-104-actions-resolved-iam4-final.json`, `...-105-findings-new-iam4-final.json`, `...-106-findings-resolved-iam4-final.json`, `...-107-target-finding-detail-final.*` |
| 14 | AWS CLI | Runtime stack version proof | Runtime stack query | `0` | Runtime stack confirms image tag `20260301T205539Z` for API/worker; Lambda inventory query returned no direct runtime function-name matches. | 2026-03-01T21:58:28Z to 2026-03-01T21:59:28Z | `...-108-runtime-stack-version.*`, `...-109-lambda-api-version.*`, `...-110-runtime-lambda-function-inventory.*`, `...-111-summary.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/actions` (no auth) | No-auth user must not access actions UI data | `307` redirect; no unauthenticated actions data served | `evidence/ui/test-28-closure-20260301T215524Z-ui-01-actions-route-no-auth.*` |

## Assertions

- Positive path: PARTIAL. SaaS run creation/execution and PR-bundle generation path succeeded (`run success`, bundle `200`), and Terraform `init/plan/show` succeeded.
- Negative path: PASS. No-auth probes remained deny-closed (`401` for remediation-options/run-create/bundle download; UI route redirect `307`).
- Auth boundary: PASS. Unauthorized API/UI access remained blocked.
- Contract shape: PASS. Strategy contract clearly marks manual high-risk root-required path with required risk acknowledgement.
- Idempotency/retry: PASS. Refresh endpoints accepted retries (`202`) and ingest refresh reached terminal `completed`.
- Auditability: PASS. Full API/UI/AWS evidence chain captured for adversarial setup, run lifecycle, bundle execution, refresh polling, and final state.
- Closure result: BLOCKED. Apply failed due root-principal requirement (`terraform apply rc=1`), and target action/finding stayed `open`/`NEW` after refresh completion.
- Policy-preservation result: PASS. B3 inline policy name/document and managed policy attachments remained unchanged (`required_safe_permissions_unchanged=true`).

## Tracker Updates

- Primary tracker section/row: Section 5 Test 28 row.
- Tracker section hint: Section 5 plus related open root-gate references in Sections 3/4/6.
- Section 8 checkbox impact: None.
- Section 9 changelog update needed: Yes.

## Notes

- Canonical evidence prefix: `test-28-closure-20260301T215524Z-*`.
- No product code changes were made.
- Evidence-only result: closure remains blocked by root-credential execution gate, while inline+managed policy preservation passed.
