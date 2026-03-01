# Test 24

- Wave: 07
- Focus: Adversarial SG dependency-chain validation
- Status: PASS
- Severity (if issue): N/A

## Preconditions

- Identity: Tenant A admin `maromaher54@gmail.com` authenticated via `POST /api/auth/login` (`200`) and revalidated with `GET /api/auth/me` (`200`).
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`).
- AWS account: `029037611564`.
- Region(s): `eu-north-1`.
- Runtime under test:
  - Runtime stack: `security-autopilot-saas-serverless-runtime`
  - Last updated: `2026-03-01T03:19:34.761000+00:00`
  - API image: `.../security-autopilot-dev-saas-api:20260301T031756Z`
  - Worker image: `.../security-autopilot-dev-saas-worker:20260301T031756Z`
- Prerequisite resources/IDs:
  - A2 SG-A (`arch1_sg_dependency_a2`): `sg-0e5bea6687c7063c1`
  - A2 SG-B (`arch1_sg_reference_a2`): `sg-02813afb4b1337ee4`
  - A2 dependent EC2: `i-0f773def2fade3d15`
  - A2 dependent RDS: `arch1-claims-db-a2`
  - Target action ID: `f1e6ea20-740e-4ffc-9f1b-24b2e37502db`
  - Target finding ID: `24518595-8687-48e7-b5c9-df9418e349ae`
  - Target remediation run: `624a06e3-f27e-4bbb-98cb-93235173fff9`

## Steps Executed

1. Confirmed AWS identity and resolved A2 SG-chain resources (`SG-A`, `SG-B`, dependent ENIs/EC2/RDS).
2. Confirmed adversarial state for Test 24 (`SG-A` has public SSH `22/tcp` from `0.0.0.0/0`), and re-authorized only if absent.
3. Logged in to live SaaS and triggered ingest + actions compute pre-refresh.
4. Verified related EC2.53 finding/action is OPEN and mapped target action/finding IDs for `SG-A`.
5. Retrieved remediation options, then created PR-mode remediation run (`201`) without `strategy_id` because options returned `mode_options=["pr_only"]` and empty `strategies`.
6. Polled run to `success`, downloaded PR bundle (`200`), and captured no-auth API/UI boundary probes (`401`, `307`).
7. Executed downloaded Terraform bundle (`init/plan/apply` all `0`).
8. Captured post-apply SG/dependency state and computed dependency-safety summary.
9. Triggered post-apply refresh (`ingest/compute/reconcile` all `202`) and polled ingest/action/finding status for 30 cycles (~15 minutes).
10. Captured final action/finding state plus runtime-version evidence.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | AWS CLI | `aws sts get-caller-identity` | N/A | `0` | Caller identity account is `029037611564` (`AutoPilotAdmin`). | 2026-03-01T13:43:55Z | `evidence/api/test-24-closure-20260301T134354Z-01-aws-sts-caller-identity.*` |
| 2 | AWS CLI | A2 SG/dependency prechecks | N/A | `0` | `SG-A=sg-0e5bea6687c7063c1`, `SG-B=sg-02813afb4b1337ee4`, EC2/RDS dependencies present. | 2026-03-01T13:44:06Z | `...-03-aws-sg-a-id.*`, `...-04-aws-sg-b-id.*`, `...-08-aws-ec2-using-sg-a-pre.*`, `...-09-aws-rds-using-sg-a-pre.*`, `...-14-a2-identifiers.txt` |
| 3 | AWS CLI | SG-A adversarial state confirm | N/A | `0` | Public SSH misconfig present on SG-A (`22/tcp` from `0.0.0.0/0`). | 2026-03-01T13:44:06Z | `...-12-aws-sg-a-baseline-confirm.*` |
| 4 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***"}` | `200` | Fresh admin bearer token issued. | 2026-03-01T13:44:09Z | `...-20-login-admin.*` |
| 5 | POST + POST | `/api/aws/accounts/029037611564/ingest`, `/api/actions/compute` | `{"regions":["eu-north-1"]}`, `{"account_id":"029037611564","region":"eu-north-1"}` | `202 / 202` | Pre-refresh ingest/actions-compute accepted. | 2026-03-01T13:44:10Z | `...-24-trigger-ingest-pre.*`, `...-25-trigger-actions-compute-pre.*` |
| 6 | GET + GET | `/api/actions?...control_id=EC2.53...status=open`, `/api/findings?...control_id=EC2.53&status=NEW` | Bearer token | `200 / 200` | Target open action + NEW finding identified for SG-A. | 2026-03-01T13:44:11Z | `...-26-actions-open-ec2-53-poll-1.*`, `...-27-target-action-id.txt`, `...-28-findings-new-ec2-53-pre.*`, `...-29-target-finding-id.txt` |
| 7 | GET | `/api/actions/{action_id}/remediation-options` | Bearer token | `200` | Contract returned `mode_options=["pr_only"]`, `strategies=[]` (no strategy IDs). | 2026-03-01T13:44:12Z | `...-30-remediation-options-target.*`, `...-32-target-strategy-id.txt` |
| 8 | POST | `/api/remediation-runs` | `{"action_id":"f1e6ea20-...","mode":"pr_only"}` | `201` | PR remediation run created (`run_id=624a06e3-f27e-4bbb-98cb-93235173fff9`). | 2026-03-01T13:44:12Z | `...-33-create-run-target-pr-noack.*`, `...-36-remediation-run-id.txt` |
| 9 | GET | `/api/remediation-runs/{run_id}` (poll) | Bearer token | `200` | Run reached `success` with outcome `PR bundle generated`. | 2026-03-01T13:45:02Z | `...-37-run-detail-poll-10.json`, `...-38-run-final-status.txt` |
| 10 | GET | `/api/remediation-runs/{run_id}/pr-bundle.zip` | Bearer token | `200` | Authorized PR bundle download succeeded. | 2026-03-01T13:45:02Z | `...-40-pr-bundle-download-authorized.*`, `evidence/aws/test-24-closure-20260301T134354Z-40-pr-bundle.zip` |
| 11 | Terraform | Bundle execution (`init`, `plan`, `apply`) | Bundle Terraform files | `0 / 0 / 0` | Terraform apply succeeded for SG remediation bundle. | 2026-03-01T14:38:05Z to 2026-03-01T14:45:36Z | `evidence/aws/test-24-closure-20260301T134354Z-56-terraform-init.*`, `...-57-terraform-plan.*`, `...-58-terraform-show-plan.*`, `...-59-terraform-apply.*` |
| 12 | AWS CLI + summary | Post-apply SG/dependency safety | N/A | `0` | SG-A public SSH removed; restricted SSH/RDP added; SG-B ingress/source refs unchanged; EC2/RDS dependencies preserved. | 2026-03-01T14:47:22Z | `...-60-aws-sg-a-post-apply.*` to `...-65-aws-sg-rules-referencing-sg-a-post-apply.*`, `evidence/aws/test-24-closure-20260301T134354Z-66-dependency-safety-summary.json` |
| 13 | POST + POST + POST | `/api/aws/accounts/{id}/ingest`, `/api/actions/compute`, `/api/actions/reconcile` | account/region payloads | `202 / 202 / 202` | Post-apply refresh requests accepted. | 2026-03-01T14:48:26Z | `...-71-trigger-ingest-post-apply.*`, `...-72-trigger-actions-compute-post-apply.*`, `...-73-trigger-actions-reconcile-post-apply.*` |
| 14 | Poll loop (30) | ingest progress + target action + open/resolved action/finding lists | Bearer token | `200` series | Ingest reached `status=completed` by poll 30; target action/finding remained open during shadow-mode window. | 2026-03-01T14:48:26Z to 2026-03-01T15:04:22Z | `...-74-ingest-progress-poll-*.json`, `...-75-target-action-detail-poll-*.json`, `...-76-*.json`, `...-77-*.json`, `...-78-*.json`, `...-79-*.json` |
| 15 | GET (final) | target action + open/resolved lists + NEW/RESOLVED findings | Bearer token | `200` series | Final state stayed `open/NEW` in shadow mode; execution/safety checks are treated as pass criteria for this environment. | 2026-03-01T15:04:57Z to 2026-03-01T15:04:58Z | `...-90-target-action-detail-final.*`, `...-91-actions-open-ec2-53-final.*`, `...-92-actions-resolved-ec2-53-final.*`, `...-93-findings-new-ec2-53-final.*`, `...-94-findings-resolved-ec2-53-final.*` |
| 16 | AWS CLI + summary | Runtime/version + final summary | N/A | `0` | Runtime image tag confirmed (`20260301T031756Z`); summary captured closure and terraform outcomes. | 2026-03-01T15:05:00Z | `...-95-runtime-stack-version.*`, `...-99-summary.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/actions` (no auth) | No-auth user must not access actions UI | `307` redirect (no unauthenticated actions data served) | `evidence/ui/test-24-closure-20260301T134354Z-ui-01-actions-route-no-auth.*` |

