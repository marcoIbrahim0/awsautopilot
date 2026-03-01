# Test 25

- Wave: 07
- Focus: Adversarial IAM multi-principal validation
- Status: BLOCKED
- Severity (if issue): 🟠 HIGH

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
  - A3 role: `arch2_shared_compute_role_a3`
  - B3 role: `arch2_mixed_policy_role_b3`
  - Target action ID: `c8201c18-5054-42ee-99c6-815ea082f2c9`
  - Target finding IDs: `fe935ab6-1117-4475-a5fb-edbdf8cc8a4b`, `9a553808-2729-49af-9b92-118a618162f2`
  - Target remediation run: `d7325d69-35ec-4d2b-8042-72d5b36f35ad`

## Steps Executed

1. Confirmed adversarial IAM multi-principal state in AWS (A3/B3 trust/policy posture) and recorded state summary.
2. Logged in to live SaaS, triggered ingest + actions compute, and verified related IAM.4 action/finding chain is OPEN/NEW.
3. Pulled remediation options, created PR-mode remediation run with `risk_acknowledged=true`, and polled run to terminal `success`.
4. Downloaded authorized PR bundle (`200`) and captured no-auth bundle/API and UI boundary probes (`401`, `307`).
5. Executed downloaded Terraform bundle in the AWS test account (`init=0`, `plan=0`, `show=0`, `apply=1`) and saved full outputs.
6. Triggered post-apply refresh using ingest/compute/reconcile APIs (`202/202/202`).
7. Polled refresh and target status endpoints for 30 cycles (~15 minutes) until timeout.
8. Verified final action/finding state remained unresolved (`open` / `NEW`).
9. Verified principal-preservation safety (A3 trust principals and B3 managed policies unchanged pre/post apply).

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | AWS CLI | IAM A3/B3 adversarial-state checks | N/A | `0` series | A3 multi-principal trust + wildcard inline policies and B3 inline+managed posture confirmed (`adversarial_state_confirmed=true`). | 2026-03-01T15:40:46Z to 2026-03-01T15:40:57Z | `evidence/api/test-25-closure-20260301T154046Z-01-aws-a3-role-pre.*` to `...-12-adversarial-state-summary.json` |
| 2 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***"}` | `200` | Fresh admin bearer token issued. | 2026-03-01T15:40:57Z | `...-30-login-admin.*` |
| 3 | POST + POST | `/api/aws/accounts/029037611564/ingest`, `/api/actions/compute` | `{"regions":["eu-north-1"]}`, `{"account_id":"029037611564","region":"eu-north-1"}` | `202 / 202` | Pre-refresh ingest/compute accepted. | 2026-03-01T15:40:59Z | `...-34-trigger-ingest-pre.*`, `...-35-trigger-actions-compute-pre.*` |
| 4 | GET + GET | `/api/actions?...control_id=IAM.4...status=open`, `/api/findings?...control_id=IAM.4&status=NEW` | Bearer token | `200 / 200` | Target IAM.4 action and linked findings confirmed open/new. | 2026-03-01T15:41:00Z | `...-36-actions-open-iam4-poll-1.*`, `...-38-target-action-detail-open.*`, `...-39-findings-new-iam4-pre.*`, `...-40-target-finding-ids.txt` |
| 5 | GET | `/api/actions/{action_id}/remediation-options` | Bearer token | `200` | `mode_options=["pr_only"]`; strategies require root-credential runbook and risk acknowledgement. | 2026-03-01T15:41:01Z | `...-42-remediation-options-target.*` |
| 6 | POST | `/api/remediation-runs` | `{"action_id":"...","mode":"pr_only","strategy_id":"iam_root_key_disable"}` | `400` | No-ack create correctly blocked with `Risk acknowledgement required`. | 2026-03-01T15:41:01Z | `...-45-create-run-pr-noack.*` |
| 7 | POST | `/api/remediation-runs` | `{"action_id":"...","mode":"pr_only","strategy_id":"iam_root_key_disable","risk_acknowledged":true}` | `201` | PR run created (`run_id=d7325d69-35ec-4d2b-8042-72d5b36f35ad`, `manual_high_risk=true`). | 2026-03-01T15:41:07Z | `...-47-create-run-pr-ack.*`, `...-48-remediation-run-id.txt` |
| 8 | GET | `/api/remediation-runs/{run_id}` + `/execution` (poll) | Bearer token | `200` | Run reached `success`; `PR bundle generated`; execution endpoint reached `current_step=completed`, `progress_percent=100`. | 2026-03-01T15:41:57Z | `...-51-run-detail-final.json`, `...-52-run-execution-final.json`, `...-53-run-final-status.txt` |
| 9 | GET | `/api/remediation-runs/{run_id}/pr-bundle.zip` | Bearer token | `200` | Authorized bundle downloaded. | 2026-03-01T15:42:02Z | `...-54-pr-bundle-download-authorized.*`, `evidence/aws/test-25-closure-20260301T154046Z-54-pr-bundle.zip` |
| 10 | Terraform | Bundle execution (`init`, `plan`, `show`, `apply`) | Bundle Terraform files | `0 / 0 / 0 / 1` | Apply failed with explicit root-credential gate (`ERROR: root credentials are required to disable root access keys.`). | 2026-03-01T15:42:08Z to 2026-03-01T15:44:49Z | `evidence/aws/test-25-closure-20260301T154046Z-70-terraform-init.*`, `...-71-terraform-plan.*`, `...-72-terraform-show.*`, `...-73-terraform-apply.*` |
| 11 | AWS CLI + summary | Principal-preservation checks pre/post apply | N/A | `0` series | A3 principals unchanged; A3 inline policy names unchanged; B3 principals and managed policy attachments unchanged (`principal_preservation_pass=true`). | 2026-03-01T15:42:03Z to 2026-03-01T15:44:52Z | `...-63-*.json` to `...-77-*.json`, `evidence/aws/test-25-closure-20260301T154046Z-78-principal-preservation-summary.json` |
| 12 | POST + POST + POST | `/api/aws/accounts/{id}/ingest`, `/api/actions/compute`, `/api/actions/reconcile` | account/region payloads | `202 / 202 / 202` | Post-apply refresh triggers accepted. | 2026-03-01T15:46:09Z | `...-91-trigger-ingest-post-apply.*`, `...-92-trigger-actions-compute-post-apply.*`, `...-93-trigger-actions-reconcile-post-apply.*` |
| 13 | Poll loop (30) | ingest progress + target action + open/resolved action/finding lists | Bearer token | `200` series | Ingest progressed from `queued` (`9%`) to `completed` (`100%`), but target action/finding remained unresolved through timeout. | 2026-03-01T15:46:09Z to 2026-03-01T16:01:34Z | `...-94-ingest-progress-poll-*.json`, `...-95-*.json`, `...-96-*.json`, `...-97-*.json`, `...-98-*.json`, `...-99-*.json` |
| 14 | GET (final) | target action/open/resolved lists + NEW/RESOLVED findings | Bearer token | `200` series | Final state: action still `open` (open-list contains target), resolved-list empty; both linked findings still in `NEW`, none in `RESOLVED`. | 2026-03-01T16:01:35Z | `...-110-target-action-detail-final.*`, `...-111-actions-open-iam4-final.*`, `...-112-actions-resolved-iam4-final.*`, `...-113-findings-new-iam4-final.*`, `...-114-findings-resolved-iam4-final.*` |
| 15 | AWS CLI | Runtime version proof (`describe-stacks`) | Runtime stack query | `0` | Confirms run executed against runtime images tag `20260301T031756Z`. | 2026-03-01T16:01:37Z | `...-115-runtime-stack-version.*`, `...-99-summary.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/actions` (no auth) | No-auth user must not access actions UI data | `307` redirect to `/findings`; no unauthenticated actions data served | `evidence/ui/test-25-closure-20260301T154046Z-ui-01-actions-route-no-auth.*` |

