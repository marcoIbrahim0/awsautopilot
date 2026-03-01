# Test 27

- Wave: 07
- Focus: Adversarial mixed SG rule preservation checks
- Status: PASS
- Severity (if issue): N/A

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
  - VPC: `arch1_vpc_main` (`vpc-049294166c1c2fbd4`)
  - Target SG (B2): `arch1_sg_app_b2` (`sg-0124289e9646c8683`)
  - Preserved source SG for PostgreSQL rule: `sg-02813afb4b1337ee4`
  - Target action ID: `9c31f438-1ade-4cc7-91c8-b959870a615b`
  - Target finding ID: `ae59b887-2032-445a-a357-a5feeb25bca5`
  - Target remediation run: `cf13482a-b5f6-4a98-bf06-9cc455c01991`

## Steps Executed

1. Created/confirmed adversarial B2 SG state in AWS for `arch1_sg_app_b2`: legitimate rules (`443` from `10.0.0.0/16`, `8080` from `203.0.113.10/32`, `5432` from SG source) plus permissive `22` from `0.0.0.0/0`.
2. Verified the related EC2.53 action/finding appeared OPEN/NEW in live SaaS for target SG resource ARN.
3. Created remediation run in PR mode for the target action/group.
4. Downloaded the generated PR bundle and saved authorized/no-auth evidence.
5. Executed downloaded remediation Terraform files in AWS test account and saved init/plan/show/apply output.
6. Triggered post-apply refresh using ingest/compute/reconcile APIs.
7. Polled ingest/action/finding status endpoints until refresh processing finished.
8. Verified target action/finding reached resolved/RESOLVED.
9. Verified mixed-rule preservation: benign SG rules remained unchanged while public SSH was removed.
10. Saved complete API/UI/AWS evidence and updated docs/tracker records.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | AWS CLI | `aws sts get-caller-identity` + VPC/SG lookups | N/A | `0` series | Confirmed caller account `029037611564`; resolved `vpc-049294166c1c2fbd4` and `sg-0124289e9646c8683`. | 2026-03-01T21:25:35Z to 2026-03-01T21:25:37Z | `evidence/api/test-27-closure-20260301T212534Z-01-aws-sts-caller-identity.*`, `...-02-aws-vpc-main-lookup.*`, `...-04-aws-b2-sg-lookup.*`, `...-05-b2-sg-id.txt` |
| 2 | AWS CLI + summary | B2 SG adversarial-state confirm/reset | N/A | `0` series | Confirmed mixed-rule adversarial state (`adversarial_state_confirmed=true`) with public SSH + legitimate 443/8080/5432 rules present. | 2026-03-01T21:25:39Z to 2026-03-01T21:25:40Z | `...-06-aws-b2-sg-pre.*`, `...-07-b2-public-ssh-reset-action.txt`, `...-08-aws-b2-sg-confirm.*`, `...-09-adversarial-state-summary.json` |
| 3 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***"}` | `200` | Fresh admin bearer token issued. | 2026-03-01T21:25:42Z | `...-20-login-admin.*` |
| 4 | POST + POST + POST | `/api/aws/accounts/029037611564/ingest`, `/api/actions/compute`, `/api/actions/reconcile` | account/region payloads | `202 / 202 / 202` | Pre-refresh ingest/compute/reconcile accepted. | 2026-03-01T21:25:44Z to 2026-03-01T21:25:45Z | `...-24-trigger-ingest-pre.*`, `...-25-trigger-actions-compute-pre.*`, `...-26-trigger-actions-reconcile-pre.*` |
| 5 | GET + GET | `/api/actions?...control_id=EC2.53...status=open`, `/api/findings?...control_id=EC2.53&status=NEW` | Bearer token | `200 / 200` | Target action found OPEN on poll-1; target finding found NEW for same resource ARN. | 2026-03-01T21:25:46Z to 2026-03-01T21:25:47Z | `...-31-actions-open-ec2-53-poll-1.*`, `...-39-target-action-id.txt`, `...-39c-open-verified.txt`, `...-42-findings-new-ec2-53-pre.*`, `...-43-target-finding-id.txt` |
| 6 | GET | `/api/actions/{action_id}/remediation-options` | Bearer token | `200` | Contract returned `mode_options=["pr_only"]` with `strategies=[]` (no strategy required). | 2026-03-01T21:25:47Z | `...-44-remediation-options-target.*`, `...-45-target-strategy-id.txt` |
| 7 | POST | `/api/remediation-runs` | `{"action_id":"9c31f438-...","mode":"pr_only"}` | `201` | PR remediation run created (`run_id=cf13482a-b5f6-4a98-bf06-9cc455c01991`). | 2026-03-01T21:25:48Z | `...-46-create-run-target-pr-noack.*`, `...-48-remediation-run-id.txt` |
| 8 | GET | `/api/remediation-runs/{run_id}` + `/execution` | Bearer token | `200` | Run reached `success`; execution endpoint shows `current_step=completed`, `progress_percent=100`. | 2026-03-01T21:25:54Z to 2026-03-01T21:25:55Z | `...-49-run-detail-poll-*.json`, `...-49c-run-final-status.txt`, `...-50-run-execution-final.*` |
| 9 | GET | `/api/remediation-runs/{run_id}/pr-bundle.zip` | Bearer token / no-auth | `200 / 401` | Authorized bundle download succeeded; no-auth download denied. | 2026-03-01T21:25:55Z | `...-60-pr-bundle-download-authorized.*`, `evidence/aws/test-27-closure-20260301T212534Z-60-pr-bundle.zip`, `...-61-pr-bundle-download-no-auth.*` |
| 10 | Terraform | Bundle execution (`init`, `plan`, `show`, `apply`) | Bundle Terraform files | `0 / 0 / 0 / 0` | Terraform apply succeeded end-to-end. | 2026-03-01T21:25:58Z to 2026-03-01T21:28:57Z | `evidence/aws/test-27-closure-20260301T212534Z-70-terraform-init.*`, `...-71-terraform-plan.*`, `...-72-terraform-show-plan.*`, `...-73-terraform-apply.*` |
| 11 | AWS CLI + summary | Post-apply SG state + preservation check | N/A | `0` | Public SSH removed; legitimate 443/8080/5432 rules preserved including source SG parity (`preservation_pass=true`). | 2026-03-01T21:28:58Z | `...-74-aws-b2-sg-post-apply.*`, `evidence/aws/test-27-closure-20260301T212534Z-75-sg-preservation-summary.json` |
| 12 | POST + POST + POST | `/api/aws/accounts/{id}/ingest`, `/api/actions/compute`, `/api/actions/reconcile` | account/region payloads | `202 / 202 / 202` | Post-apply refresh triggers accepted. | 2026-03-01T21:28:58Z to 2026-03-01T21:28:59Z | `...-80-trigger-ingest-post-apply.*`, `...-81-trigger-actions-compute-post-apply.*`, `...-82-trigger-actions-reconcile-post-apply.*` |
| 13 | Poll loop (2) | ingest progress + target action/finding detail | Bearer token | `200` series | Ingest reached `completed` by poll-2; target action/finding resolved by poll-2 (`terminal_poll=2`). | 2026-03-01T21:29:00Z to 2026-03-01T21:29:31Z | `...-84-ingest-progress-poll-*.json`, `...-85-target-action-detail-poll-*.json`, `...-86-target-finding-detail-poll-*.json`, `...-87-terminal-poll.txt` |
| 14 | GET (final) | target action/finding + open/resolved lists | Bearer token | `200` series | Final action `resolved`; finding `RESOLVED`; target removed from open lists and present in resolved lists. | 2026-03-01T21:29:32Z to 2026-03-01T21:29:34Z | `...-90-target-action-detail-final.*`, `...-91-target-finding-detail-final.*`, `...-92-actions-open-ec2-53-final.*`, `...-93-actions-resolved-ec2-53-final.*`, `...-94-findings-new-ec2-53-final.*`, `...-95-findings-resolved-ec2-53-final.*` |
| 15 | AWS CLI | Runtime stack + Lambda image proof | N/A | `0` series | Runtime stack and Lambda image URIs confirm test ran on tag `20260301T205539Z` for API and worker. | 2026-03-01T21:29:36Z to 2026-03-01T21:30:44Z | `...-96-runtime-stack-version.*`, `...-97-lambda-api-version.*`, `...-98-lambda-worker-version.*`, `...-99-summary.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/actions` (no auth) | No-auth user must not access actions UI data | `307` redirect; no unauthenticated actions data served | `evidence/ui/test-27-closure-20260301T212534Z-ui-01-actions-route-no-auth.*` |

