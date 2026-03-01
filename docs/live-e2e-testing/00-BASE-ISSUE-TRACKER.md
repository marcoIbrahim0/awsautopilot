# QA Issue Tracker — AWS Security Autopilot
**Base file for all test run outputs**
Environment: https://dev.valensjewelry.com
Test account: maromaher54@gmail.com
Last updated: 2026-03-01T19:51:33Z (Wave 7 Test 26 rerun after effective-status deploy)

---

## HOW TO USE THIS FILE

After each test run, paste findings into the matching section below.
Use the status tags: `🔴 BLOCKING` · `🟠 HIGH` · `🟡 MEDIUM` · `🔵 LOW` · `✅ FIXED` · `⚪ SKIP/NA`

This file is your source of truth. The individual test-NN files are raw output.
This file is the curated list of what actually needs to be fixed.

---

## QUICK STATUS BOARD

| Wave | Tests | Last Run | Pass | Fail | Partial | Blocked |
|------|-------|----------|------|------|---------|---------|
| Wave 1 | 01 | 2026-02-28 | 0 | 1 | 0 | 0 |
| Wave 2 | 02–04 | 2026-02-28 | 3 | 0 | 0 | 0 |
| Wave 3 | 05–08 | 2026-02-28 | 4 | 0 | 0 | 0 |
| Wave 4 | 09–12 | 2026-02-28 | 4 | 0 | 0 | 0 |
| Wave 5 | 13–16 | 2026-03-01 | 4 | 0 | 0 | 0 |
| Wave 6 | 17–22 | 2026-03-01 | 6 | 0 | 0 | 0 |
| Wave 7 | 23–28 | 2026-03-01 | 1 | 0 | 2 | 1 |
| Wave 8 | 29–33 | — | — | — | — | — |
| Wave 9 | 34–35 | — | — | — | — | — |
| **TOTAL** | **35** | **2026-03-01** | **22** | **1** | **2** | **1** |

---

## SECTION 1 — MISSING ENDPOINTS
*Endpoints the frontend calls that returned 404. These are build gaps.*

| # | Endpoint | HTTP Method | Called From | Test Found | Severity | Status |
|---|----------|------------|-------------|-----------|----------|--------|
| 1 | `/api/auth/password` | PUT | Settings → Security | Test 04 | 🔴 BLOCKING | ✅ FIXED (Wave 2 rerun, 2026-02-28: observed `400` wrong-old-password and `204` correct flow) |
| 2 | `/api/auth/refresh` | POST | AuthContext auto-refresh | Test 03 | 🔴 BLOCKING | ✅ FIXED (Wave 2 rerun, 2026-02-28: observed `200` with refresh token payload) |
| 3 | `/api/users/invite-info` | GET | Accept-invite page | Test 08 | 🟠 HIGH | ✅ FIXED (Wave 3 Test 08 rerun, 2026-02-28: observed `400` for invalid-token format and `200` for valid token via backward-compatible alias) |
| 4 | `/api/users/me/slack-settings` | GET/PATCH | Notifications tab | Test 19 | 🟡 MEDIUM | ✅ FIXED (Wave 6 Test 19, 2026-03-01: observed `GET=200`, `PATCH=200` for admin flow; endpoint did not return `404`) |
| 5 | `/api/users/me/digest-settings` | GET/PATCH | Notifications tab | Test 19 | 🟡 MEDIUM | ✅ FIXED (Wave 6 Test 19, 2026-03-01: observed `GET=200`, `PATCH=200` for admin flow; endpoint did not return `404`) |
| 6 | `/api/audit-log` | GET | Settings → Audit | Test 32 | 🟠 HIGH | — |
| 7 | `/api/baseline-report/{id}/data` | GET | In-app report viewer | Test 22 | 🔵 LOW | ✅ FIXED (Wave 6 Test 22 post-deploy rerun, 2026-03-01: authenticated probe returned `200` with report-view payload; no-auth probe returned `401` `{\"detail\":\"Not authenticated\"}`) |
| 8 | `/api/internal/weekly-digest` | POST | Scheduler | Test 20 | 🟡 MEDIUM | ✅ FIXED (Wave 4 Test 10 rerun, 2026-02-28: endpoint present and auth-protected; unauthorized calls returned `403`, not `404`) |
| 9 | `/api/internal/compute` | POST | Scheduler | Test 20 | 🟡 MEDIUM | — |
| 10 | `/api/actions/reconcile` | POST | Post-remediation drawer | Test 16 | 🟡 MEDIUM | ✅ FIXED (Wave 5 Test 16 post-deploy rerun, 2026-03-01: `POST /api/actions/reconcile` returned `202` for admin and `401` with no auth) |
| 11 | `/api/remediation-runs/group-pr-bundle` | POST | PR bundle page | Test 17 | 🟠 HIGH | ✅ FIXED (Wave 6 Test 17 live execution, 2026-03-01: create returned `201`, immediate retry returned `409`, and no-auth probe returned `401`) |
| 12 | `/api/aws/accounts/{id}/control-plane-readiness` | GET | Onboarding wizard | Test 06 | 🟡 MEDIUM | ✅ FIXED (Wave 3 Test 06, 2026-02-28: observed `200` response from account-scoped endpoint) |
| 13 | `/api/aws/accounts/{id}/onboarding-fast-path` | POST | Onboarding wizard | Test 06 | 🟡 MEDIUM | ✅ FIXED (Wave 3 Test 06, 2026-02-28: observed `200` with fast-path trigger payload) |
| 14 | `/api/aws/accounts/{id}/ingest-sync` | POST | Accounts page | Test 29 | 🟡 MEDIUM | — |
| 15 | `/api/auth/forgot-password` | POST | Login/Settings password recovery | Test 04 | 🟠 HIGH | ✅ FIXED (Wave 2 rerun, 2026-02-28: observed `200` generic response) |

> **After each run:** Delete rows that now return non-404. Add new rows for newly discovered 404s.

---

## SECTION 2 — FRONTEND WIRING GAPS
*API returns a response but the shape doesn't match what the component needs to render.*

