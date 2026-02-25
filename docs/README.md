# AWS Security Autopilot Documentation

**AWS Security Autopilot** is a SaaS platform that operationalizes AWS-native security services (Security Hub, GuardDuty, IAM Access Analyzer, Inspector) by converting findings into prioritized actions, managing exceptions, executing hybrid remediation (safe direct fixes + Infrastructure-as-Code PR bundles), and generating audit-ready evidence packs for SOC 2 / ISO compliance readiness.

## Quick Navigation

### For Developers
- **[Local Development Guide](local-dev/README.md)** — Set up your development environment, run the backend and worker locally, and execute tests
- **[Prod Readiness](prod-readiness/README.md)** — Production-hardening notes and verification checklists for remediation artifact generation
- **[API Reference](api/README.md)** — Complete REST API documentation with request/response schemas
- **[Data Model](data-model/README.md)** — Database schema, entity relationships, and data flow patterns
- **[Architectural Decisions](decisions/README.md)** — ADRs explaining key design choices
> ⚠️ Status: Planned — not yet implemented
> `docs/api/`, `docs/data-model/`, and `docs/decisions/` are planned documentation areas.

### For SaaS Owners / Operators
- **[Owner Deployment Guide](deployment/README.md)** — Step-by-step infrastructure deployment on AWS (ECS Fargate or Lambda)
- **[Production Deployment Profile](Production/deployment.md)** — High-importance deployment command set: low-cost standard, scale-up, rollout, rollback
- **[CI Dependency Governance Policy](deployment/ci-dependency-governance.md)** — Required checks, dependency lock/version policy, and vulnerability gates
- **[Owner-Side Architecture](architecture/owner/README.md)** — System architecture, backend services, AWS resources, and data flows
- **[Deployer Runbook (Phase 1-3)](audit-remediation/deployer-runbook-phase1-phase3.md)** — End-to-end SaaS deployer sequence (`.env.ops` -> AWS serverless deploy -> worker enablement -> Cloudflare custom domain -> verification)
- **[Monitoring & Runbooks](runbooks/README.md)** — Operational procedures for incidents, DR, and queue management
- **[Reconciliation Quality Review](reconciliation_quality_review.md)** — Control-by-control audit of inventory collectors, reconciliation logic quality, and prioritized fixes
> ⚠️ Status: Planned — not yet implemented
> `docs/architecture/owner/` remains a planned documentation area.

### For Customers
- **[Customer Onboarding Guide](customer-guide/README.md)** — Account creation, AWS account connection, and feature walkthroughs
- **[Client-Side AWS Resources](architecture/client/README.md)** — What gets deployed in your AWS account and why
> ⚠️ Status: Planned — not yet implemented
> `docs/architecture/client/` is a planned documentation area.

### For Auditors & Compliance
- **[Audit Remediation Package](audit-remediation/README.md)** — Architecture, security, implementation, and UX remediation plans
- **[Phase 4 Required Check Governance](audit-remediation/phase4-required-check-governance.md)** — Final branch-protection required checks matrix and governance baseline

---

## System Overview

### Control Plane (Your SaaS Infrastructure)

- **Frontend**: React/Next.js application
- **API**: Python FastAPI REST API (`backend/main.py`)
- **Worker**: Python SQS consumers (`backend/workers/main.py`) for background job processing (legacy import/entrypoint compatibility remains via `worker` shim package)
- **Database**: PostgreSQL (RDS) with async SQLAlchemy 2.0
- **Queues**: Amazon SQS (4 main queues + 4 DLQs + 1 quarantine queue)
  - `security-autopilot-ingest-queue` — Legacy ingestion jobs
  - `security-autopilot-events-fastlane-queue` — Near-real-time control-plane events
  - `security-autopilot-inventory-reconcile-queue` — Inventory reconciliation jobs
  - `security-autopilot-export-report-queue` — Evidence/compliance pack exports and baseline reports
  - `security-autopilot-contract-quarantine-queue` — Malformed/unknown job payloads
- **Storage**: Amazon S3 buckets
  - Export bucket (`S3_EXPORT_BUCKET`) — Evidence packs, baseline reports
  - Support bucket (`S3_SUPPORT_BUCKET`) — Admin→tenant support files
  - Template bucket — Versioned CloudFormation templates