## Assertions

- Positive path: PASS. Full remediation chain succeeded (`run success`, bundle `200`, Terraform `0/0/0/0`, refresh complete, action/finding resolved).
- Negative path: PASS. No-auth PR-bundle download denied (`401`).
- Auth boundary: PASS. UI actions-route no-auth probe redirected (`307`) and API no-auth probe denied.
- Contract shape: PASS. Remediation options contract was valid for `pr_only` execution with no strategy ID required.
- Idempotency/retry: PASS. Refresh calls accepted (`202`) and polling converged deterministically (`terminal_poll=2`).
- Auditability: PASS. Complete API/UI/AWS artifact chain captured for setup, run, apply, refresh, and final state.
- Closure result: PASS. Target action `resolved` and target finding `RESOLVED` after post-apply refresh.
- SG-preservation result: PASS. Legitimate mixed SG rules remained unchanged while permissive SSH rule was removed.

## Tracker Updates

- Primary tracker section/row: Section 5 Test 27 row.
- Tracker section hint: Section 5 (no new Section 3/4/6 defects observed in this run).
- Section 8 checkbox impact: None.
- Section 9 changelog update needed: Yes.

## Notes

- Canonical evidence prefix: `test-27-closure-20260301T212534Z-*`.
- No product code changes were made.
- Evidence-only result: full remediation closure and SG rule preservation both passed.
