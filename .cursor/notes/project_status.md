# Project Status

## Overview

| Section | Purpose |
|---------|---------|
| **High-Level Goal** | AWS Security Autopilot for SMB — A SaaS that operationalizes AWS-native security (Security Hub / GuardDuty / IAM Access Analyzer) by converting findings into prioritized actions, managing exceptions, executing hybrid remediation (safe direct fixes + IaC PR/patches), and generating audit-ready evidence packs (SOC 2 / ISO readiness). |
| **Current Phase** | MVP Build Plan (Phase 0 → Phase 1): Foundation + Read-only onboarding + Security Hub ingestion + basic Actions view. |
| **Infrastructure** | AWS hosting: ECS Fargate (API + Worker), RDS Postgres, SQS, S3 (exports), Secrets Manager, CloudWatch. Customer AWS integration via STS AssumeRole + ExternalId with separate ReadRole (required) and WriteRole (required at account connection). |
| **Known Blockers** | (1) Finalizing least-privilege IAM policies for ReadRole/WriteRole across regions/accounts. (2) ~~PR generation approach~~ — Implementation plan Step 9 specifies patch bundles with real Terraform/CloudFormation per action type. (3) Defining a minimal, safe auto-remediation allowlist and safety checks. |

## Product Definition

### Core Promise

**"Secure AWS quickly, stay secure with minimal weekly effort."**

### Core User Outcomes (what you sell)

- Faster time-to-secure (baseline enabled + tuned)
- Reduced noise (actions > raw findings)
- Fixes shipped (approved direct fixes + PR bundles)
- Compliance readiness (evidence pack + exception governance)

## System Architecture

### Control Plane (Your SaaS)

- Frontend: React / Next.js
- API: Python FastAPI
- DB: Postgres (RDS)
- Queue: SQS
- Workers: Python consumers (ingest, action compute, remediation, exports)
- Exports: S3 evidence bundles
- Observability: CloudWatch logs/metrics/alarms
- Secrets: Secrets Manager

### Customer AWS Data Plane

- ReadRole (required): ingest Security Hub (and minimal describe calls)
- WriteRole (required): limited to safe remediations only; required at account connection
- Access method: STS AssumeRole + ExternalId (no long-lived keys)

## MVP Scope

### MVP Includes (sellable)

- AWS account onboarding (ReadRole)
- Security Hub findings ingestion (start 1 region; expand)
- Action engine v1: dedupe + prioritize + "Top risks"
- Exceptions/suppressions with expiry + approvals
- Hybrid remediation:
  - **7 real action types** (3 direct fix + 4 PR bundle): S3 account-level, Security Hub, GuardDuty (direct fix); S3 bucket block, S3 bucket encryption, SG restrict, CloudTrail (PR bundle)
  - PR/patch bundle for most fixes
- Evidence export v1 (CSV/JSON zipped)

### MVP Excludes (initially)

- Deep container runtime security
- Advanced SIEM integrations
- High-risk auto-remediation without guardrails
- Broad multi-cloud CNAPP scope

## Remediation Strategy (Hybrid)

| Mode | Pros | Cons | Best For |
|------|------|------|----------|
| Direct Fix (approved) | Fastest value, strongest differentiation | Needs strict safety, fear of write access | Safe, idempotent remediations |
| PR / Patch Bundle | Safer, fits IaC workflows | Slower perceived value if PRs aren't merged | Medium/high-risk changes |

### Safe Direct-Fix Starter List (v1)

- Enable S3 Block Public Access (account-level)
- Enable Security Hub / GuardDuty (if disabled)
- (Optional) Restrict SG 0.0.0.0/0 on 22/3389 with allowlist + exemptions
- Everything else → PR/patch until proven safe

## Data Model (Core Tables)

| Table | Purpose |
|-------|---------|
| `tenants`, `users` | Multi-tenant auth + ownership |
| `aws_accounts` | account_id, role ARNs, regions, externalId |
| `findings` | normalized + raw Security Hub JSON |
| `actions` | deduped tasks derived from findings |
| `action_findings` | many-to-many mapping |
| `exceptions` | reason, expiry, approvals, scope |
| `remediation_runs` | mode, logs, outcome, artifacts URL |

## API Surface (MVP)

| Endpoint | Purpose |
|----------|---------|
| `POST /tenants/aws-accounts` | Register account + role ARNs |
| `POST /jobs/ingest` | Enqueue ingestion |
| `GET /findings` | List + filters |
| `GET /actions` | Prioritized action list |
| `POST /actions/{id}/exception` | Add/approve exception |
| `POST /actions/{id}/approve` | Approve remediation run |
| `GET /remediation-runs/{id}` | Run status + logs |
| `POST /exports/evidence` | Generate evidence pack |

## Roadmap & Milestones

### Phase 0 — Foundation

- Tenancy + auth
- Role assume utility + validation
- SQS + worker skeleton
- Postgres schema + migrations

**Done when:** you can connect an AWS account and verify STS assume-role.

### Phase 1 — Ingest + Visibility

- Pull Security Hub findings (1 region)
- Store + display findings
- Basic "Top risks" view

**Done when:** customer sees findings within minutes of connecting.

### Phase 2 — Actions + Exceptions

- Action grouping/dedupe
- Exceptions with expiry + approvals
- Weekly digest (email/Slack)

**Done when:** findings collapse into a manageable action list.

### Phase 3 — Hybrid Remediation v1