| # | Test | Component | Field the UI needs | Field the API returns | Visible breakage | Status |
|---|------|-----------|-------------------|----------------------|-----------------|--------|
| 1 | Test 02 | Signup form | top-level `access_token` | top-level `access_token` (present in `201` signup response) | No breakage observed in live rerun | ✅ FIXED (2026-02-28) |
| 2 | Test 03 | AuthContext | `user.role` | `user.role` present in `/api/auth/me` response (`admin` observed) | No breakage observed in Wave 2 rerun | ✅ FIXED (2026-02-28) |
| 3 | Test 06 | Onboarding wizard | per-service `status` field | `all_*_enabled` + `regions[].*_enabled` + per-service errors | Service-level readiness fields observed in live response | ✅ FIXED (Wave 3 Test 06, 2026-02-28) |
| 4 | Test 09 | Ingest progress bar | `percent_complete` | present and aligned with `progress` | Progress contract now complete in rerun evidence | ✅ FIXED (Wave 4 Test 09 rerun, 2026-02-28: observed `percent_complete=100`) |
| 5 | Test 09 | Ingest progress bar | `estimated_time_remaining` | present | ETA field now available in progress response | ✅ FIXED (Wave 4 Test 09 rerun, 2026-02-28: observed `estimated_time_remaining=0`) |
| 6 | Test 10 | Finding card | `aws_service` or `service` | absent on some findings | Service badge blank | — |
| 7 | Test 10 | Finding card | `action_type` | absent on some findings | Action button doesn't render | — |
| 8 | Test 13 | Action drawer | `what_is_wrong` | present in `/api/actions/{id}` detail payload | Explanation section now populated | ✅ FIXED (Wave 5 Test 13 post-deploy rerun, 2026-02-28: observed non-empty `what_is_wrong`) |
| 9 | Test 13 | Action drawer | `what_the_fix_does` | present in `/api/actions/{id}` detail payload | Fix description now populated | ✅ FIXED (Wave 5 Test 13 post-deploy rerun, 2026-02-28: observed non-empty `what_the_fix_does`) |
| 10 | Test 15 | Run progress panel | `current_step` | present via `/api/remediation-runs/{id}/execution` fallback payload (`source=run_fallback`) | Step label now has stable API source on completed runs | ✅ FIXED (Wave 5 Test 15 post-deploy rerun, 2026-03-01: `/execution` returned `200` on all polls with `current_step=completed`) |
| 11 | Test 22 | Reports page | `download_url` on report | absent until polled | Download button never appears | — |
| 12 | Test 29 | Accounts page | `last_synced_at` | absent or null | Last-scanned date blank | — |

> **After each run:** Mark rows ✅ FIXED when confirmed. Add new rows for newly found mismatches.

---

## SECTION 3 — SECURITY ISSUES
*Any finding that could expose data or allow unauthorized access. Review every run.*

| # | Test | Severity | Issue | Expected behavior | Observed | Status |
|---|------|----------|-------|------------------|----------|--------|
| 1 | Test 12 | 🔴 BLOCKING | Cross-tenant finding access returns 200 | 403 or 404 | Post-deploy Wave 4 rerun observed `404` for direct cross-tenant finding lookup | ✅ FIXED (Wave 4 Test 12 rerun, 2026-02-28) |
| 2 | Test 12 | 🔴 BLOCKING | Cross-tenant account access returns 200 | 403 or 404 | Post-deploy Wave 4 rerun observed isolated account list (`200` with empty array for Tenant B) and no Tenant A account read path exposure | ✅ FIXED (Wave 4 Test 12 rerun, 2026-02-28) |
| 3 | Test 12 | 🔴 BLOCKING | Cross-tenant ingest trigger returns 200 | 403 or 404 | Post-deploy Wave 4 rerun observed `404` on cross-tenant ingest, ingest-access-analyzer, and ingest-inspector | ✅ FIXED (Wave 4 Test 12 rerun, 2026-02-28) |
| 4 | Test 19 | 🔴 BLOCKING | SSRF via Slack webhook URL (non-hooks.slack.com accepted) | 400 | Post-deploy Wave 6 Test 19 rerun observed unsafe webhook probes rejected with `400` and stable validation error (`Invalid Slack webhook URL. Expected https://hooks.slack.com/services/...`) for `example.com`, metadata IP, and hooks-lookalike domain | ✅ FIXED (Wave 6 Test 19 rerun, 2026-03-01: `test-19-rerun-20260301T015756Z`) |
| 5 | Test 30 | 🟠 HIGH | Login endpoint not rate-limited after N attempts | 429 after threshold | TBD | — |
| 6 | Test 30 | 🟠 HIGH | No `Retry-After` header on 429 response | Header present | TBD | — |
| 7 | Test 31 | 🟠 HIGH | Non-admin can invite users | 403 | TBD | — |
| 8 | Test 31 | 🟠 HIGH | Non-admin can delete accounts | 403 | TBD | — |
| 9 | Test 18 | 🟠 HIGH | PR bundle ZIP downloadable without auth token | 401 | Wave 6 Test 18 observed no-auth `401`, invalid-token `401`, and wrong-tenant token `404` on `GET /api/remediation-runs/{id}/pr-bundle.zip` | ✅ FIXED (Wave 6 Test 18, 2026-03-01) |
| 10 | Test 08 | 🟠 HIGH | Invite token reuse not blocked | 404 or 410 (must reject reuse/expired token) | Post-deploy Wave 3 rerun observed consumed token rejection on replay: `GET /api/users/invite-info` -> `404`, `POST /api/users/accept-invite` -> `404` (`Invite not found or expired`) | ✅ FIXED (Wave 3 Test 08 rerun, 2026-02-28) |
| 11 | Test 32 | 🟡 MEDIUM | Audit records contain secrets (token, role_arn, password) | No secrets in payload | TBD | — |
| 12 | Test 32 | 🟡 MEDIUM | Non-admin user can read audit log | 403 | TBD | — |
| 13 | Test 03 | 🔴 BLOCKING | Bearer token remains valid after logout | 401 on post-logout `/api/auth/me` with pre-logout token | Observed `401` (`Invalid or expired token`) in Wave 2 rerun | ✅ FIXED (Wave 2 rerun, 2026-02-28) |
| 14 | Test 07 | 🔴 BLOCKING | AWS account registration accepts no-auth requests when `tenant_id` is known | 401/403 for unauthenticated register calls | Post-deploy Wave 3 rerun observed `401` for no-auth with both known and random tenant ids, and `401` for invalid bearer token | ✅ FIXED (Wave 3 Test 07 rerun, 2026-02-28) |
| 15 | Test 25 | 🟠 HIGH | IAM.4 root-key finding remained active after full closure flow | Target action/finding should resolve after successful root-key remediation apply and refresh | Wave 7 Test 25 created run `d7325d69-35ec-4d2b-8042-72d5b36f35ad` (`201`), refresh reached `completed` (`100%`), but apply failed under non-root credentials (`ERROR: root credentials are required to disable root access keys.`) and linked findings remained `NEW` | OPEN (Wave 7 Test 25 full closure validation, 2026-03-01: `test-25-closure-20260301T154046Z`) |
| 16 | Test 26 | 🟠 HIGH | Complex S3 remediation overwrote existing non-risk bucket policy statements | Non-risk statements should remain preserved after remediation apply | Latest rerun reconfirmed non-risk statements were unchanged (`removed_non_risk=0`, `added_non_risk=0`) with only CloudFront remediation statement rotation (`removed_cloudfront=1`, `added_cloudfront=1`) | ✅ FIXED (Wave 7 Test 26 rerun, 2026-03-01: `test-26-closure-20260301T193804Z`) |

