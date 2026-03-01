# Test 23

- Wave: 07
- Focus: Adversarial S3 blast-radius validation
- Status: PARTIAL
- Severity (if issue): 🟡 MEDIUM

## Preconditions

- Identity: Tenant A admin `maromaher54@gmail.com` authenticated via fresh `POST /api/auth/login` (`200`) and revalidated with `GET /api/auth/me` (`200`).
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`).
- AWS account: `029037611564`.
- Region(s): `eu-north-1`.
- Runtime under test:
  - Runtime stack: `security-autopilot-saas-serverless-runtime`
  - Last updated: `2026-03-01T03:19:34.761000+00:00`
  - API image: `.../security-autopilot-dev-saas-api:20260301T031756Z`
  - Worker image: `.../security-autopilot-dev-saas-worker:20260301T031756Z`
- Prerequisite resources/IDs:
  - A1 bucket: `arch1-bucket-website-a1-029037611564-eu-north-1`
  - B1 bucket: `arch1-bucket-evidence-b1-029037611564-eu-north-1`
  - A1 action ID: `232870db-8f7d-49ee-8361-8ad1bd79eff2`
  - B1 action ID: `26403d52-eff4-47ce-ab52-49bd237e72f5`
  - Target remediation run: `335f0b32-772a-4cf1-a9e6-cc3c2ecefe67` (B1 standard strategy)

## Steps Executed

1. Confirmed adversarial baseline state for A1/B1 using AWS CLI.
2. Patched test-account ReadRole policy to include `s3:GetBucketWebsite` so runtime blast-radius probes can collect website evidence (previous blocker was `AccessDenied`).
3. Re-applied/confirmed adversarial S3 setup:
   - A1: website enabled + public object-read policy + bucket-level PAB disabled.
   - B1: no website configuration + non-public policy + bucket-level PAB disabled.
4. Triggered ingest + actions compute and verified A1/B1 `s3_bucket_block_public_access` actions are `open`.
5. Pulled remediation options:
   - A1 remained `warn` (dependency review required).
   - B1 became `pass` (no direct public-access dependency detected).
6. Created PR-mode remediation run for B1 standard strategy; polled run to `success`.
7. Downloaded authorized PR bundle ZIP for run `335f0b32-772a-4cf1-a9e6-cc3c2ecefe67`.
8. Executed bundle Terraform in test AWS (`init/plan/apply` all success).
9. Triggered post-apply ingest/compute/reconcile refresh APIs.
10. Polled near-real-time updates for 15 minutes (30 polls) and verified target closure state plus unaffected-resource blast-radius safety.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | AWS CLI | `aws sts get-caller-identity` | N/A | `0` | Caller identity account is `029037611564` (`arn:aws:iam::029037611564:user/AutoPilotAdmin`). | 2026-03-01T03:39:53Z | `evidence/api/test-23-closure-20260301T033953Z-00-aws-sts-caller-identity.*` |
| 2 | AWS CLI | `aws iam get-policy-version` + `create-policy-version` | ReadRole policy patch | `0 / 0` | Added `s3:GetBucketWebsite` to `SecurityAutopilotReadRolePolicy` (`S3AccessPathReadChecks`) and verified new default version. | 2026-03-01T03:40:15Z | `...-09-aws-readrole-policy-pre.*`, `...-11-aws-readrole-policy-create-version.*`, `...-13-aws-readrole-policy-version-post.*` |
| 3 | AWS CLI | A1/B1 baseline confirm (`get-bucket-website`, `get-bucket-policy-status`) | Bucket-specific | `0/254/0/0` | A1 website config present + `IsPublic=true`; B1 website absent (`NoSuchWebsiteConfiguration`) + `IsPublic=false`. | 2026-03-01T03:40:22Z to 2026-03-01T03:40:25Z | `...-21-*.json`, `...-22-*.json`, `...-23-*.json`, `...-24-*.json` |
| 4 | POST | `https://api.valensjewelry.com/api/auth/login` | `{"email":"maromaher54@gmail.com","password":"***"}` | `200` | Fresh admin bearer token issued. | 2026-03-01T03:40:27Z | `...-30-login-admin.*` |
| 5 | POST + POST | `/api/aws/accounts/029037611564/ingest`, `/api/actions/compute` | `{"regions":["eu-north-1"]}`, `{"account_id":"029037611564","region":"eu-north-1"}` | `202 / 202` | Ingest and compute queued for account/region scope. | 2026-03-01T03:40:33Z / 2026-03-01T03:40:34Z | `...-33-trigger-ingest.*`, `...-34-trigger-actions-compute.*` |
| 6 | GET | `/api/actions?...action_type=s3_bucket_block_public_access&status=open` | Bearer token | `200` | A1 + B1 open S3.2 actions discovered and selected. | 2026-03-01T03:40:34Z | `...-35-actions-open-s3-bpa-poll-1.*`, `...-36-selected-action-ids.*` |
| 7 | GET | `/api/actions/{a1|b1}/remediation-options` | Bearer token | `200 / 200` | A1 strategy checks `warn`; B1 standard/migrate checks now `pass` (no `access_path_evidence_unavailable` fail). | 2026-03-01T03:40:36Z / 2026-03-01T03:40:37Z | `...-39-remediation-options-a1.*`, `...-40-remediation-options-b1.*` |
| 8 | POST | `/api/remediation-runs` | `{"action_id":"26403d52-...","mode":"pr_only","strategy_id":"s3_bucket_block_public_access_standard"}` | `201` | Remediation run created for B1 target action. | 2026-03-01T03:40:38Z | `...-43-create-run-target-pr.*`, `...-45-remediation-run-id.txt` |
| 9 | GET | `/api/remediation-runs/{run_id}` | Bearer token | `200` | Run reached `success`; `risk_snapshot` recommendation `safe_to_proceed`; PR bundle files embedded in artifacts. | 2026-03-01T03:41:17Z | `...-48-run-detail-final.json` |
| 10 | GET | `/api/remediation-runs/{run_id}/pr-bundle.zip` | Bearer token | `200` | Authorized PR bundle download successful. | 2026-03-01T03:41:23Z | `...-50-pr-bundle-download-authorized.*`, `evidence/aws/test-23-closure-20260301T033953Z-50-pr-bundle.zip` |
| 11 | Terraform | Bundle apply path (`init`, `plan`, `apply`) | Bundle Terraform files | `0 / 0 / 0` | Apply succeeded: `aws_s3_bucket_public_access_block.security_autopilot` created for B1 bucket. | 2026-03-01T03:44:11Z | `evidence/aws/test-23-closure-20260301T033953Z-54-terraform-init.*`, `...-55-terraform-plan.*`, `...-56-terraform-apply.*` |
| 12 | AWS CLI | Post-apply S3 state checks | Bucket-specific | `0` | Target B1 now has PAB all `true` + `IsPublic=false`; unaffected A1 remains PAB all `false` + `IsPublic=true` + website config present. | 2026-03-01T03:44:11Z to 2026-03-01T03:44:16Z | `...-57-*.json` to `...-62-*.json` |
| 13 | POST + POST + POST | `/api/aws/accounts/{id}/ingest`, `/api/actions/compute`, `/api/actions/reconcile` | account/region payloads | `202 / 202 / 202` | Post-apply refresh calls accepted. | 2026-03-01T03:44:17Z to 2026-03-01T03:44:18Z | `...-63-*.json`, `...-64-*.json`, `...-65-*.json` |
| 14 | Poll loop (30) | action detail + open/resolved action lists | Bearer token | `200` series | After 15-minute poll window: target B1 action still `open`; unresolved list still contains B1; resolved list contains `0` S3.2 items. | 2026-03-01T03:59:47Z to 2026-03-01T03:59:49Z | `...-70-target-action-detail-poll-30.*`, `...-72-actions-open-s3-bpa-poll-30.*`, `...-73-actions-resolved-s3-bpa-poll-30.*` |
| 15 | GET | `/api/findings?control_id=S3.2&status=NEW...limit=200` and `/api/findings?control_id=S3.2...limit=200` | Bearer token | `200 / 200` | Target B1 finding still present in `NEW` set after apply/refresh (`target_new=1`). | 2026-03-01T04:02:34Z / 2026-03-01T04:02:35Z | `...-83-findings-s3-2-open-final-fixed.*`, `...-84-findings-s3-2-all-final-fixed.*` |
| 16 | AWS CLI | Runtime version proof (`describe-stacks`) | Runtime stack query | `0` | Confirms run executed against stack last updated `2026-03-01T03:19:34.761000+00:00`, API/worker image tag `20260301T031756Z`. | 2026-03-01T04:03:52Z | `...-85-runtime-stack-version.*` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/actions` (no auth) | No-auth access should not expose actions UI data | `307` redirect with `Location: /findings`; no unauthenticated action data served | N/A (`evidence/ui/test-23-closure-20260301T033953Z-ui-01-actions-route-no-auth.*`) |

## Assertions

- Positive path: PARTIAL. Full PR-run lifecycle succeeded for B1 (create `201`, run `success`, bundle `200`, Terraform `init/plan/apply` all `0`).
- Negative path: PASS. No-auth remediation-options probe still denies (`401`); UI route no-auth probe redirects (`307`).
- Auth boundary: PASS. No unauthorized success observed for tested API/UI boundary probes.
- Contract shape: PASS for blast-radius differentiation. A1 remains `warn`; B1 now returns `pass` for `s3_public_access_dependency` (no access-path fail blocker).
- Idempotency/retry: PASS (run lifecycle stable and deterministic during poll loop; no duplicate-run instability observed in this flow).
- Auditability: PASS. Complete API/UI/AWS artifacts captured for preconditions, run/apply chain, refresh calls, and terminal poll window.
- Closure result: FAIL within timeout window. Despite successful apply and refresh triggers, target B1 action/finding remained `open/NEW` after 15 minutes.
- Blast-radius result: PASS. Target B1 security state changed as intended (PAB all `true`), while unaffected A1 state remained unchanged (website + public policy posture preserved).

## Tracker Updates

- Primary tracker section/row: Section 5 Test 23 row.
- Tracker section hint: Section 5 and Section 4.
- Section 8 checkbox impact: None.
- Section 9 changelog update needed: Yes.

## Notes

- Canonical closure evidence prefix: `test-23-closure-20260301T033953Z-*`.
- No product code changes were made.
- Environment-side change applied for testability: ReadRole policy gained `s3:GetBucketWebsite`, which removed `access_path_evidence_unavailable` and enabled A1/B1 blast-radius differentiation in remediation-options.
- Final outcome is still **PARTIAL (🟡 MEDIUM)** because remediation closure did not propagate to target finding/action within the required 15-minute window.
