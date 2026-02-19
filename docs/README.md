# AWS Security Autopilot Documentation

**AWS Security Autopilot** is a SaaS platform that operationalizes AWS-native security services (Security Hub, GuardDuty, IAM Access Analyzer, Inspector) by converting findings into prioritized actions, managing exceptions, executing hybrid remediation (safe direct fixes + Infrastructure-as-Code PR bundles), and generating audit-ready evidence packs for SOC 2 / ISO compliance readiness.

## Quick Navigation

### For Developers
- **[Local Development Guide](local-dev/README.md)** — Set up your development environment, run the backend and worker locally, and execute tests
- **[API Reference](api/README.md)** — Complete REST API documentation with request/response schemas
- **[Data Model](data-model/README.md)** — Database schema, entity relationships, and data flow patterns
- **[Architectural Decisions](decisions/README.md)** — ADRs explaining key design choices

### For SaaS Owners / Operators
- **[Owner Deployment Guide](deployment/README.md)** — Step-by-step infrastructure deployment on AWS (ECS Fargate or Lambda)
- **[CI Dependency Governance Policy](deployment/ci-dependency-governance.md)** — Required checks, dependency lock/version policy, and vulnerability gates
- **[Owner-Side Architecture](architecture/owner/README.md)** — System architecture, backend services, AWS resources, and data flows
- **[Monitoring & Runbooks](runbooks/README.md)** — Operational procedures for incidents, DR, and queue management

### For Customers
- **[Customer Onboarding Guide](customer-guide/README.md)** — Account creation, AWS account connection, and feature walkthroughs
- **[Client-Side AWS Resources](architecture/client/README.md)** — What gets deployed in your AWS account and why

### For Auditors & Compliance
- **[Audit Remediation Package](audit-remediation/README.md)** — Architecture, security, implementation, and UX remediation plans
- **[Phase 4 Required Check Governance](audit-remediation/phase4-required-check-governance.md)** — Final branch-protection required checks matrix and governance baseline

---

## System Overview

### Control Plane (Your SaaS Infrastructure)

- **Frontend**: React/Next.js application
- **API**: Python FastAPI REST API (`backend/main.py`)
- **Worker**: Python SQS consumers (`worker/main.py`) for background job processing
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

### `/docs/architecture/owner/`
Technical reference for SaaS infrastructure:
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
- `README.md` — Overview
- `customer-resources.md` — What gets created per customer
- `naming-and-tagging.md` — Resource naming conventions
- `permissions-and-isolation.md` — IAM policies and security boundaries
- `teardown.md` — Safe decommissioning procedures

### `/docs/api/`
Complete API reference:
- `README.md` — Authentication, base URLs, error handling
- Domain-specific docs (`auth.md`, `aws-accounts.md`, `findings.md`, `actions.md`, `exceptions.md`, `remediation-runs.md`, `exports.md`, `baseline-report.md`, `users.md`, `reconciliation.md`, `control-plane.md`, `internal.md`, `saas-admin.md`)

### `/docs/data-model/`
Database schema and relationships:
- `README.md` — Entity overview
- `schema.md` — ER diagram and table descriptions
- `tenancy-and-accounts.md` — Tenant/account relationships
- `audit-and-evidence.md` — Audit logs and compliance evidence

### `/docs/local-dev/`
Local development setup:
- `README.md` — Overview
- `environment.md` — `.env` setup, Python dependencies
- `backend.md` — Running FastAPI locally
- `worker.md` — Running worker against SQS
- `tests.md` — Running pytest and interpreting results
- `frontend.md` — Frontend development (if applicable)

### `/docs/decisions/`
Architectural Decision Records (ADRs):
- `README.md` — ADR conventions
- Individual ADRs (e.g., `0001-multi-tenant-single-db.md`, `0002-hybrid-remediation-strategy.md`)

### `/docs/runbooks/`
Operational procedures:
- `README.md` — Runbook index
- Links to existing runbooks (DR, edge incidents, queue quarantine, control-plane monitoring)

### `/docs/audit-remediation/`
Audit remediation program documentation (preserved from existing structure):
- `README.md` — Program overview
- `00-program-plan.md` — Program sequencing and governance
- `01-priority-backlog.md` — Issue backlog
- `02-architecture-plan.md` — Architecture remediation tasks
- `03-security-plan.md` — Security remediation tasks
- `04-implementation-plan.md` — Implementation remediation tasks
- `05-ux-plan.md` — UX remediation tasks
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
