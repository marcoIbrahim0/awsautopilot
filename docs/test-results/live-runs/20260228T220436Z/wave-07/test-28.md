# Test 28

- Wave: 07
- Focus: Adversarial IAM inline+managed policy preservation checks
- Status: BLOCKED
- Severity (if issue): 🟠 HIGH

## Preconditions

- Identity: Tenant A admin `maromaher54@gmail.com` authenticated via `POST /api/auth/login`.
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`).
- AWS account: `029037611564`.
- Region(s): `eu-north-1`.
- Runtime under test:
  - Runtime stack: `security-autopilot-saas-serverless-runtime`
  - Last verified image tag in run artifacts: `20260301T205539Z`
- Prerequisite resources/IDs:
  - B3 role: `arch2_mixed_policy_role_b3`
  - B3 inline policy: `arch2_mixed_policy_role_b3-inline-wildcard`
  - B3 required managed policy: `arn:aws:iam::aws:policy/ReadOnlyAccess`
  - Target action ID: `c8201c18-5054-42ee-99c6-815ea082f2c9`
  - Target finding ID: `fe935ab6-1117-4475-a5fb-edbdf8cc8a4b`

## Steps Executed

1. Created/confirmed adversarial IAM B3 inline + managed state.
2. Verified IAM.4 target action/finding as OPEN/NEW pre-remediation.
3. Created PR-mode remediation run and downloaded bundle.
4. Executed bundle Terraform (`init/plan/show/apply`) with non-root credentials (Attempt A).
5. Triggered ingest/compute/reconcile refresh, polled to completion, verified target remained open/NEW.
6. Re-executed downloaded bundle with verified root credentials and full refresh polling (Attempt B).
7. Verified target still remained open/NEW after successful root apply + refresh.
8. Created new PR run with explicit `iam_root_key_delete` strategy and executed bundle with root credentials (Attempt C).
9. Captured apply failure (`InvalidClientTokenId` during generated `UpdateAccessKey`) and then ran post-failure refresh/poll.
10. Verified target remained open/NEW and captured post-run preservation evidence for required B3 safe permissions.
11. Saved evidence and updated tracker/notes.

## API/AWS Evidence (Latest + Closure-Relevant)

| # | Flow | Observed | Artifact Path |
|---|---|---|---|
| 1 | Adversarial IAM B3 setup + prechecks | B3 adversarial inline+managed state confirmed before run chain. | `evidence/api/test-28-closure-20260301T215524Z-01-*.json` to `...-16-adversarial-state-summary.json` |
| 2 | Pre-run OPEN/NEW verification | Target action/finding confirmed open/new before remediation (`IAM.4`). | `.../test-28-closure-20260301T215524Z-36-actions-open-iam4-poll-1.json`, `...-39-findings-new-iam4-pre.json`, `...-37-target-action-id.txt`, `...-40-target-finding-id.txt` |
| 3 | Attempt A run + bundle | Run created/succeeded and bundle downloaded (`201` -> `success`, bundle `200`, no-auth `401`). | `.../test-28-closure-20260301T215524Z-47-create-run-pr-ack.json`, `...-53-run-final-status.txt`, `...-54-pr-bundle-download-authorized.status`, `...-55-pr-bundle-download-noauth.status` |
| 4 | Attempt A Terraform apply (non-root) | `init/plan/show/apply = 0/0/0/1`; explicit root-principal gate failure (`root credentials are required`). | `evidence/aws/test-28-closure-20260301T215524Z-70-terraform-*.status`, `...-73-terraform-apply.err` |
| 5 | Attempt A refresh + terminal status | Ingest/compute/reconcile accepted (`202/202/202`), ingest completed, target remained `action=open`, `finding=NEW`. | `.../test-28-closure-20260301T215524Z-91-*.status`, `...-94-ingest-progress-poll-2.json`, `...-102-target-action-detail-final.json`, `...-107-target-finding-detail-final.json` |
| 6 | Attempt B root identity + apply | Root principal confirmed; root apply succeeded (`init/plan/show/apply=0/0/0/0`). | `evidence/api/test-28-closure-rootapply-20260301T221832Z-120-root-sts-caller-identity.json`, `evidence/aws/test-28-closure-rootapply-20260301T221832Z-130-terraform-*.status`, `...-133-terraform-apply-root.out` |
| 7 | Attempt B refresh + terminal status | Full poll window completed; target still unresolved (`action=open`, `finding=NEW`). | `evidence/api/test-28-closure-rootapply-20260301T221832Z-159-summary-root-apply.json` |
| 8 | Attempt C (`iam_root_key_delete`) run + bundle | Strategy requested (`iam_root_key_delete`), run succeeded, bundle downloaded (`200`, no-auth `401`). | `evidence/api/test-28-closure-rootdelete-20260302T133128Z-203-target-strategy-id.txt`, `...-204-create-run-pr-delete-ack.json`, `...-210-run-final-status.txt`, `...-211-pr-bundle-download-authorized.status`, `...-212-pr-bundle-download-noauth.status` |
| 9 | Attempt C Terraform apply (root) | `init/plan/show/apply = 0/0/0/1`; generated local-exec failed with `InvalidClientTokenId` at `UpdateAccessKey`. | `evidence/aws/test-28-closure-rootdelete-20260302T133128Z-214-terraform-*.status`, `...-217-terraform-apply.err` |
| 10 | Attempt C post-failure refresh | Refresh triggers accepted (`202/202/202`), ingest completed by poll-2, target stayed `action=open`, `finding=NEW`. | `evidence/api/test-28-closure-rootdelete-20260302T133128Z-postrefresh-242-*.status`, `...-253-ingest-progress-final.json`, `...-260-summary.json` |
| 11 | Post-run preservation validation | B3 inline policy + required managed policy still present (`required_safe_permissions_unchanged=true`). | `evidence/api/test-28-closure-rootdelete-20260302T133128Z-postrefresh-261-*.json`, `...-263-*.json`, `...-264-policy-preservation-summary-default.json` |
| 12 | Root-key post-run diagnostic | `test28-root` profile became invalid (`InvalidClientTokenId`), account summary still reports root keys present (`RootKeys=1`). | `evidence/api/test-28-closure-rootdelete-20260302T133128Z-postrefresh-265-root-profile-sts-postrun.*`, `...-266-account-summary-rootkeys.json` |
| 13 | Consolidated attempt-C summary | Manual closure summary: `closure_pass=false`, preservation unchanged `true`. | `evidence/api/test-28-closure-rootdelete-20260302T133128Z-267-summary-manual.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot/Artifact Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/actions` (no auth) | No-auth user must not access actions UI data | `307` redirect; no unauthenticated actions data served | `evidence/ui/test-28-closure-20260301T215524Z-ui-01-actions-route-no-auth.*` |

## Assertions

- Positive path: PARTIAL. PR-mode run creation/execution and bundle generation/download were consistently successful.
- Negative/auth boundaries: PASS. No-auth probes stayed deny-closed (`401` API, `307` UI redirect).
- Closure result: BLOCKED. Across non-root and root attempts, target action/finding remained unresolved (`open`/`NEW`).
- Root execution behavior: BLOCKED.
  - Non-root path fails by explicit root-principal gate.
  - Root delete-strategy apply fails at generated `UpdateAccessKey` with `InvalidClientTokenId`, leaving remediation not closed.
- Policy-preservation result: PASS. Required B3 inline and managed safe permissions remained unchanged in post-run checks (`required_safe_permissions_unchanged=true`).

## Tracker Updates

- Primary tracker section/row: Section 5 Test 28 row updated with latest root-delete continuation evidence.
- Related sections updated: Section 3 #15, Section 4 #22, Section 6 #8.
- Section 8 checkbox impact: None.
- Section 9 changelog update: Added Test 28 continuation entry for 2026-03-02.

## Notes

- Evidence prefixes used:
  - `test-28-closure-20260301T215524Z-*` (Attempt A: non-root)
  - `test-28-closure-rootapply-20260301T221832Z-*` (Attempt B: root disable strategy)
  - `test-28-closure-rootdelete-20260302T133128Z-*` + `...-postrefresh-*` (Attempt C: root delete strategy)
- No product code changes were made.
- Evidence-only conclusion: Test 28 remains blocked due IAM.4 root remediation execution/closure behavior, while policy preservation remains intact.