- **Observability**: CloudWatch (logs, metrics, alarms)
- **Secrets**: AWS Secrets Manager (`DATABASE_URL`, `JWT_SECRET`, `CONTROL_PLANE_EVENTS_SECRET`)
- **Runtime Env Model (split by service)**:
  - Backend runtime: `backend/.env`
  - Worker runtime: `backend/workers/.env`
  - Frontend public vars: `frontend/.env`
  - Deploy/ops scripts: `config/.env.ops`
  - Root `.env` is backup-only and not a runtime source
  - Cross-reference: [Local Development Environment Setup](local-dev/environment.md)
- **Deployment Options**:
  - **ECS Fargate** (recommended for dev/prod) — ALB, persistent connections, easier debugging
  - **Lambda** (serverless alternative) — HTTP API + SQS triggers, cost-efficient scaling

### Customer AWS Data Plane

- **ReadRole** (`SecurityAutopilotReadRole`) — Required; STS AssumeRole + ExternalId for Security Hub/GuardDuty/Access Analyzer/Inspector read access
- **WriteRole** (`SecurityAutopilotWriteRole`) — Optional; Limited write permissions for safe direct remediations
- **Control Plane Forwarder** (optional) — EventBridge rule + API Destination for near-real-time control-plane events

### Core Features

- **Multi-tenant SaaS** — Row-level tenant isolation, JWT-based authentication
- **AWS Account Onboarding** — CloudFormation-based role deployment, STS validation
- **Findings Ingestion** — Security Hub, IAM Access Analyzer, Inspector (multi-region)
- **Action Engine** — Deduplication, prioritization, grouping
- **Exceptions Management** — Expiry-based suppressions with approvals
- **Hybrid Remediation**:
  - **Direct Fix** — Safe, idempotent remediations (S3 account-level public access block, Security Hub/GuardDuty enablement)
  - **PR Bundle** — Terraform/CloudFormation patches for medium/high-risk changes
- **Evidence & Compliance Exports** — SOC 2 / ISO-ready evidence packs
- **48h Baseline Report** — Lead magnet report generation
- **Weekly Digest** — Email/Slack notifications
- **Control-Plane Pipeline** — Shadow mode → authoritative control promotion
- **Inventory Reconciliation** — Periodic sweeps of EC2, S3, CloudTrail, Config, IAM, EBS, RDS, EKS, SSM, GuardDuty

---

## Documentation Structure

### `/docs/deployment/`
Owner-facing deployment guides:
- `README.md` — Overview and deployment path selection
- `prerequisites.md` — AWS accounts, IAM permissions, tools
- `infrastructure-ecs.md` — ECS Fargate deployment (CloudFormation/Terraform)
- `infrastructure-serverless.md` — Lambda serverless deployment
- `database.md` — RDS Postgres setup, migrations, backups
- `domain-dns.md` — Route 53, ACM certificates, ALB/CloudFront
- `secrets-config.md` — Environment variables and Secrets Manager
- `ci-cd.md` — CI/CD pipelines, deployment workflows, rollback procedures
- `ci-dependency-governance.md` — Dependency version policy, lockfile rules, vulnerability gate checks
- `monitoring-alerting.md` — CloudWatch setup, alarms, readiness checks

### `/docs/customer-guide/`
Non-technical customer onboarding and usage:
- `README.md` — Product overview
- `account-creation.md` — Signup, login, onboarding wizard
- `connecting-aws.md` — AWS account connection steps
- `features-walkthrough.md` — Page-by-page feature guide
- `team-management.md` — User invites, roles, notifications
- `billing.md` — Subscription and billing (current vs planned)
- `troubleshooting.md` — FAQs and common issues
> ⚠️ Status: Planned — not yet implemented
> `features-walkthrough.md`, `team-management.md`, and `billing.md` are planned but not present yet.

