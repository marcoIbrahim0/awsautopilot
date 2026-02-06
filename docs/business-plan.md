# Business plan

## 1) Executive summary

**Product:** AWS Security Autopilot for SMB—turns AWS-native signals (Security Hub / GuardDuty / IAM Access Analyzer / optional Inspector) into prioritized actions, manages exceptions, ships safe remediations (direct fixes or IaC PRs), and produces audit-ready evidence packs for SOC 2 / ISO 27001 readiness.

**Primary buyer:** Founder/CTO or Head of Engineering at AWS-first SMBs who need security posture and compliance readiness without hiring a cloud security engineer.

**Core promise:** "Secure AWS quickly, stay secure with minimal weekly effort."
**Differentiator:** Not "more findings," but outcomes: fixes shipped + guardrails + proof.

## 2) Problem

SMB teams on AWS face three recurring issues:

- **Implementation gap:** They know they should enable best-practice services/controls, but don't execute consistently.

- **Operational gap:** They get flooded with findings; nobody owns tuning, exceptions, and follow-through.

- **Compliance gap:** Evidence collection for SOC 2/ISO is time-consuming; exceptions lack approvals/expiry; auditors need traceability.

AWS-native tooling improves visibility, but SMBs still struggle with day-2 operations and proof.

## 3) Solution
### What you deliver

- **Baseline enablement** (read-only onboarding + optional write role)

- **Action engine** (dedupe + prioritize + "what to do next")

- **Hybrid remediation**
  - Direct fixes for a small safe list (approved changes)
  - IaC PR / patch bundles for higher-risk fixes

- **Evidence packs**
  - Config snapshots, action history, approvals, exceptions with expiry, remediation run logs

- **The "productized service" wrapper** (optional but recommended early)
  - Offer onboarding as a paid implementation sprint, while your SaaS becomes the ongoing autopilot.

## 4) Target market and ICP
### Initial ICP (tight and winnable)

- AWS-first SaaS / B2B startups
- 1–20 AWS accounts (or 1 account with multiple envs)
- Need SOC 2 in the next 3–9 months
- IaC present (Terraform/CloudFormation) or willing to adopt minimal IaC workflow for fixes

### Avoid initially

- Regulated enterprises (heavy procurement)
- Teams requiring deep Kubernetes runtime security as day-1 (too broad)
- Highly customized landing zones where auto-remediation risk is high

## 5) Competitive landscape

You're positioned between:

- **AWS-native stack:** strong visibility, improving posture management
- **CNAPP leaders** (Wiz/Orca/etc.): broad detection and enterprise feature depth

Your wedge is operationalization for SMB:
- time-to-secure
- remediation-as-code / approved auto-fix
- evidence generation and exception governance

## 6) Differentiation and moat
### Moat #1: Remediation safety system

- approval workflow + scoped write permissions
- allowlists + "blast radius" checks
- idempotent remediations + audit logs + rollback guidance

### Moat #2: Evidence + exception governance

- expiring exceptions with approvals and rationale
- auditor-ready exports mapped to controls and changes over time

### Moat #3: Action abstraction layer

- stable "Actions" UX that hides noisy raw findings
- templates for the top SMB issues (S3, SGs, IAM hygiene, logging drift)

## 7) Packaging and pricing
### Structure

- One-time onboarding fee (implementation + baseline + tuning)
- Monthly subscription (autopilot + workflow + remediation + evidence)
- Compliance add-on (evidence + exception attestations + auditor exports)

### Practical SMB pricing (starting point)

**Onboarding:** $1.5k–$6k (single vs multi-account/org, IaC integration)

**Monthly tiers** (by accounts + included "approved fixes/month"):
- **Starter:** $399/mo (1 account, 10 fixes)
- **Growth:** $999/mo (up to 5 accounts, 40 fixes)
- **Scale:** $2,499/mo (up to 20 accounts, 120 fixes)

**Compliance pack add-on:** +$500–$1,500/mo (or one-time "SOC 2 sprint")

**Key rule:** price on accounts + fixes shipped + evidence, not "findings ingested."

## 8) Go-to-market plan
### Channel strategy (order)

1. **Founder-led outbound** (first 10–30 customers)
   - LinkedIn + targeted email: "SOC 2 in 3–9 months on AWS?"
   - Lead magnet: free read-only baseline scan → paid "Autopilot + fixes"

2. **AWS-focused MSP/MSSP partners**
   - You become their repeatable product; they bring pipeline

3. **AWS Marketplace** (after initial traction)
   - reduces procurement friction for AWS-native buyers

### Sales motion (simple)

20-min discovery → connect read-only role → 48h report → propose onboarding sprint → convert to monthly autopilot

## 9) Operations plan
### Customer success

- Default cadence: weekly digest + monthly posture review
- Support tiers: email/Slack, response-time targets (keep lightweight early)

### Incident handling

Runbooks for:
- failed remediations
- AWS permission issues
- false positives and suppression
- customer "break-glass" requests

## 10) Legal, risk, and trust

Key risks to manage explicitly:

- **Auto-remediation risk:** mitigate via approvals + safe list + allowlists
- **Access risk:** no long-lived keys; STS assume role + ExternalId
- **Liability:** contract language that you provide "best-effort automation," customer approves changes, and you keep detailed logs

## 11) Metrics and KPIs
### North-star metric

Risk reduced per week (actions resolved weighted by severity)

### Supporting KPIs

- Time-to-secure (onboarding → baseline active)
- % of actions auto-fixed vs PR-only
- Exception rate and expiry compliance
- False positive rate per rule
- Weekly active usage (digest opens, approvals)
- Churn and expansion (accounts added, compliance add-on attach)

## 12) Financial model (simple unit economics)

Track per-customer costs:
- AWS infra: ingestion + storage + exports
- Support time (most expensive early)
- Payment processing / marketplace fee

Target: keep your plan priced so that even with support you have positive gross margin.