> **Any 🔴 BLOCKING security issue must halt go-live. Fix before resuming the test cycle.**

---

## SECTION 4 — BUGS & BROKEN FLOWS
*Things that work structurally but produce wrong behavior.*

| # | Test | Flow | What breaks | Root cause hypothesis | Priority | Status |
|---|------|------|------------|----------------------|----------|--------|
| 1 | Test 03 | Post-logout token check | Token still valid after logout | Session not invalidated server-side | 🔴 BLOCKING | ✅ FIXED (Wave 2 rerun, 2026-02-28: post-logout pre-logout bearer token returned `401`) |
| 2 | Test 04 | Password change | 404 on PUT /api/auth/password | Endpoint not built | 🔴 BLOCKING | ✅ FIXED (Wave 2 rerun, 2026-02-28: observed `400` wrong-old-password and `204` correct flow) |
| 3 | Test 11 | Multi-value filter | `severity=CRITICAL,HIGH` returns wrong set | Comma-separated not parsed | 🟠 HIGH | ✅ FIXED (Wave 4 Test 11 rerun, 2026-02-28: observed severities only `CRITICAL`/`HIGH`, `total=39`) |
| 4 | Test 11 | Pagination | Page 1 and page 2 contain duplicate IDs | Missing stable sort on paginated query | 🟠 HIGH | ✅ FIXED (Wave 4 Test 11 rerun, 2026-02-28: duplicate IDs across page1/page2 = `0`) |
| 5 | Test 14 | Duplicate run guard | Immediate duplicate creates on same action return `201` with new run IDs instead of conflict (`409`) | Duplicate/idempotency guard no longer enforced for observed immediate retries | 🟠 HIGH | ✅ FIXED (Wave 5 Test 14 post-deploy rerun, 2026-03-01: first/immediate/third create observed `201/409/409` for action `9c31f438-1ade-4cc7-91c8-b959870a615b`, conflict payload included `reason=duplicate_active_run`) |
| 6 | Test 16 | Recompute | `/api/actions/compute` returns 404 | Endpoint not built | 🟠 HIGH | ✅ FIXED (Wave 5 Test 16 live execution, 2026-02-28: `POST /api/actions/compute` returned `202` with stable retry status/body and required fields) |
| 7 | Test 17 | PR bundle group | `/api/remediation-runs/group-pr-bundle` returns 404 | Endpoint not built | 🟠 HIGH | ✅ FIXED (Wave 6 Test 17 live execution, 2026-03-01: endpoint returned `201` on create, duplicate guard `409`, run completed `success`) |
| 8 | Test 18 | ZIP contents | Terraform file contains PLACEHOLDER values | Templating not substituting real resource IDs | 🟠 HIGH | ✅ FIXED (Wave 6 Test 18 post-deploy rerun, 2026-03-01: ZIP contract check passed with `expected=78`, `actual=78`, `missing=0`, `unexpected=0`, and `placeholder_hits=[]` in IaC files; auth matrix remained `200/401/401/404`) |
| 9 | Test 20 | Internal digest/scheduler auth guard | Correct user token gets 200 on internal endpoint | Missing auth guard on `/api/internal/*` | 🔴 BLOCKING | ✅ FIXED (Wave 6 Test 20 live + rerun, 2026-03-01: `/api/internal/reconciliation/schedule-tick` returned `403` for no-secret/wrong-secret/user-token-only calls and `200` only with correct scheduler secret in both `test-20-live-20260301T011449Z` and `test-20-rerun-20260301T014248Z`) |
| 10 | Test 22 | Baseline report | Second report not rate-limited (no 429) | Rate-limit not implemented | 🟡 MEDIUM | ✅ FIXED (Wave 6 Test 22 live execution, 2026-03-01: first `POST /api/baseline-report` returned `201`; immediate repeats returned `429` with `Retry-After: 86399`) |
| 11 | Test 06 | Invite DB query | DB model path wrong in Python helper | Model import path mismatch | 🔵 LOW | — |
| 12 | Test 33 | PR proof C2 | No Terraform plan timestamp in README | Template doesn't include plan metadata | 🟠 HIGH | — |
| 13 | Test 33 | PR proof C5 | No preserved-config statement in B-series README | README template missing preservation section | 🟠 HIGH | — |
| 14 | Test 04 | Forgot-password flow | 404 on POST /api/auth/forgot-password | Endpoint not built | 🟠 HIGH | ✅ FIXED (Wave 2 rerun, 2026-02-28: observed `200` generic response) |
| 15 | Test 07 | Duplicate account registration | Re-registering an already connected account returns `201` instead of conflict/idempotent duplicate response | Duplicate path currently behaves like create/upsert | 🟠 HIGH | ✅ FIXED (Wave 3 Test 07 rerun, 2026-02-28: duplicate register now returns `409` with explicit conflict detail) |
| 16 | Test 16 | Preview mode compatibility | `/api/actions/{id}/remediation-options` advertises `mode_options=[\"pr_only\"]`, but `/api/actions/{id}/remediation-preview?mode=pr_only` returns `422` expecting `direct_fix` | Preview validator only accepts `direct_fix`, causing options/preview contract mismatch | 🟡 MEDIUM | ✅ FIXED (Wave 5 Test 16 post-deploy rerun, 2026-03-01: options still advertise `pr_only` and realistic preview call returned `200`) |
| 17 | Test 16 | Reconcile write path | `POST /api/actions/reconcile` returns `405` (`Allow: GET`) on admin/no-auth probes | Route/method mismatch vs expected POST reconcile flow | 🟡 MEDIUM | ✅ FIXED (Wave 5 Test 16 post-deploy rerun, 2026-03-01: reconcile POST returned `202`; no-auth probe returned `401`) |
| 18 | Test 19 | Slack webhook validation | `PATCH /api/users/me/slack-settings` accepts non-Slack and SSRF-style webhook URLs | Missing strict webhook allowlist/URL validation (domain/scheme/host) before persistence | 🔴 BLOCKING | ✅ FIXED (Wave 6 Test 19 post-deploy rerun, 2026-03-01: unsafe probes returned `400`, valid hooks URL remained `200`) |
| 19 | Test 23 | S3 blast-radius differentiation | Non-website/non-public B1 bucket still receives the same `s3_public_access_dependency` warn+block treatment family as A1 | Runtime dependency evidence remained unavailable for both (`access_path_evidence_unavailable`, website probe `AccessDenied`), so blast-radius differentiation did not occur for B1 | 🟡 MEDIUM | ✅ FIXED (Wave 7 Test 23 full closure rerun, 2026-03-01: `test-23-closure-20260301T033953Z`; runtime checks now differentiate: A1 `warn`, B1 `pass`) |
| 20 | Test 23 | Post-apply closure propagation | Target B1 S3.2 action/finding remained open after successful PR run + Terraform apply + refresh sequence | Finding/action closure did not propagate within 15-minute poll window despite applied bucket PAB state and accepted refresh triggers (`ingest/compute/reconcile` all `202`) | 🟡 MEDIUM | OPEN (Wave 7 Test 23 full closure rerun, 2026-03-01: `test-23-closure-20260301T033953Z`) |
| 21 | Test 24 | Post-apply closure propagation in shadow mode | Target A2 EC2.53 action/finding remained open after successful PR run + Terraform apply + refresh sequence | In this environment (shadow mode), immediate resolved-status transition is not expected; ingest/compute/reconcile accepted (`202`) and ingest-progress reached `completed` (`100%`) | 🟡 MEDIUM | ⚪ SKIP/NA (Expected in shadow mode; Test 24 accepted as PASS, 2026-03-01: `test-24-closure-20260301T134354Z`) |
| 22 | Test 25 | IAM root-key remediation apply path | Full closure cannot complete from non-root operator session; `terraform apply` fails while run generation succeeds | Generated IAM.4 bundle enforces root principal at execution (`null_resource` local-exec checks caller ARN matches `arn:aws:iam::*:root`), so standard IAM admin credentials cannot execute the remediation step | 🟠 HIGH | OPEN (Wave 7 Test 25 full closure validation, 2026-03-01: `test-25-closure-20260301T154046Z`) |
| 23 | Test 26 | PR remediation lifecycle for complex S3 policy | Run previously stayed `pending/queued`, preventing bundle download/apply | Earlier worker throughput/concurrency bottleneck delayed dequeue/processing; rerun reached terminal state quickly (`pending` -> `success` by poll-2) and bundle download returned `200` | 🟠 HIGH | ✅ FIXED (Wave 7 Test 26 rerun, 2026-03-01: `test-26-closure-20260301T171651Z`) |
| 24 | Test 26 | Complex-policy preservation + closure semantics | Non-risk policy statements were dropped and target action stayed open in prior rerun | Generation path now fails closed when preservation input is missing, auto-preloads policy preservation evidence, and action recompute uses effective shadow status so target action moved to `resolved` after refresh | 🟠 HIGH | ✅ FIXED (Wave 7 Test 26 closure rerun, 2026-03-01: `test-26-closure-20260301T181657Z`) |
| 25 | Test 26 | Canonical vs effective finding status drift | Finding detail payload can report canonical `status=NEW` while effective/shadow status is resolved | After effective-status deploy, finding detail now reports user-facing `status=RESOLVED` plus `effective_status=RESOLVED`; canonical status is still preserved in separate `canonical_status=NEW` debug field | 🟡 MEDIUM | ✅ FIXED (Wave 7 Test 26 rerun, 2026-03-01: `test-26-closure-20260301T193804Z`) |
| 26 | Test 26 | Pre-run adversarial reopen detection | After restoring adversarial state, target B1 S3.2 action should reappear in OPEN set before remediation run | Even with pre-run `ingest+compute+reconcile`, OPEN polling (`status=open`) returned 24 S3.2 actions but did not include target; target remained discoverable only via `status=resolved` fallback | 🟡 MEDIUM | OPEN (Wave 7 Test 26 rerun, 2026-03-01: `test-26-closure-20260301T193804Z`) |