### `/docs/architecture/owner/`
Technical reference for SaaS infrastructure:
> ⚠️ Status: Planned — not yet implemented
- `README.md` — Architecture overview
- `system-architecture.md` — High-level component diagram
- `backend-services.md` — FastAPI routers, worker jobs, services
- `aws-resources.md` — Complete AWS resource catalog
- `auth-and-tenancy.md` — JWT auth, user roles, tenant isolation
- `data-flows.md` — Sequence diagrams for core operations
- `control-plane.md` — Control-plane pipeline details
- `billing-and-plans.md` — Billing implementation (current vs planned)
- `frontend-overview.md` — Frontend routing and API integration

### `/docs/architecture/client/`
Customer-side AWS resources:
> ⚠️ Status: Planned — not yet implemented
- `README.md` — Overview
- `customer-resources.md` — What gets created per customer
- `naming-and-tagging.md` — Resource naming conventions
- `permissions-and-isolation.md` — IAM policies and security boundaries
- `teardown.md` — Safe decommissioning procedures

### `/docs/api/`
Complete API reference:
> ⚠️ Status: Planned — not yet implemented
- `README.md` — Authentication, base URLs, error handling
- Domain-specific docs (`auth.md`, `aws-accounts.md`, `findings.md`, `actions.md`, `exceptions.md`, `remediation-runs.md`, `exports.md`, `baseline-report.md`, `users.md`, `reconciliation.md`, `control-plane.md`, `internal.md`, `saas-admin.md`)

### `/docs/data-model/`
Database schema and relationships:
> ⚠️ Status: Planned — not yet implemented
- `README.md` — Entity overview
- `schema.md` — ER diagram and table descriptions
- `tenancy-and-accounts.md` — Tenant/account relationships
- `audit-and-evidence.md` — Audit logs and compliance evidence

### `/docs/local-dev/`
Local development setup:
- `README.md` — Overview
- `environment.md` — Split env-file setup, Python dependencies
- `backend.md` — Running FastAPI locally
- `worker.md` — Running worker against SQS
- `tests.md` — Running pytest and interpreting results
- `frontend.md` — Frontend development (if applicable)

### `/docs/prod-readiness/`
Production-readiness implementation notes and validation records:
- `01-discovery.md` — Discovery contract and normalization rules for control/action inventory validation
- `README.md` — PR bundle artifact generation readiness contract, unsupported-case error model, and test verification matrix
- `important-to-do.md` — High-priority follow-up checklist for rollout monitoring and release-readiness validation
- `06-task1-file-map.md` — Candidate inventory of control/action/ID definition files grouped by confidence
- `06-control-action-inventory.md` — Consolidated control/action inventory used as scenario and architecture planning input
- `07-task1-input-validation.md` — Input validation summary for control/action coverage constraints and scenario requirements
- `07-task2-arch1-scenario.md` — Architecture 1 business scenario, tier narrative, and control coverage split plan
- `07-task3-arch2-scenario.md` — Architecture 2 business scenario, tier narrative, and remaining-control coverage split plan
- `07-task3-control-coverage-validation.md` — Cross-architecture control assignment validation (full coverage, no overlap)
- `07-architecture-design.md` — Canonical Architecture 1/2 resource design tables (groups, tiers, tags, dependencies, and PR-proof targets)
- `07-task4-a-series-resources.md` — A1/A2/A3 adversarial resource definitions for blast-radius-safe remediation behavior tests
- `07-task5-b-series-resources.md` — B1/B2/B3 adversarial resource definitions with preserve-vs-remediate Terraform plan expectations
- `08-task1-resource-inventory.md` — Architecture resource-inventory extraction, dependency ordering, adversarial registry, and validation flags for script-prep
- `08-task8-coverage-matrix.md` — Control-level Group A/B/C coverage matrix plus PR proof validation checklist and pass/fail summary
- `08-task4-reset-arch1.sh` — Standalone Architecture 1 reset commands that reintroduce adversarial misconfiguration states after remediation validation
- `08-task6-teardown-arch1-groupA.sh` — Architecture 1 Group A-only teardown in reverse dependency order scoped to `TestGroup=detection`
- `08-task6-teardown-arch1-groupB.sh` — Architecture 1 Group B-only teardown in reverse dependency order scoped to `TestGroup=negative`
- `08-task6-teardown-arch1-full.sh` — Architecture 1 full teardown in exact reverse dependency order across all groups
- `08-task7-teardown-arch2-groupA.sh` — Architecture 2 Group A-only teardown using the Architecture 2 delete-order dependency guard for `arch2_eks_cluster_c` before role deletion
- `08-task7-teardown-arch2-groupB.sh` — Architecture 2 Group B-only teardown for `arch2_mixed_policy_role_b3`
- `08-task7-teardown-arch2-full.sh` — Architecture 2 full teardown in exact `08-task1-resource-inventory.md` delete order across Group A, Group B, and Group C
- `08-deployment-scripts.md` — Compiled deployment and reset script bundle for Architecture 1 and Architecture 2
- `08-teardown-scripts.md` — Compiled teardown script bundle with Group A/B and full teardown variants for both architectures
- `08-coverage-matrix.md` — Published coverage matrix and PR proof checklist copied from Task 8 output
- `08-summary.md` — Final compilation summary with architecture resource counts, coverage counts, and residual risk list
- `root-credentials-required-iam-root-access-key-absent.md` — Manual/high-risk runbook for `iam_root_access_key_absent` with root-credential approvals, execution, rollback, and audit evidence capture

