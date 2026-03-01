# Test 26

- Wave: 07
- Focus: Adversarial complex S3 policy preservation checks
- Status: PARTIAL
- Severity (if issue): 🟡 MEDIUM

## Preconditions

- Identity: Tenant A admin `maromaher54@gmail.com` authenticated via `POST /api/auth/login` (`200`) and `GET /api/auth/me` (`200`).
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`).
- AWS account: `029037611564`.
- Region(s): `eu-north-1`.
- Runtime under test:
  - Runtime stack: `security-autopilot-saas-serverless-runtime`
  - Last updated: `2026-03-01T19:36:52.274000+00:00`
  - API image: `.../security-autopilot-dev-saas-api:20260301T193511Z`
  - Worker image: `.../security-autopilot-dev-saas-worker:20260301T193511Z`
- Target resources:
  - Bucket: `arch1-bucket-evidence-b1-029037611564-eu-north-1`
  - Target action ID: `26403d52-eff4-47ce-ab52-49bd237e72f5`
  - Target finding ID (primary): `280fd5e2-6075-490f-913d-0ef52315a518`
  - Test run ID: `0bd646aa-911c-4acd-b898-012d76e03ec8`

## Steps Executed

1. Reconfirmed adversarial complex S3 policy + open PAB state on B1.
2. Triggered pre-run ingest/compute/reconcile refresh.
3. Queried target in OPEN S3.2 actions; target was not returned in open set.
4. Queried target in RESOLVED S3.2 actions (fallback) and continued with the same target action ID.
5. Created PR-mode remediation run for the target action and polled to terminal status.
6. Downloaded generated PR bundle and captured no-auth boundary check.
7. Executed downloaded Terraform (`init/plan/show/apply`) against AWS account.
8. Triggered post-apply ingest/compute/reconcile and polled refresh/status endpoints.
9. Captured final action/finding states.
10. Compared pre/post bucket policy and PAB state with both legacy strict and delta-aware checks.

## API/AWS Evidence

| # | Check | Expected | Observed | Artifact Path |
|---|---|---|---|---|
| 1 | Adversarial state present | Complex policy + PAB all false | Confirmed (`statement_count=4`, root + `PutObject` + `aws:SourceVpc`, PAB all false) | `evidence/api/test-26-closure-20260301T193804Z-12-adversarial-state-summary.json` |
| 2 | Auth + scope | Admin auth succeeds | `POST /api/auth/login=200`, `GET /api/auth/me=200`, accounts list `200` | `...-30-login-admin.*`, `...-31-auth-me-admin.*`, `...-32-accounts-list.*` |
| 3 | Target visibility pre-run | Target should be discoverable for test flow | OPEN query returned 24 items but did not include target; RESOLVED fallback returned target action ID (same result after pre-run reconcile trigger) | `...-36-actions-open-s3-2-poll-12.json`, `...-36-actions-resolved-s3-2-fallback.json`, `...-37-target-action-id.txt`, `...-35b-trigger-actions-reconcile-pre.*` |
| 4 | Target finding pre-run | Target finding should be visible by status query path | `status=NEW` query did not include target finding | `...-39-findings-new-s3-2-pre.json`, `...-40-target-finding-id-primary.txt` |
| 5 | Remediation options | `pr_only` strategies available, no-auth denied | Auth `200`, no-auth `401`; selected strategy `s3_migrate_cloudfront_oac_private` | `...-42-remediation-options-target.json`, `...-43-remediation-options-target-noauth.*`, `...-44-target-strategy-id.txt` |
| 6 | Run create | Auth create succeeds, no-auth denied | No-auth `401`; auth create `201` | `...-45-create-run-target-pr-noauth.*`, `...-46-create-run-target-pr-noack.*`, `...-48-remediation-run-id.txt` |
| 7 | Run lifecycle | Run should reach terminal state | `success` | `...-51-run-detail-final.json`, `...-52-run-execution-final.json`, `...-53-run-final-status.txt` |
| 8 | Bundle download | Auth `200`, no-auth denied | Auth `200`; no-auth `401` | `...-54-pr-bundle-download-authorized.*`, `...-55-pr-bundle-download-noauth.*`, `evidence/aws/test-26-closure-20260301T193804Z-54-pr-bundle.zip` |
| 9 | Terraform execution | `init/plan/show/apply` succeed | All succeeded (`0/0/0/0`) | `evidence/aws/test-26-closure-20260301T193804Z-70-terraform-*.out/.status`, `...-73-terraform-apply.out` |
| 10 | Post-apply refresh triggers | `ingest/compute/reconcile` accepted | All `202`; refresh completed before timeout | `...-91-trigger-ingest-post-apply.*`, `...-92-trigger-actions-compute-post-apply.*`, `...-93-trigger-actions-reconcile-post-apply.*`, `...-94-ingest-progress-poll-1.json`, `...-99-summary.json` |
| 11 | Final action state | Target action resolved | Target remained in resolved set (`final_action_status=resolved`, `target_in_resolved_list=true`) | `...-110-target-action-detail-final.json`, `...-111-actions-open-s3-2-final.json`, `...-112-actions-resolved-s3-2-final.json`, `...-99-summary.json` |
| 12 | Final finding state (status filters) | Target finding in resolved result set | Target not in NEW list and present in RESOLVED list (`target_finding_in_new_final=false`, `target_finding_in_resolved_final=true`) | `...-113-findings-new-s3-2-final.json`, `...-114-findings-resolved-s3-2-final.json`, `...-99-summary.json` |
| 13 | Finding status source-of-truth detail | User-facing detail status should align with resolved behavior | Detail now returns `status=RESOLVED`, `effective_status=RESOLVED`, and `shadow.status_normalized=RESOLVED` (with canonical/debug state still exposed as `canonical_status=NEW`) | `...-116-target-finding-detail-final.json` |
| 14 | Linked findings status consistency | Linked findings should show same closure interpretation in user-facing status | Linked set: `resolved_by_status_count=4`, `resolved_by_effective_count=4`, `resolved_by_shadow_count=4` (`canonical_status` remains `NEW` for all 4) | `...-117-linked-findings-shadow-summary.json` |
| 15 | Policy preservation (legacy strict compare) | Strict equality may fail if CloudFront statement is re-keyed | Legacy strict compare reports `false` (`policy_preservation_pass=false`) | `evidence/aws/test-26-closure-20260301T193804Z-77-policy-preservation-summary.json` |
| 16 | Policy preservation (delta-aware) | Non-risk statements preserved; only CloudFront remediation delta changed | Passed: `removed_non_risk_statement_count=0`, `added_non_risk_statement_count=0`, CloudFront statement changed only (`removed_cloudfront_statement_count=1`, `added_cloudfront_statement_count=1`) | `evidence/aws/test-26-closure-20260301T193804Z-78-policy-preservation-delta-summary.json` |
| 17 | PAB hardening | Post-apply PAB all true | Passed (`Block*`/`Ignore*`/`Restrict*` all true) | `...-76-aws-b1-public-access-block-post-apply.json`, `...-77-policy-preservation-summary.json`, `...-78-policy-preservation-delta-summary.json` |
| 18 | Runtime version proof | Capture deployed runtime image tags | Captured API/worker images `20260301T193511Z` | `...-115-runtime-stack-version.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/actions` (no auth) | No-auth user must not access actions UI data | `307` redirect | `evidence/ui/test-26-closure-20260301T193804Z-ui-01-actions-route-no-auth.*` |

## Assertions

- Positive path: PASS for remediation execution path (`run success`, bundle `200`, Terraform `init/plan/show/apply` all `0`, refresh APIs `202`).
- Negative path: PASS (`401` no-auth on run-create and bundle-download).
- Auth/UI boundary: PASS (`307` no-auth actions route redirect).
- Policy-preservation result: PASS on delta-aware check (no non-risk statement removals/additions; only CloudFront statement delta).
- Closure result: PASS for end-state resolution (`action_resolved=true`, `finding_resolved=true` by status-filter contract).
- Pre-run reopen visibility: PARTIAL. Target still did not reappear in OPEN query after adversarial-state setup (resolved fallback path was required).
- Finding status consistency: PASS for user-facing contract (`status` is now effective/resolved in detail and linked finding payloads), while canonical/debug status remains separately exposed in `canonical_status`.

## Tracker Updates

- Primary tracker section/row: Section 5 Test 26.
- Related tracker updates required: Sections 3/4/6 + Section 9 changelog.
- Section 8 checkbox impact: None.

## Notes

- Canonical evidence prefix: `test-26-closure-20260301T193804Z-*`.
- Strategy used by generated bundle: `s3_migrate_cloudfront_oac_private`.
- Legacy strict policy compare (`...-77`) remains brittle for CloudFront statement identity changes; delta-aware preservation evidence (`...-78`) confirms non-risk statement preservation.