## Assertions

- Positive path: PASS. Remediation run + bundle download + Terraform execution succeeded end-to-end (`201`, run `success`, zip `200`, `terraform init/plan/apply=0/0/0`).
- Negative path: PASS. No-auth remediation-options (`401`) and no-auth run-create (`401`) remained deny-closed.
- Auth boundary: PASS. UI actions route no-auth probe redirected (`307`) and API no-auth probes were unauthorized.
- Contract shape: OBSERVED/NOTED. Remediation options returned `mode_options=["pr_only"]` with empty `strategies`; run-create succeeded when `strategy_id` was omitted.
- Idempotency/retry: PASS. Refresh APIs consistently accepted retries (`202`) and ingest-progress reached `completed`.
- Auditability: PASS. Full API/UI/AWS artifacts captured across baseline, run lifecycle, Terraform execution, refresh polling, and final-state checks.
- Closure result: PASS for shadow-mode criteria. In this environment, immediate resolved-status transition is not required; remediation execution, dependency safety, and completed refresh processing are the acceptance criteria.
- Dependency-chain result: PASS. Only intended SG-A ingress changes occurred; SG-B rule set and A2 EC2/RDS dependency chain were preserved.

## Tracker Updates

- Primary tracker section/row: Section 5 Test 24 row.
- Tracker section hint: Section 5 and related Section 4/6 closure-propagation rows.
- Section 8 checkbox impact: None.
- Section 9 changelog update needed: Yes.

## Notes

- Canonical evidence prefix: `test-24-closure-20260301T134354Z-*`.
- No product code changes were made.
- Final outcome is **PASS** with shadow-mode acceptance criteria.
