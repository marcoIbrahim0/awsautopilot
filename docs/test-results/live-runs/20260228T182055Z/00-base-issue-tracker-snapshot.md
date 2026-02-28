# QA Issue Tracker — AWS Security Autopilot
**Base file for all test run outputs**
Environment: https://dev.valensjewelry.com
Test account: maromaher54@gmail.com
Last updated: _(fill in after each run)_

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
| Wave 1 | 01 | — | — | — | — | — |
| Wave 2 | 02–04 | — | — | — | — | — |
| Wave 3 | 05–08 | — | — | — | — | — |
| Wave 4 | 09–12 | — | — | — | — | — |
| Wave 5 | 13–16 | — | — | — | — | — |
| Wave 6 | 17–22 | — | — | — | — | — |
| Wave 7 | 23–28 | — | — | — | — | — |
| Wave 8 | 29–33 | — | — | — | — | — |
| Wave 9 | 34–35 | — | — | — | — | — |
| **TOTAL** | **35** | — | — | — | — | — |

---

## SECTION 1 — MISSING ENDPOINTS
*Endpoints the frontend calls that returned 404. These are build gaps.*

| # | Endpoint | HTTP Method | Called From | Test Found | Severity | Status |
|---|----------|------------|-------------|-----------|----------|--------|
| 1 | `/api/auth/password` | PUT | Settings → Security | Test 04 | 🔴 BLOCKING | — |
| 2 | `/api/auth/refresh` | POST | AuthContext auto-refresh | Test 03 | 🔴 BLOCKING | — |
| 3 | `/api/users/invite-info` | GET | Accept-invite page | Test 08 | 🟠 HIGH | — |
| 4 | `/api/users/me/slack-settings` | GET/PATCH | Notifications tab | Test 19 | 🟡 MEDIUM | — |
| 5 | `/api/users/me/digest-settings` | GET/PATCH | Notifications tab | Test 19 | 🟡 MEDIUM | — |
| 6 | `/api/audit-log` | GET | Settings → Audit | Test 32 | 🟠 HIGH | — |
| 7 | `/api/baseline-report/{id}/data` | GET | In-app report viewer | Test 22 | 🔵 LOW | — |
| 8 | `/api/internal/weekly-digest` | POST | Scheduler | Test 20 | 🟡 MEDIUM | — |
| 9 | `/api/internal/compute` | POST | Scheduler | Test 20 | 🟡 MEDIUM | — |
| 10 | `/api/actions/reconcile` | POST | Post-remediation drawer | Test 16 | 🟡 MEDIUM | — |
| 11 | `/api/remediation-runs/group-pr-bundle` | POST | PR bundle page | Test 17 | 🟠 HIGH | — |
| 12 | `/api/aws/accounts/{id}/control-plane-readiness` | GET | Onboarding wizard | Test 06 | 🟡 MEDIUM | — |
| 13 | `/api/aws/accounts/{id}/onboarding-fast-path` | POST | Onboarding wizard | Test 06 | 🟡 MEDIUM | — |
| 14 | `/api/aws/accounts/{id}/ingest-sync` | POST | Accounts page | Test 29 | 🟡 MEDIUM | — |

> **After each run:** Delete rows that now return non-404. Add new rows for newly discovered 404s.

---

## SECTION 2 — FRONTEND WIRING GAPS
*API returns a response but the shape doesn't match what the component needs to render.*

| # | Test | Component | Field the UI needs | Field the API returns | Visible breakage | Status |
|---|------|-----------|-------------------|----------------------|-----------------|--------|
| 1 | Test 02 | Signup form | `token` at top-level | nested at `data.token` | User stuck after signup | — |
| 2 | Test 03 | AuthContext | `user.role` | role absent from `/me` response | Role-based UI never renders | — |
| 3 | Test 06 | Onboarding wizard | per-service `status` field | flat boolean or missing | Check indicators all show red | — |
| 4 | Test 09 | Ingest progress bar | `percent_complete` | absent or null | Progress bar stuck at 0% | — |
| 5 | Test 09 | Ingest progress bar | `estimated_time_remaining` | absent | ETA never shows | — |
| 6 | Test 10 | Finding card | `aws_service` or `service` | absent on some findings | Service badge blank | — |
| 7 | Test 10 | Finding card | `action_type` | absent on some findings | Action button doesn't render | — |
| 8 | Test 13 | Action drawer | `what_is_wrong` | absent | Explanation section blank | — |
| 9 | Test 13 | Action drawer | `what_the_fix_does` | absent | Fix description blank | — |
| 10 | Test 15 | Run progress panel | `current_step` | absent | Step label never updates | — |
| 11 | Test 22 | Reports page | `download_url` on report | absent until polled | Download button never appears | — |
| 12 | Test 29 | Accounts page | `last_synced_at` | absent or null | Last-scanned date blank | — |