## Assertions

- Positive path: PARTIAL. SaaS-side remediation flow completed (`run success`, bundle download `200`), and Terraform `init/plan/show` succeeded.
- Negative path: PASS. No-auth probes remained deny-closed (`401` for remediation-options and bundle download, `307` UI redirect).
- Auth boundary: PASS. Unauthorized API/UI access remained blocked.
- Contract shape: PASS. Strategy contract explicitly flagged high-risk/manual root workflow and required `risk_acknowledged=true`.
- Idempotency/retry: PASS. Refresh endpoints accepted retries and ingest progress reached deterministic completion (`100%`).
- Auditability: PASS. Full AWS/API/UI evidence captured for preconditions, run lifecycle, bundle execution, refresh polling, and final state.
- Closure result: FAIL/BLOCKED. Target action/finding stayed `open/NEW` after full poll window; apply step failed under non-root credentials (`terraform apply rc=1`) due explicit root-principal gate.
- Principal-preservation result: PASS. A3/B3 valid principals and managed-policy attachments remained intact before/after remediation attempt (`principal_preservation_pass=true`).

## Tracker Updates

- Primary tracker section/row: Section 5 Test 25 row.
- Tracker section hint: Section 5 and related Section 3/4/6 updates for unresolved IAM.4 closure under root-credential gate.
- Section 8 checkbox impact: None.
- Section 9 changelog update needed: Yes.

## Notes

- Canonical evidence prefix: `test-25-closure-20260301T154046Z-*`.
- No product code changes were made.
- This run is evidence-only and shows remediation execution is gated by root credentials for IAM.4; full closure cannot be confirmed without root-principal apply.