---

## SECTION 5 — ADVERSARIAL TEST RESULTS (Tests 23–28)
*Fill in after each Wave 7 run.*

| Test | Resource type | Group A detected | Blast radius correct | Group B false-positive-free | Config preserved | Result |
|------|--------------|-----------------|---------------------|-----------------------------|-----------------|--------|
| 23 | S3 blast radius | Yes (`A1` + `B1` actions/findings observed) | Yes (B1 remediated without affecting A1 state) | Yes for dependency differentiation (`B1` strategy checks now `pass`) | Yes (A1 website/public posture preserved while B1 PAB hardened) | PARTIAL (🟡 MEDIUM: closure propagation still open) |
| 24 | SG dependency chain | Yes (`A2` action/finding for SG-A observed open pre-remediation) | Yes (SG-A remediated with SG-B/EC2/RDS dependencies preserved) | N/A (Test 24 focuses A2 dependency-chain target, not B2 false-positive evaluation) | Yes (only intended SG-A ingress changes; SG-B refs and attached dependencies unchanged) | PASS (shadow mode acceptance: execution + safety + refresh-completed) |
| 25 | IAM multi-principal | Yes (A3/B3 IAM adversarial state confirmed; related IAM.4 action/finding observed open) | N/A for direct blast-radius mutation (account-level IAM.4 target), with preservation checks passing | N/A (Test 25 validates multi-principal preservation during IAM.4 closure attempt, not B-series false-positive filtering) | Yes (A3 trust principals + inline policy set, and B3 trust/managed attachments remained unchanged pre/post apply) | BLOCKED (🟠 HIGH: bundle apply requires root credentials; target action/finding stayed open/NEW) |
| 26 | Complex S3 policy | Adversarial state confirmed, but target was not returned in OPEN set (resolved fallback used) | N/A (test objective centers on preservation/closure after remediation apply) | N/A (test objective is policy-preservation during remediation) | Yes on delta-aware comparison (non-risk statements unchanged; CloudFront statement rotated only) | PARTIAL (🟡 MEDIUM: execution/preservation passed; only pre-run reopen detection gap remains) |
| 27 | Mixed SG rules | — | N/A | — | — | — |
| 28 | IAM inline + managed | — | N/A | — | — | — |

---

## SECTION 6 — PARTIAL IMPLEMENTATIONS
*Endpoints that exist and respond but are incomplete or stub-level.*