> **After each run:** Mark rows ✅ FIXED when confirmed. Add new rows for newly found mismatches.

---

## SECTION 3 — SECURITY ISSUES
*Any finding that could expose data or allow unauthorized access. Review every run.*

| # | Test | Severity | Issue | Expected behavior | Observed | Status |
|---|------|----------|-------|------------------|----------|--------|
| 1 | Test 12 | 🔴 BLOCKING | Cross-tenant finding access returns 200 | 403 or 404 | TBD | — |
| 2 | Test 12 | 🔴 BLOCKING | Cross-tenant account access returns 200 | 403 or 404 | TBD | — |
| 3 | Test 12 | 🔴 BLOCKING | Cross-tenant ingest trigger returns 200 | 403 or 404 | TBD | — |
| 4 | Test 19 | 🔴 BLOCKING | SSRF via Slack webhook URL (non-hooks.slack.com accepted) | 400 | TBD | — |
| 5 | Test 30 | 🟠 HIGH | Login endpoint not rate-limited after N attempts | 429 after threshold | TBD | — |
| 6 | Test 30 | 🟠 HIGH | No `Retry-After` header on 429 response | Header present | TBD | — |
| 7 | Test 31 | 🟠 HIGH | Non-admin can invite users | 403 | TBD | — |
| 8 | Test 31 | 🟠 HIGH | Non-admin can delete accounts | 403 | TBD | — |
| 9 | Test 18 | 🟠 HIGH | PR bundle ZIP downloadable without auth token | 401 | TBD | — |
| 10 | Test 08 | 🟠 HIGH | Invite token reuse not blocked | 400 or 410 | TBD | — |
| 11 | Test 32 | 🟡 MEDIUM | Audit records contain secrets (token, role_arn, password) | No secrets in payload | TBD | — |
| 12 | Test 32 | 🟡 MEDIUM | Non-admin user can read audit log | 403 | TBD | — |

> **Any 🔴 BLOCKING security issue must halt go-live. Fix before resuming the test cycle.**

---

## SECTION 4 — BUGS & BROKEN FLOWS
*Things that work structurally but produce wrong behavior.*

| # | Test | Flow | What breaks | Root cause hypothesis | Priority | Status |
|---|------|------|------------|----------------------|----------|--------|
| 1 | Test 03 | Post-logout token check | Token still valid after logout | Session not invalidated server-side | 🔴 BLOCKING | — |
| 2 | Test 04 | Password change | 404 on PUT /api/auth/password | Endpoint not built | 🔴 BLOCKING | — |
| 3 | Test 11 | Multi-value filter | `severity=CRITICAL,HIGH` returns wrong set | Comma-separated not parsed | 🟠 HIGH | — |
| 4 | Test 11 | Pagination | Page 1 and page 2 contain duplicate IDs | Missing stable sort on paginated query | 🟠 HIGH | — |
| 5 | Test 14 | Duplicate run guard | Second run on same action returns 200 instead of 409 | No idempotency check | 🟠 HIGH | — |
| 6 | Test 16 | Recompute | `/api/actions/compute` returns 404 | Endpoint not built | 🟠 HIGH | — |
| 7 | Test 17 | PR bundle group | `/api/remediation-runs/group-pr-bundle` returns 404 | Endpoint not built | 🟠 HIGH | — |
| 8 | Test 18 | ZIP contents | Terraform file contains PLACEHOLDER values | Templating not substituting real resource IDs | 🟠 HIGH | — |
| 9 | Test 20 | Internal digest | Correct user token gets 200 on internal endpoint | Missing auth guard on `/api/internal/*` | 🔴 BLOCKING | — |
| 10 | Test 22 | Baseline report | Second report not rate-limited (no 429) | Rate-limit not implemented | 🟡 MEDIUM | — |
| 11 | Test 06 | Invite DB query | DB model path wrong in Python helper | Model import path mismatch | 🔵 LOW | — |
| 12 | Test 33 | PR proof C2 | No Terraform plan timestamp in README | Template doesn't include plan metadata | 🟠 HIGH | — |
| 13 | Test 33 | PR proof C5 | No preserved-config statement in B-series README | README template missing preservation section | 🟠 HIGH | — |

---

## SECTION 5 — ADVERSARIAL TEST RESULTS (Tests 23–28)
*Fill in after each Wave 7 run.*

| Test | Resource type | Group A detected | Blast radius correct | Group B false-positive-free | Config preserved | Result |
|------|--------------|-----------------|---------------------|-----------------------------|-----------------|--------|
| 23 | S3 blast radius | — | — | — | N/A | — |
| 24 | SG dependency chain | — | — | — | N/A | — |
| 25 | IAM multi-principal | — | — | — | N/A | — |
| 26 | Complex S3 policy | — | N/A | — | — | — |
| 27 | Mixed SG rules | — | N/A | — | — | — |
| 28 | IAM inline + managed | — | N/A | — | — | — |