### `/docs/Production/`
High-importance operator documentation:
> ⚠️ Change Control: This folder is not routine-editable. Update only when explicitly commanded.
- `deployment.md` — Standard low-cost deployment profile, scale-up command, rollout procedure, and rollback command set

### `/docs/decisions/`
Architectural Decision Records (ADRs):
> ⚠️ Status: Planned — not yet implemented
- `README.md` — ADR conventions
- Individual ADRs (e.g., `0001-multi-tenant-single-db.md`, `0002-hybrid-remediation-strategy.md`)

### `/docs/runbooks/`
Operational procedures:
- `README.md` — Runbook index
- `no-ui-pr-bundle-agent.md` — Fully automated no-UI PR-bundle validation flow
- `e2e_no_ui_agent_debug_reference.md` — Known no-UI E2E issues, S0–S6 code mapping, and required code-level fixes

### `/docs/audit-remediation/`
Audit remediation program documentation (preserved from existing structure):
- `README.md` — Program overview
- `00-program-plan.md` — Program sequencing and governance
- `01-priority-backlog.md` — Issue backlog
- `02-architecture-plan.md` — Architecture remediation tasks
- `03-security-plan.md` — Security remediation tasks
- `04-implementation-plan.md` — Implementation remediation tasks
- `05-ux-plan.md` — UX remediation tasks
- `deployer-runbook-phase1-phase3.md` — Deployer-grade runbook for Phases 1-3 with exact deployment and verification commands
- `phase4-required-check-governance.md` — Required CI checks and branch-protection governance baseline
- Phase closure checklists

---

## Getting Started

**New to the project?** Start here:

1. **Developers**: Read [Local Development Guide](local-dev/README.md) to set up your environment
2. **SaaS Owners**: Read [Owner Deployment Guide](deployment/README.md) to deploy infrastructure
3. **Customers**: Read [Customer Onboarding Guide](customer-guide/README.md) to get started
4. **Auditors**: Review [Audit Remediation Package](audit-remediation/README.md) for compliance evidence

---

## Key Concepts

- **Multi-tenancy**: Single PostgreSQL database with row-level isolation by `tenant_id`
- **STS AssumeRole**: No long-lived AWS keys; customer roles assumed via STS + ExternalId
- **Hybrid Remediation**: Direct fixes for safe operations, PR bundles for IaC workflows
- **Control-Plane Pipeline**: Shadow mode for testing, authoritative controls for production
- **Queue Contracts**: Schema-versioned SQS messages with quarantine for malformed payloads
- **Evidence Packs**: SOC 2 / ISO-ready exports with findings, actions, exceptions, remediation runs

---

## Version History

See [CHANGELOG.md](CHANGELOG.md) for a complete history of major features and milestones.

---

## Support

- **Technical Issues**: Check [Troubleshooting Guide](customer-guide/troubleshooting.md) or [Runbooks](runbooks/README.md)
- **API Questions**: See [API Reference](api/README.md)
- **Deployment Help**: See [Owner Deployment Guide](deployment/README.md)