| # | Endpoint | What works | What's missing | Test | Status |
|---|----------|-----------|----------------|------|--------|
| 1 | `/api/aws/accounts/{id}/service-readiness` | Returns 200 | Per-service status fields missing | Test 06 | ✅ FIXED (Wave 3 Test 06, 2026-02-28: per-service fields observed) |
| 2 | `/api/findings/grouped` | Returns 200 | Group keys not stable across requests | Test 10 | — |
| 3 | `/api/exports` | Creates export | `download_url` never populated | Test 21 | ✅ FIXED (Wave 6 Test 21 live execution, 2026-03-01: create `202`, poll `pending -> success`, `download_url` observed `null -> present`, download `200` with ZIP integrity pass) |
| 4 | `/api/baseline-report` | Creates report | In-app viewer and throttle contracts now observed end-to-end (`/data` returns report payload) | Test 22 | ✅ FIXED (Wave 6 Test 22 post-deploy rerun, 2026-03-01: create `201`, immediate repeats `429` + `Retry-After`, detail `pending -> success`, `/api/baseline-report/{id}/data` `200`, no-auth `/data` `401`) |
| 5 | `/api/remediation-runs/{id}/execution` | Endpoint returns stable `200` payload for valid in-tenant runs (including completed runs) | Pollable progress fields now present (`current_step`, `progress_percent`, `completed_steps`, `total_steps`) | Test 15 | ✅ FIXED (Wave 5 Test 15 post-deploy rerun, 2026-03-01: `200/200/200` with stable field values) |
| 6 | `/api/auth/forgot-password` | Returns 200 generic message | No account-existence differential in existing vs non-existing probe | Test 04 | ✅ FIXED (Wave 2 rerun, 2026-02-28) |
| 7 | `/api/actions/reconcile` + refresh chain | Post-apply refresh calls (`ingest/compute/reconcile`) accept and return `202`; ingest-progress can still complete (`status=completed`) | Closure propagation remains open for S3.2 in Test 23 (`open/NEW` after 15-minute poll). Test 24 is accepted as PASS under shadow-mode criteria. | Test 23 | — |
| 8 | `/api/remediation-runs` IAM.4 PR-bundle execution path | Run creation/execution contracts and bundle generation/download work (`201`, run `success`, zip `200`) with explicit `manual_high_risk` metadata | Closure still requires root-principal execution; generated Terraform apply fails for non-root IAM sessions (`ERROR: root credentials are required to disable root access keys.`), leaving IAM.4 action/finding open after completed refresh | Test 25 | OPEN (Wave 7 Test 25 full closure validation, 2026-03-01: `test-25-closure-20260301T154046Z`) |
| 9 | `/api/remediation-runs` S3.2 PR-bundle execution path (B1 complex policy) | Run create/detail/execution/download contracts now complete (`201`, `success`, bundle `200`) | Prior stuck-pending behavior no longer reproduced in rerun (`pending` to `success` by poll-2) | Test 26 | ✅ FIXED (Wave 7 Test 26 rerun, 2026-03-01: `test-26-closure-20260301T171651Z`) |
| 10 | `/api/remediation-runs` S3.2 complex-policy preservation behavior | Latest run/bundle/apply/refresh all succeeded (`terraform init/plan/show/apply=0/0/0/0`); end state remained resolved in action/finding status filters; finding detail now returns user-facing `status=RESOLVED` with canonical debug separation | Pre-run adversarial reopen still does not surface target in OPEN query (`status=open`) even after pre-run reconcile trigger | Test 26 | PARTIAL (Wave 7 Test 26 rerun, 2026-03-01: `test-26-closure-20260301T193804Z`) |

---

## SECTION 7 — ENVIRONMENT & INFRASTRUCTURE NOTES
*One-time issues that are setup-related, not product bugs.*

| # | Test | Note | Action needed | Status |
|---|------|------|---------------|--------|
| 1 | Test 01 + Test 05 | Frontend HTTP still serves `200` without HTTPS redirect; Wave 3 rerun fixed prior HTTPS `530` (`1033`) outage and now serves app content at `https://dev.valensjewelry.com/` | Keep frontend/tunnel services active and enforce HTTP->HTTPS redirect at edge/proxy; then re-run Test 01 HTTPS-redirect check | 🟠 HIGH (Wave 3 Test 05 rerun, 2026-02-28: HTTPS root restored to `200`; redirect gap remains) |
| 2 | Test 05 | `08-deployment-report.md` now includes explicit `TEST_ACCOUNT_ID`, `READ_ROLE_ARN`, and `WRITE_ROLE_ARN` labels (rechecked in Wave 3 rerun evidence) | None | ✅ FIXED (Wave 3 Test 05 rerun, 2026-02-28) |
| 3 | Test 07 | UserInvite DB model path may differ from example | Confirm Python import path | — |
| 4 | Test 20 | Internal scheduler secret location | Runtime source confirmed on live API Lambda: `RECONCILIATION_SCHEDULER_SECRET` unset, fallback uses `CONTROL_PLANE_EVENTS_SECRET`; `DIGEST_CRON_SECRET` currently absent | None | ✅ FIXED (Wave 6 Test 20, 2026-03-01) |
| 5 | Test 30 | Rate limit window duration unknown | Check middleware config | — |

---

## SECTION 8 — GO-LIVE BLOCKERS CHECKLIST
*Every item here must be ✅ before go-live is approved.*

### 🔴 Critical — must fix before any user touches production

- [x] **T12-1** Cross-tenant data isolation confirmed across findings, accounts, runs
- [x] **T12-3** Cross-tenant ingest trigger blocked (403/404)
- [x] **T19-4** SSRF via Slack webhook — non-hooks.slack.com domain rejected
- [x] **T20-9** `/api/internal/*` routes protected from user-token access
- [x] **T07-14** AWS account registration rejects unauthenticated requests even when `tenant_id` is supplied
- [x] **T03-1** Token invalidated server-side on logout
- [x] **T14-5** Duplicate run guard returns 409 (idempotency)

### 🟠 High — fix before go-live, workaround required otherwise

- [x] **T04-2** PUT `/api/auth/password` endpoint built and working
- [x] **T16-6** POST `/api/actions/compute` endpoint built and working
- [x] **T17-7** POST `/api/remediation-runs/group-pr-bundle` endpoint built and working
- [ ] **T30-5** Login rate-limiting enforced (429 after threshold)
- [ ] **T31-7** Non-admin invite blocked (403)
- [ ] **T31-8** Non-admin account delete blocked (403)
- [x] **T18-8** PR bundle ZIP requires auth to download
- [x] **T08-10** Invite token reuse blocked after acceptance
- [x] **T11-3** Multi-value severity filter works correctly
- [x] **T11-4** Pagination returns no duplicate IDs

### 🟡 Medium — fix before first paying customer