---

## SECTION 6 — PARTIAL IMPLEMENTATIONS
*Endpoints that exist and respond but are incomplete or stub-level.*

| # | Endpoint | What works | What's missing | Test | Status |
|---|----------|-----------|----------------|------|--------|
| 1 | `/api/aws/accounts/{id}/service-readiness` | Returns 200 | Per-service status fields missing | Test 06 | — |
| 2 | `/api/findings/grouped` | Returns 200 | Group keys not stable across requests | Test 10 | — |
| 3 | `/api/exports` | Creates export | `download_url` never populated | Test 21 | — |
| 4 | `/api/baseline-report` | Creates report | In-app `/data` sub-endpoint 404 | Test 22 | — |
| 5 | `/api/remediation-runs/{id}/execution` | Returns 200 | Step log array always empty | Test 15 | — |
| 6 | `/api/auth/forgot-password` | Returns 200 | Does not always return 200 (leaks user existence) | Test 04 | — |

---

## SECTION 7 — ENVIRONMENT & INFRASTRUCTURE NOTES
*One-time issues that are setup-related, not product bugs.*

| # | Test | Note | Action needed | Status |
|---|------|------|---------------|--------|
| 1 | Test 01 | NEXT_PUBLIC_API_URL vs same-domain routing unclear | Confirm in next.config.js | — |
| 2 | Test 05 | TEST_ACCOUNT_ID not in 08-deployment-report.md | Marco to confirm and add | — |
| 3 | Test 07 | UserInvite DB model path may differ from example | Confirm Python import path | — |
| 4 | Test 20 | INTERNAL_SECRET not found in expected .env paths | Locate and document actual path | — |
| 5 | Test 30 | Rate limit window duration unknown | Check middleware config | — |

---

## SECTION 8 — GO-LIVE BLOCKERS CHECKLIST
*Every item here must be ✅ before go-live is approved.*

### 🔴 Critical — must fix before any user touches production

- [ ] **T12-1** Cross-tenant data isolation confirmed across findings, accounts, runs
- [ ] **T12-3** Cross-tenant ingest trigger blocked (403/404)
- [ ] **T19-4** SSRF via Slack webhook — non-hooks.slack.com domain rejected
- [ ] **T20-9** `/api/internal/*` routes protected from user-token access
- [ ] **T03-1** Token invalidated server-side on logout
- [ ] **T14-5** Duplicate run guard returns 409 (idempotency)

### 🟠 High — fix before go-live, workaround required otherwise

- [ ] **T04-2** PUT `/api/auth/password` endpoint built and working
- [ ] **T16-6** POST `/api/actions/compute` endpoint built and working
- [ ] **T17-7** POST `/api/remediation-runs/group-pr-bundle` endpoint built and working
- [ ] **T30-5** Login rate-limiting enforced (429 after threshold)
- [ ] **T31-7** Non-admin invite blocked (403)
- [ ] **T31-8** Non-admin account delete blocked (403)
- [ ] **T18-8** PR bundle ZIP requires auth to download
- [ ] **T08-10** Invite token reuse blocked after acceptance
- [ ] **T11-3** Multi-value severity filter works correctly
- [ ] **T11-4** Pagination returns no duplicate IDs

### 🟡 Medium — fix before first paying customer

- [ ] **T06** Per-service status fields in service-readiness response
- [ ] **T21** Evidence export `download_url` populated correctly
- [ ] **T09** `percent_complete` present in ingest-progress response
- [ ] **T19** Slack webhook settings persist correctly
- [ ] **T22** Baseline report second-request rate-limited
- [ ] **T32** Audit log inaccessible to non-admin roles
- [ ] **T33** PR bundle README includes Terraform plan timestamp (C2)
- [ ] **T33** PR bundle README includes preservation statement (C5)

---

## SECTION 9 — CHANGELOG
*Track when issues are fixed so you know what to re-test.*

| Date | Fixed issue # | Fix description | Re-tested in | Result |
|------|--------------|----------------|-------------|--------|
| — | — | — | — | — |

---

## SECTION 10 — KNOWN ACCEPTABLE GAPS
*Things that are broken but are explicitly deferred.*

| Gap | Why acceptable | Mitigation | Revisit by |
|-----|---------------|------------|-----------|
| In-app report viewer (`/data` endpoint) | PDF download works; viewer is a V2 feature | Provide download link | V1.1 |
| Weekly digest Slack delivery | Webhook save works; actual delivery needs real Slack URL | Manual send for beta | GA |
| Token auto-refresh | Session expires after JWT TTL; user re-logs in | Short-session acceptable for beta | GA |

---

*This file is owned by: Marco Maher*
*Update after every test run. Commit alongside test-NN result files.*