- Remediation runs + audit logs
- PR/patch bundle output
- 7 real action types (3 direct fix + 4 PR bundle) behind approval / PR bundle

**Done when:** approve → (fix or PR bundle) with before/after checks and logs.

### Phase 4 — Evidence + Billing

- Evidence pack export to S3
- Stripe billing + plan gates
- Pilot customer onboarding playbook

**Done when:** you can charge and deliver end-to-end.

## Security & Trust Requirements

| Requirement | Implementation |
|-------------|----------------|
| No long-lived AWS keys | STS AssumeRole + ExternalId |
| Least privilege | Separate ReadRole vs WriteRole, tight permissions |
| Auditability | Remediation run logs + approval records + exports |
| Idempotency | Safe to re-run jobs/remediations |
| Failure handling | Retries + DLQ for SQS + run status visible |
| Tenant isolation | Row-level access enforced in API |

## KPIs

### North Star

- Risk reduced per week (actions resolved weighted by severity)

### Supporting

- Time-to-secure (connect → baseline visible)
- Fix throughput (approved fixes/week)
- Exception expiry compliance
- False positive rate per rule
- Weekly active usage (digest opens, approvals)
- Churn / expansion (accounts added, compliance attach)

## Implementation steps (plan)

**Steps completed:**
- **Step 1** (AWS Account Connect + STS) — ✅ Done
- **Step 2** (SQS + Worker + Findings Ingestion) — ✅ Done
- **Step 2.7** (Multi-region ingestion) — ✅ Done (docstring, test N regions → N SQS messages)
- **Step 2B.1** (IAM Access Analyzer ingestion) — ✅ Done (source column, access_analyzer service + job, API ingest-access-analyzer, ReadRole permissions, findings API source filter)
- **Step 3** (UI Pages: Accounts → Findings → Top Risks) — ✅ Done
- **Step 4** (Auth, Sign Up, Login, Onboarding, User Management) — ✅ Done
- **Step 5** (Action Grouping + Dedupe) — ✅ Done
- **Step 6** (Exceptions + Expiry) — ✅ Done
- **Step 7** (Remediation Runs Model + PR Bundle Scaffold) — ✅ Done (replaced by Step 9 real IaC)
- **Step 8** (7 Real Action Types: Direct Fix + WriteRole) — ✅ Done
- **Step 9** (Real PR Bundle IaC per Action Type) — ✅ Done
- **Step 11.1** (Scheduled job: EventBridge/cron, payload per tenant) — ✅ Done (last_digest_sent_at, weekly_digest job, POST /api/internal/weekly-digest, DIGEST_CRON_SECRET)
- **Step 11.2** (Digest content: email subject/body, Slack blocks, View in app link) — ✅ Done (digest_content.py, expiring_exceptions in payload)
- **Step 11.3** (Email delivery: reuse email.py, optional preferences) — ✅ Done (send_weekly_digest, digest_enabled/digest_recipients, GET/PATCH digest-settings)
- **Step 11.4** (Slack delivery: webhook, tenant setting) — ✅ Done (slack_digest.py, slack_webhook_url/slack_digest_enabled, GET/PATCH slack-settings)
- **Step 11.5** (Frontend: Digest and Slack settings UI) — ✅ Done (Settings → Notifications tab: digest toggle/recipients, Slack webhook Configured/Change/Clear, Slack digest toggle)
- **Step 12.1** (Compliance pack contents: evidence + attestation + control mapping + auditor summary) — ✅ Done (compliance_pack_spec.py, builders, v1 control mapping)
- **Step 12.2** (Export type: evidence vs compliance; API and worker support) — ✅ Done (pack_type on API/worker/SQS; compliance pack zip adds exception_attestations, control_mapping, auditor_summary)
- **Step 12.3** (Control mapping data: v1 mapping table/config) — ✅ Done (control_mappings table + seed; build_control_mapping_rows from DB; GET/POST /api/control-mappings)
- **Step 13** (48h Baseline Report — lead magnet) — ✅ Done (13.1 spec + schema; 13.2 job + S3 + baseline_reports; 13.3 POST/GET API + email; 13.4 Settings UI + GTM playbook)

**Step 4 included:**
- User model extended with password_hash, role, onboarding_completed_at
- UserInvite model for email-based invitations
- Auth module with JWT sign/verify, bcrypt password hashing
- POST /api/auth/signup, POST /api/auth/login, GET /api/auth/me endpoints
- Optional auth on existing routers (backward compatible with tenant_id)
- Users API: list, invite, accept-invite, update me, delete user
- Email service for invite emails (logs in local mode)
- Frontend AuthContext with token persistence
- Login, signup, accept-invite pages
- 5-step onboarding wizard (External ID, connect account, ingest)
- Settings page with Team and Organization tabs
- Sidebar shows real tenant name and user when authenticated

**Next:** Step 10 (Evidence Export v1 — CSV/JSON zip to S3), Phase 4 (Evidence pack + Billing)

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Auto-remediation breaks prod | Approval required, safe list only, pre/post checks, allowlists |
| IAM permissions too broad | Start narrow, expand per feature, document every permission |
| "Just another dashboard" perception | Focus UI on actions + fixes + evidence, not raw findings |
| Slow value if PR-only | Hybrid: a few safe direct fixes to demonstrate immediate impact |
| Support load | Clear scope, runbooks, plan-based support boundaries |