- [x] **T06** Per-service status fields in service-readiness response
- [x] **T21** Evidence export `download_url` populated correctly
- [x] **T09** `percent_complete` present in ingest-progress response
- [x] **T13** Action detail payload includes drawer explanation fields (`what_is_wrong`, `what_the_fix_does`)
- [x] **T15** Remediation run execution contract exposes pollable execution/step-log data
- [x] **T16-preview** Remediation preview accepts mode values returned by remediation-options
- [x] **T16-reconcile** POST `/api/actions/reconcile` supports write contract (not `405 Allow: GET`)
- [x] **T19** Slack webhook settings persist correctly
- [x] **T22** Baseline report second-request rate-limited
- [ ] **T32** Audit log inaccessible to non-admin roles
- [ ] **T33** PR bundle README includes Terraform plan timestamp (C2)
- [ ] **T33** PR bundle README includes preservation statement (C5)

---

## SECTION 9 — CHANGELOG
*Track when issues are fixed so you know what to re-test.*

| Date | Fixed issue # | Fix description | Re-tested in | Result |
|------|--------------|----------------|-------------|--------|
| 2026-02-28 | Section 2 #1 | Live signup contract returns top-level `access_token` (no nested `data.token` mismatch observed) | Wave 2 Test 02 | ✅ FIXED |
| 2026-02-28 | Section 2 #2 | `/api/auth/me` includes `user.role` (`admin` observed) for AuthContext role wiring | Wave 2 Test 03 rerun | ✅ FIXED |
| 2026-02-28 | Section 1 #2 | `/api/auth/refresh` now responds with `200` and refresh token payload | Wave 2 Test 03 rerun | ✅ FIXED |
| 2026-02-28 | Section 3 #13 / Section 4 #1 | Post-logout pre-logout bearer token now rejected (`401 Invalid or expired token`) | Wave 2 Test 03 rerun | ✅ FIXED |
| 2026-02-28 | Section 1 #1 / Section 4 #2 | `PUT /api/auth/password` now functional (`400` wrong old password, `204` correct change) | Wave 2 Test 04 rerun | ✅ FIXED |
| 2026-02-28 | Section 1 #15 / Section 4 #14 / Section 6 #6 | `POST /api/auth/forgot-password` now returns generic `200` for existing and non-existing emails | Wave 2 Test 04 rerun | ✅ FIXED |
| 2026-02-28 | Section 1 #12 / Section 1 #13 | Onboarding `control-plane-readiness` and `onboarding-fast-path` account endpoints observed returning `200` | Wave 3 Test 06 | ✅ FIXED |
| 2026-02-28 | Section 2 #3 / Section 6 #1 | Service-readiness payload now includes service-level fields consumed by onboarding (`all_*` and `regions[].*_enabled`) | Wave 3 Test 06 | ✅ FIXED |
| 2026-02-28 | Section 3 #14 | `POST /api/aws/accounts` now rejects unauthenticated known-tenant and random-tenant registration attempts with `401` (no tenant enumeration) | Wave 3 Test 07 rerun | ✅ FIXED |
| 2026-02-28 | Section 4 #15 | Duplicate AWS account registration now returns deterministic `409` with explicit `Account already connected` conflict contract | Wave 3 Test 07 rerun | ✅ FIXED |
| 2026-02-28 | Section 7 #1 (HTTPS `530` sub-issue) | `https://dev.valensjewelry.com/` restored from Cloudflare `530/1033` to `200` by restoring active `valens-dev` tunnel connector and frontend origin service; HTTP redirect gap still open | Wave 3 Test 05 rerun | PARTIAL |
| 2026-02-28 | Section 1 #3 | Added backward-compatible `GET /api/users/invite-info` alias with canonical invite-info behavior parity (`400` invalid format, `200` valid token) | Wave 3 Test 08 rerun | ✅ FIXED |
| 2026-02-28 | Section 3 #10 / Section 8 T08-10 | Invite token lifecycle now verified in live rerun: valid token accepted once (`200`), replay rejected (`404`), and expired token rejected (`410`) on both invite-info and accept-invite paths | Wave 3 Test 08 rerun | ✅ FIXED |
| 2026-02-28 | Section 7 #2 | `08-deployment-report.md` now explicitly lists `TEST_ACCOUNT_ID`, `READ_ROLE_ARN`, and `WRITE_ROLE_ARN` and passed Wave 3 doc-prereq recheck | Wave 3 Test 05 rerun | ✅ FIXED |
| 2026-02-28 | Section 2 #4 / Section 2 #5 / Section 8 T09 | Ingest progress contract now includes compatibility fields `percent_complete` and `estimated_time_remaining` while keeping existing `progress` | Wave 4 Test 09 rerun | ✅ FIXED |
| 2026-02-28 | Section 4 #9 / Section 8 T20-9 / Section 1 #8 | Internal weekly-digest endpoint auth guard now deny-closed with `403` for unauthorized calls (member bearer and wrong secret) | Wave 4 Test 10 rerun | ✅ FIXED |
| 2026-02-28 | Section 4 #3 / Section 4 #4 / Section 8 T11-3 / Section 8 T11-4 | Findings filters/pagination rerun verified: invalid severity now returns `400`; multi-value severity returns correct set; page1/page2 duplicate IDs `0` | Wave 4 Test 11 rerun | ✅ FIXED |
| 2026-02-28 | Section 3 #1 / Section 3 #2 / Section 3 #3 / Section 8 T12-1 / Section 8 T12-3 | Cross-tenant reads and ingest triggers revalidated as blocked (`404`) with isolated tenant account visibility | Wave 4 Test 12 rerun | ✅ FIXED |
| 2026-02-28 | Section 2 #8 / Section 2 #9 / Section 8 T13 | `GET /api/actions/{id}` now returns non-empty `what_is_wrong` and `what_the_fix_does`; auth/negative/idempotency checks remained stable (`401` no-auth, `404` wrong-tenant, deterministic repeat body) | Wave 5 Test 13 post-deploy rerun | ✅ FIXED |
| 2026-02-28 | Section 4 #5 / Section 8 T14-5 | Duplicate-run guard now verified live: `POST /api/remediation-runs` first call returned `201` (`pending`), immediate identical second call returned `409` (`Duplicate pending run`) | Wave 5 Test 14 live execution | ✅ FIXED |
| 2026-02-28 | Section 4 #6 / Section 8 T16-6 | Recompute endpoint contract revalidated live: `POST /api/actions/compute` returned `202` with stable immediate-retry behavior and required fields (`message`, `tenant_id`, `scope`) | Wave 5 Test 16 live execution | ✅ FIXED |
| 2026-03-01 | Section 1 #10 / Section 4 #16 / Section 4 #17 / Section 8 T16-preview,T16-reconcile | Test 16 post-deploy rerun closed preview/reconcile gaps: `mode=pr_only` preview returned `200`, `POST /api/actions/reconcile` returned `202` with stable immediate retry, and no-auth reconcile probe returned `401` | Wave 5 Test 16 post-deploy rerun | ✅ FIXED |
| 2026-03-01 | Section 2 #10 / Section 6 #5 / Section 8 T15 | `/api/remediation-runs/{id}/execution` now returns `200` for sampled completed in-tenant run with stable progress fields (`current_step`, `progress_percent`, `completed_steps`, `total_steps`) across three polls | Wave 5 Test 15 post-deploy rerun | ✅ FIXED |
| 2026-03-01 | Section 1 #11 / Section 4 #7 / Section 8 T17-7 | Grouped PR bundle endpoint validated live: `POST /api/remediation-runs/group-pr-bundle` returned `201`, immediate duplicate create returned `409`, no-auth probe returned `401`, and created run reached `success` with `group_bundle` + `pr_bundle` artifacts | Wave 6 Test 17 live execution | ✅ FIXED |
| 2026-03-01 | Section 3 #9 / Section 8 T18-8 | PR bundle ZIP download auth boundary validated live: authorized download returned `200`, no-auth and invalid-token probes returned `401`, and wrong-tenant probe returned `404` | Wave 6 Test 18 live execution | ✅ FIXED |
| 2026-03-01 | Section 4 #8 | Post-deploy Wave 6 rerun closed ZIP artifact-correctness gap: fresh grouped run `0b91ccbd-1c39-4cb3-8791-4e3a363c0fcb` produced ZIP contract `expected=78`, `actual=78`, `missing=0`, `unexpected=0`, and no unresolved placeholder tokens in IaC files (`placeholder_hits=[]`) | Wave 6 Test 18 post-deploy rerun (`test-18-rerun-postdeploy-20260301T010114Z`) | ✅ FIXED |
| 2026-03-01 | Section 6 #3 / Section 8 T21 | Export download-url contract validated live: `POST /api/exports` returned `202`; detail poll showed `status=pending` with `download_url=null` then `status=success` with non-null `download_url`; presigned download returned `200` (repeat `200`) with matching SHA-256 and ZIP integrity pass | Wave 6 Test 21 live execution (`test-21-live-20260301T011127Z`) | ✅ FIXED |
| 2026-03-01 | Section 1 #4 / Section 1 #5 | Notifications settings endpoints validated as present in live SaaS: `GET/PATCH /api/users/me/slack-settings` and `GET/PATCH /api/users/me/digest-settings` returned non-404 contracts (`200` in admin flow) | Wave 6 Test 19 live execution (`test-19-live-20260301T011252Z`) | ✅ FIXED |
| 2026-03-01 | Section 8 T19 | Slack settings persistence revalidated live on isolated tenant: valid hooks URL persisted (`slack_webhook_configured=true`) and clear flow persisted (`slack_webhook_configured=false`) | Wave 6 Test 19 live execution (`test-19-live-20260301T011252Z`) | ✅ FIXED |
| 2026-03-01 | Section 4 #5 / Section 8 T14-5 | Duplicate-run guard regression observed in rerun recheck: identical immediate create retries returned `201/201/201` with distinct run IDs for the same action instead of `409 Duplicate pending run` | Wave 5 Test 14 rerun recheck (`test-14-rerun-recheck-20260301T011119Z`) | 🔁 REGRESSION |
| 2026-03-01 | Section 4 #5 / Section 8 T14-5 | Duplicate-run guard revalidated as fixed after deploy: first create returned `201` and both immediate retries returned `409` with stable conflict metadata (`reason=duplicate_active_run`, same `existing_run_id`) | Wave 5 Test 14 post-deploy rerun (`test-14-rerun-postdeploy-20260301T013443Z`) | ✅ FIXED |
| 2026-03-01 | Section 4 #9 / Section 8 T20-9 / Section 7 #4 | Internal scheduler auth guard revalidated live on `/api/internal/reconciliation/schedule-tick`: no secret `403`, wrong secret `403`, user-token-only `403`, correct scheduler secret `200`; runtime secret source confirmed via Lambda env (`RECONCILIATION_SCHEDULER_SECRET` absent, fallback `CONTROL_PLANE_EVENTS_SECRET` present) | Wave 6 Test 20 live execution (`test-20-live-20260301T011449Z`) | ✅ FIXED |
| 2026-03-01 | Section 4 #9 / Section 8 T20-9 | Test 20 rerun reconfirmed scheduler secret-guard contract unchanged: no secret `403`, wrong secret `403`, user-token-only `403`, correct scheduler secret `200`, `all_pass=true` | Wave 6 Test 20 rerun (`test-20-rerun-20260301T014248Z`) | ✅ FIXED |
| 2026-03-01 | Section 4 #10 / Section 8 T22 | Baseline-report throttle contract validated live: `POST /api/baseline-report` returned `201` (`pending`), immediate repeated requests returned `429` with `Retry-After: 86399`, and created report progressed to `success` with `download_url` present | Wave 6 Test 22 live execution (`test-22-live-*`) | ✅ FIXED |
| 2026-03-01 | Section 3 #4 / Section 4 #18 / Section 8 T19-4 | Slack webhook SSRF validation revalidated post-deploy: valid hooks URL remained accepted (`200`), while unsafe probes (`example.com`, metadata IP, hooks-lookalike domain) now reject with `400` and deterministic validation error body | Wave 6 Test 19 rerun (`test-19-rerun-20260301T015756Z`) | ✅ FIXED |
| 2026-03-01 | Section 1 #7 / Section 6 #4 / Section 8 T22 | Baseline report viewer endpoint closure validated post-deploy: fresh tenant flow observed `POST /api/baseline-report` `201`, immediate repeats `429` (`Retry-After: 86399`), detail `pending -> success`, `GET /api/baseline-report/{id}/data` `200`, and no-auth `/data` `401` | Wave 6 Test 22 post-deploy rerun (`test-22-rerun-postdeploy-20260301T021102Z-*`) | ✅ FIXED |
| 2026-03-01 | Section 5 Test 23 / Section 4 #19 | Wave 7 Test 23 adversarial run observed A1/B1 detection and A1 blast-radius gating, but B1 (no website configuration, non-public policy) still received identical `s3_public_access_dependency` warn/risk-ack gate; logged as differentiation gap | Wave 7 Test 23 live execution (`test-23-live-20260301T023337Z`) | PARTIAL |
| 2026-03-01 | Section 5 Test 23 / Section 4 #19 | Post-redeploy rerun executed against runtime images `20260301T031756Z`; A1/B1 remained detected and auth boundaries passed, but B1 still failed blast-radius differentiation because runtime checks reported `access_path_evidence_unavailable` (`AccessDenied`) and kept warn+block dependency behavior | Wave 7 Test 23 post-deploy rerun (`test-23-rerun-postdeploy-20260301T032419Z`) | PARTIAL |
| 2026-03-01 | Section 4 #19 / Section 5 Test 23 | Full closure rerun fixed blast-radius differentiation: runtime access-path evidence is now available, A1 strategies remain `warn`, and B1 standard/migrate strategies now return dependency `pass`; B1 PR run creation succeeded (`201`) without risk-ack gate | Wave 7 Test 23 full closure rerun (`test-23-closure-20260301T033953Z`) | ✅ FIXED |
| 2026-03-01 | Section 4 #20 / Section 6 #7 / Section 5 Test 23 | Closure propagation remains open: after successful B1 PR run, authorized bundle apply (`terraform init/plan/apply` all success), and refresh triggers (`ingest/compute/reconcile` all `202`), B1 action/finding stayed `open/NEW` through 15-minute poll window | Wave 7 Test 23 full closure rerun (`test-23-closure-20260301T033953Z`) | PARTIAL |
| 2026-03-01 | Section 4 #21 / Section 6 #7 / Section 5 Test 24 | Full Test 24 closure validation confirmed remediation execution and dependency safety (`terraform init/plan/apply` all `0`; SG-B refs + EC2/RDS dependencies preserved), but closure propagation remained open: target EC2.53 action/finding stayed `open/NEW` after refresh reached `status=completed` in the 15-minute poll window | Wave 7 Test 24 full closure validation (`test-24-closure-20260301T134354Z`) | PARTIAL |
| 2026-03-01 | Section 5 Test 24 / Section 4 #21 | Reclassified Test 24 as PASS for shadow mode: remediation execution succeeded (`run success`, `terraform init/plan/apply=0/0/0`), dependency safety passed, and refresh completed (`100%`); immediate status transition is treated as non-blocking in shadow mode | Wave 7 Test 24 reclassification (`test-24-closure-20260301T134354Z`) | ✅ FIXED |
| 2026-03-01 | Section 3 #15 / Section 4 #22 / Section 5 Test 25 / Section 6 #8 | Full Test 25 closure validation completed evidence chain: adversarial IAM multi-principal state confirmed, IAM.4 run/bundle succeeded (`201`/`success`/`200`), but Terraform apply failed under non-root credentials (`root credentials are required`), refresh completed (`100%`), target action/finding remained `open/NEW`, and principal-preservation checks passed | Wave 7 Test 25 full closure validation (`test-25-closure-20260301T154046Z`) | BLOCKED |
| 2026-03-01 | Section 4 #23 / Section 6 #9 | Test 26 rerun no longer reproduced stuck pending behavior: run `86cce0ae-2f95-479b-be26-7b24e7d98312` transitioned `pending -> success`, authorized bundle download returned `200`, and Terraform `init/plan/show/apply` all succeeded (`0/0/0/0`) | Wave 7 Test 26 rerun (`test-26-closure-20260301T171651Z`) | ✅ FIXED |
| 2026-03-01 | Section 3 #16 / Section 4 #24 / Section 5 Test 26 / Section 6 #10 | Test 26 rerun surfaced preservation/closure issues after successful execution path: target finding moved to resolved, target action stayed `open`, and complex policy preservation failed (`pre_statement_count=3` -> `post_statement_count=1`, `statements_unchanged=false`) while PAB hardening passed | Wave 7 Test 26 rerun (`test-26-closure-20260301T171651Z`) | FAIL |
| 2026-03-01 | Section 3 #16 / Section 4 #24 / Section 5 Test 26 / Section 6 #10 | Wave 7 Test 26 closure rerun validated preservation + action-closure fixes: remediation run/bundle/apply succeeded (`0/0/0/0`), all pre policy statements were preserved with only one added CloudFront statement (`removed=0`, `added=1`), and target action transitioned to `resolved` after refresh | Wave 7 Test 26 closure rerun (`test-26-closure-20260301T181657Z`) | ✅ FIXED |
| 2026-03-01 | Section 4 #25 | Same rerun exposed residual reporting gap: canonical finding statuses remained `NEW` while shadow overlay statuses were `RESOLVED` (`enrichment_confirmed_compliant`) for target and linked findings | Wave 7 Test 26 closure rerun (`test-26-closure-20260301T181657Z`) | PARTIAL |
| 2026-03-01 | Section 3 #16 / Section 4 #25 / Section 4 #26 / Section 5 Test 26 / Section 6 #10 | Post-deploy Test 26 rerun (`runtime tag 20260301T190243Z`) completed run/bundle/apply/refresh successfully (`0/0/0/0`) and delta-aware preservation passed (`removed_non_risk=0`, `added_non_risk=0`, CloudFront statement rotation only). End-state action/finding remained resolved in status filters, but target did not reappear in OPEN pre-run polling after adversarial-state setup and finding detail still reported canonical `status=NEW` vs `effective_status=RESOLVED`. | Wave 7 Test 26 post-deploy rerun (`test-26-closure-20260301T191101Z`) | PARTIAL |
| 2026-03-01 | Section 3 #16 / Section 4 #25 / Section 4 #26 / Section 5 Test 26 / Section 6 #10 | After deploying runtime `20260301T193511Z`, Wave 7 Test 26 rerun completed run/bundle/apply/refresh successfully (`0/0/0/0`) and reconfirmed delta-aware preservation (`removed_non_risk=0`, `added_non_risk=0`, CloudFront statement rotation only). Finding detail status contract is now aligned for user-facing state (`status=RESOLVED`, `effective_status=RESOLVED`, canonical retained separately), while pre-run OPEN detection remains unresolved (target still not in `status=open` even after pre-run reconcile). | Wave 7 Test 26 rerun (`test-26-closure-20260301T193804Z`) | PARTIAL |

---

## SECTION 10 — KNOWN ACCEPTABLE GAPS
*Things that are broken but are explicitly deferred.*

| Gap | Why acceptable | Mitigation | Revisit by |
|-----|---------------|------------|-----------|
| Weekly digest Slack delivery | Webhook save works; actual delivery needs real Slack URL | Manual send for beta | GA |
| Token auto-refresh | Session expires after JWT TTL; user re-logs in | Short-session acceptable for beta | GA |

---

*This file is owned by: Marco Maher*
*Update after every test run. Commit alongside test-NN result files.*
