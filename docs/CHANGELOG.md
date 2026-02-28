# Changelog

All notable changes to AWS Security Autopilot are documented in this file. This changelog is retroactively compiled from the project's implementation history.

## [Unreleased]

### Planned
- Step 10: Evidence Export v1 (CSV/JSON zip to S3)
- Phase 4: Evidence pack + Billing (Stripe integration, plan gates)

---

## [Phase 3] — Resilience & Security Hardening

### Added
- **Phase 3 Architecture Resilience** (`ARC-008`, `ARC-009`)
  - Edge protection (CloudFront, WAF) — `infrastructure/cloudformation/edge-protection.yaml`
  - DR backup controls — `infrastructure/cloudformation/dr-backup-controls.yaml`
  - Synthetic alarm drills and failure injection tests
  - Load testing and resilience validation
- **Phase 3 Security Hardening** (`SEC-008`, `SEC-010`)
  - Security hardening measures and validation
  - Security evidence collection scripts — `scripts/collect_phase3_security_evidence.py`
- **Architecture Evidence Collection** — `scripts/collect_phase3_architecture_evidence.py`
- **Deployment Scripts**:
  - `scripts/deploy_phase3_architecture.sh`
  - `scripts/deploy_phase3_security.sh`
- **Tests**:
  - `tests/test_cloudformation_phase3_resilience.py`
  - `tests/test_security_phase3_hardening.py`
  - `tests/test_saas_system_health_phase3.py`

### Documentation
- `docs/edge-protection-architecture.md`
- `docs/disaster-recovery-runbook.md`
- `docs/edge-traffic-incident-runbook.md`
- `docs/audit-remediation/phase3-architecture-closure-checklist.md`
- `docs/audit-remediation/phase3-security-closure-checklist.md`

---

## [Phase 2] — Architecture Remediation

### Added
- **Phase 2 Architecture Remediation** (`ARC-002` through `ARC-007`)
  - Architecture improvements and validation
  - Architecture evidence collection — `scripts/collect_phase2_architecture_evidence.py`
- **Deployment Script** — `scripts/deploy_phase2_architecture.sh`
- **Tests**:
  - `tests/test_cloudformation_phase2_reliability.py`
  - `tests/test_control_plane_readiness.py`

### Documentation
- `docs/audit-remediation/phase2-architecture-closure-checklist.md`

---

## [Step 13] — 48h Baseline Report (Lead Magnet)

### Added
- **Baseline Report Generation**
  - `baseline_reports` table schema
  - `worker/jobs/generate_baseline_report.py` — Baseline report job
  - `backend/services/baseline_report_service.py` — Report generation logic
  - `backend/routers/baseline_report.py` — POST/GET API endpoints
  - S3 export bucket integration for report storage
  - Email delivery for completed reports
- **Frontend Integration**
  - Settings UI for baseline report generation
- **GTM Playbook** — `docs/gtm-baseline-report-playbook.md`

### Documentation
- `docs/baseline-report-spec.md` — Baseline report specification

---

## [Step 12] — Compliance Pack Export

### Added
- **Compliance Pack Contents**
  - `backend/services/compliance_pack_spec.py` — Compliance pack builders
  - Exception attestations
  - Control mapping integration
  - Auditor summary generation
- **Export Type Support**
  - `pack_type` field (evidence vs compliance) on API, worker, and SQS
  - Compliance pack ZIP includes `exception_attestations`, `control_mapping`, `auditor_summary`
- **Control Mapping Data**
  - `control_mappings` table + seed data
  - `build_control_mapping_rows` from database
  - `GET/POST /api/control-mappings` endpoints

---

## [Step 11] — Weekly Digest (Email & Slack)

### Added
- **Scheduled Job Infrastructure**
  - `last_digest_sent_at` field on `tenants` table
  - `worker/jobs/weekly_digest.py` — Weekly digest job
  - `POST /api/internal/weekly-digest` endpoint (secret auth via `DIGEST_CRON_SECRET`)
  - EventBridge/cron integration for scheduled execution
- **Digest Content**
  - `backend/services/digest_content.py` — Email subject/body, Slack blocks
  - "View in app" link generation
  - Expiring exceptions included in payload
- **Email Delivery**
  - `send_weekly_digest` function (reuses `email.py`)
  - `digest_enabled` / `digest_recipients` tenant settings
  - `GET/PATCH /api/users/me/digest-settings` endpoints
- **Slack Delivery**
  - `backend/services/slack_digest.py` — Slack webhook integration
  - `slack_webhook_url` / `slack_digest_enabled` tenant settings
  - `GET/PATCH /api/users/me/slack-settings` endpoints
- **Frontend Integration**
  - Settings → Notifications tab
  - Digest toggle and recipient management
  - Slack webhook configuration (Configured/Change/Clear)
  - Slack digest toggle

---

## [Step 9] — Real PR Bundle IaC per Action Type

### Added
- **Terraform/CloudFormation PR Bundles**
  - Real Infrastructure-as-Code patches per action type
  - `backend/services/pr_bundle.py` — PR bundle generation
  - Replaces Step 7 scaffold with production-ready IaC
- **PR Bundle Execution**
  - `remediation_run_executions` table for plan/apply phases
  - `POST /api/remediation-runs/{id}/executions/{exec_id}/plan` — Terraform plan
  - `POST /api/remediation-runs/{id}/executions/{exec_id}/apply` — Terraform apply
  - SaaS-managed Terraform runner (optional, via `SAAS_BUNDLE_EXECUTOR_ENABLED`)
  - Bundle reporting tokens for downloaded bundle execution tracking

---

## [Step 8] — 7 Real Action Types (Direct Fix + WriteRole)

### Added
- **Direct Fix Actions** (3 types)
  - S3 account-level public access block
  - Security Hub enablement
  - GuardDuty enablement
- **PR Bundle Actions** (4 types)
  - S3 bucket public access block
  - S3 bucket encryption
  - Security group restriction (0.0.0.0/0 on 22/3389)
  - CloudTrail configuration
- **WriteRole Integration**
  - WriteRole required at account connection
  - `worker/services/direct_fix.py` — Direct remediation implementations
  - `backend/services/remediation_runtime_checks.py` — Pre/post remediation checks

---

## [Step 7] — Remediation Runs Model + PR Bundle Scaffold

### Added
- **Remediation Runs**
  - `remediation_runs` table schema
  - `POST /api/remediation-runs` — Create remediation run
  - `POST /api/remediation-runs/{id}/approve` — Approve run
  - `POST /api/remediation-runs/{id}/execute` — Execute run
  - `GET /api/remediation-runs/{id}` — Run status and logs
  - PR bundle scaffold (later replaced by Step 9 real IaC)

---

## [Step 6] — Exceptions + Expiry

### Added
- **Exceptions Management**
  - `exceptions` table schema
  - `POST /api/exceptions` — Create exception
  - `GET /api/exceptions` — List exceptions
  - `DELETE /api/exceptions/{id}` — Delete exception
  - Expiry-based suppressions with approvals
  - Exception expiry tracking and notifications

---

## [Step 5] — Action Grouping + Dedupe

### Added
- **Action Engine**
  - `actions` table schema
  - `action_findings` many-to-many mapping
  - `action_groups` table for persistent grouping
  - `action_group_memberships` table
  - `action_group_runs` table for group execution
  - `POST /api/actions/compute` — Trigger action computation
  - `GET /api/actions` — List prioritized actions
  - `GET /api/action-groups` — List action groups
  - Deduplication and prioritization logic

---

## [Step 4] — Auth, Sign Up, Login, Onboarding, User Management

### Added
- **Authentication**
  - `users` table extended with `password_hash`, `role`, `onboarding_completed_at`
  - `user_invites` table for email-based invitations
  - `backend/auth.py` — JWT sign/verify, bcrypt password hashing
  - `POST /api/auth/signup` — Create tenant + admin user
  - `POST /api/auth/login` — Authenticate
  - `GET /api/auth/me` — Current user + tenant
- **User Management**
  - `GET /api/users` — List users (tenant-scoped)
  - `POST /api/users/invite` — Invite user
  - `GET/POST /api/users/accept-invite` — Accept invite
  - `PATCH /api/users/me` — Update current user
  - `DELETE /api/users/{id}` — Delete user
- **Email Service**
  - `backend/services/email.py` — Invite email delivery (logs in local mode)
- **Frontend Integration**
  - AuthContext with token persistence
  - Login, signup, accept-invite pages
  - 5-step onboarding wizard (External ID, connect account, ingest)
  - Settings page with Team and Organization tabs
  - Sidebar shows real tenant name and user when authenticated

---

## [Step 3] — UI Pages: Accounts → Findings → Top Risks

### Added
- **Frontend Pages**
  - Accounts page
  - Findings view with filters
  - Actions/Top Risks view

---

## [Step 2B.1] — IAM Access Analyzer Ingestion

### Added
- **Access Analyzer Support**
  - `source` column on `findings` table
  - `worker/services/access_analyzer.py` — Access Analyzer API wrapper
  - `worker/jobs/ingest_access_analyzer.py` — Access Analyzer ingestion job
  - `POST /api/aws/accounts/{id}/ingest-access-analyzer` endpoint
  - ReadRole permissions for Access Analyzer
  - Findings API source filter

---

## [Step 2.7] — Multi-Region Ingestion

### Added
- **Multi-Region Support**
  - Docstring and test for N regions → N SQS messages
  - Per-account region configuration
  - Multi-region ingestion job handling

---

## [Step 2] — SQS + Worker + Findings Ingestion

### Added
- **SQS Infrastructure**
  - `infrastructure/cloudformation/sqs-queues.yaml` — Queue definitions
  - `security-autopilot-ingest-queue` + DLQ
  - `security-autopilot-events-fastlane-queue` + DLQ
  - `security-autopilot-inventory-reconcile-queue` + DLQ
  - `security-autopilot-export-report-queue` + DLQ
  - `security-autopilot-contract-quarantine-queue`
  - IAM managed policies (`SecurityAutopilotApiSqsSendPolicy`, `SecurityAutopilotWorkerSqsConsumePolicy`)
  - CloudWatch alarms for queue depth, age, DLQ ingress
- **Worker Infrastructure**
  - `worker/main.py` — SQS polling loop, job routing, graceful shutdown
  - `worker/jobs/ingest_findings.py` — Security Hub ingestion
  - `worker/services/security_hub.py` — Security Hub API wrapper
  - Contract violation quarantine for malformed payloads
- **Findings Storage**
  - `findings` table schema
  - Normalized + raw Security Hub JSON storage
- **Queue Utilities**
  - `backend/utils/sqs.py` — SQS message building, queue region parsing, job type constants

---

## [Step 1] — AWS Account Connect + STS

### Added
- **AWS Account Registration**
  - `aws_accounts` table schema
  - `POST /api/aws/accounts` — Register account
  - `GET /api/aws/accounts` — List accounts
  - `POST /api/aws/accounts/{id}/validate` — Validate role access
  - `POST /api/aws/accounts/{id}/ingest` — Trigger ingestion
  - `GET /api/aws/accounts/{id}/ping` — Ping account
- **STS AssumeRole**
  - `backend/services/aws.py` — STS AssumeRole utility
  - ExternalId per tenant for security
  - ReadRole/WriteRole trust policy validation
- **CloudFormation Templates**
  - `infrastructure/cloudformation/read-role-template.yaml` — Customer ReadRole template
  - `infrastructure/cloudformation/write-role-template.yaml` — Customer WriteRole template
  - `infrastructure/cloudformation/control-plane-forwarder-template.yaml` — EventBridge forwarder

---

## [Phase 0] — Foundation

### Added
- **Multi-Tenancy**
  - `tenants` table schema
  - `users` table schema
  - Row-level tenant isolation
- **Database**
  - PostgreSQL (RDS) setup
  - Alembic migrations
  - Async SQLAlchemy 2.0
  - `backend/database.py` — Database connection management
- **API Foundation**
  - FastAPI application (`backend/main.py`)
  - Router mounting structure
  - Health/readiness endpoints (`/health`, `/ready`)
  - CORS middleware
- **Configuration**
  - `backend/config.py` — Pydantic settings from environment variables
  - `.env` file support for local development
- **Migration Guard**
  - `backend/services/migration_guard.py` — Fail-fast if DB revision != Alembic head

---

## Additional Features & Infrastructure

### Control-Plane Pipeline
- **Control-Plane Events**
  - `control_plane_events` table
  - `control_plane_event_ingest_status` table
  - `worker/jobs/ingest_control_plane_events.py` — Event ingestion job
  - `POST /api/control-plane/events` — Event ingestion endpoint
  - `POST /api/internal/control-plane-events` — Internal event ingestion
  - Shadow mode (`CONTROL_PLANE_SHADOW_MODE=true`) for testing
  - Authoritative controls promotion (`CONTROL_PLANE_AUTHORITATIVE_CONTROLS`)
- **Inventory Reconciliation**
  - `inventory_assets` table
  - `control_plane_reconcile_jobs` table
  - `tenant_reconcile_runs` table
  - `tenant_reconcile_run_shards` table
  - `aws_account_reconcile_settings` table
  - `worker/services/inventory_reconcile.py` — Inventory collection (EC2, S3, CloudTrail, Config, IAM, EBS, RDS, EKS, SSM, GuardDuty)
  - `worker/jobs/reconcile_inventory_shard.py` — Shard processing
  - `worker/jobs/reconcile_inventory_global_orchestration.py` — Global orchestration
  - `worker/jobs/reconcile_recently_touched_resources.py` — Recently touched resources
  - `POST /api/reconciliation/recently-touched` — Tenant-triggered reconciliation
  - `POST /api/reconciliation/global` — Global reconciliation
  - `POST /api/internal/reconciliation/schedule-tick` — Reconciliation scheduler tick
  - Reconciliation scheduler template (`reconcile-scheduler-template.yaml`)

### Inspector Ingestion
- **Inspector Support**
  - `worker/services/inspector.py` — Inspector API wrapper
  - `worker/jobs/ingest_inspector.py` — Inspector ingestion job

### Action Groups
- **Persistent Action Groups**
  - `action_groups` table
  - `action_group_memberships` table
  - `action_group_runs` table
  - `action_group_action_state` table
  - `action_group_run_result` table
  - `GET /api/action-groups/{id}/runs` — List group runs
  - `POST /api/action-groups/{id}/runs` — Create group run
- **Backfill Jobs**
  - `worker/jobs/backfill_finding_keys.py` — Finding key backfill
  - `worker/jobs/backfill_action_groups.py` — Action group backfill

### Exports & Evidence
- **Evidence Exports**
  - `evidence_exports` table
  - `worker/jobs/evidence_export.py` — Export generation job
  - `backend/services/evidence_export.py` — Evidence pack generation
  - `POST /api/exports` — Create export
  - `GET /api/exports` — List exports
  - `GET /api/exports/{id}` — Get export detail
  - S3 presigned URL generation (`backend/services/s3_presigned.py`)

### SaaS Admin
- **Admin Endpoints**
  - `backend/routers/saas_admin.py` — SaaS admin router
  - `GET /api/saas/system-health` — System health
  - `GET /api/saas/control-plane/slo` — Control-plane SLO metrics
  - `GET /api/saas/tenants` — List tenants
  - `GET /api/saas/tenants/{id}` — Tenant overview
  - Tenant management endpoints
- **Support Files**
  - `support_files` table
  - `support_notes` table
  - `backend/routers/support_files.py` — Support file downloads

### Remediation Safety
- **Runtime Checks**
  - `backend/services/remediation_runtime_checks.py` — Pre/post remediation checks
  - Safety model documentation (`docs/remediation-safety-model.md`)

### Deployment Infrastructure
- **ECS Fargate**
  - `infrastructure/cloudformation/saas-ecs-dev.yaml` — ECS deployment template
  - `infrastructure/terraform/saas-ecs-dev/` — Terraform alternative
  - `scripts/deploy_saas_ecs_dev.sh` — Deployment script
- **Lambda Serverless**
  - `infrastructure/cloudformation/saas-serverless-httpapi.yaml` — Lambda deployment template
  - `backend/lambda_handler.py` — Lambda API entrypoint
  - `worker/lambda_handler.py` — Lambda worker entrypoint
  - `scripts/deploy_saas_serverless.sh` — Deployment script
- **Container Images**
  - `Containerfile` — Main container image
  - `Containerfile.lambda-api` — Lambda API image
  - `Containerfile.lambda-worker` — Lambda worker image

### Testing
- **Test Suite**
  - `tests/test_health_readiness.py` — Health/readiness checks
  - `tests/test_worker_polling.py` — Worker polling tests
  - `tests/test_worker_main_contract_quarantine.py` — Contract quarantine tests
  - `tests/test_reconcile_inventory_global_orchestration_worker.py` — Inventory reconciliation tests
  - `tests/test_internal_inventory_reconcile.py` — Internal reconciliation tests
  - `tests/test_sqs_utils.py` — SQS utility tests

### Documentation
- `docs/archive/2026-02-doc-cleanup/implementation-plan.md` — Full implementation plan (archived snapshot)
- `docs/remediation-safety-model.md` — Remediation safety model
- `docs/connect-write-role.md` — Write role connection guide
- `docs/control-plane-event-monitoring.md` — Control-plane event monitoring
- `docs/queue-contract-quarantine-runbook.md` — Queue contract quarantine runbook
- `docs/eventbridge-target-dlq-replay-runbook.md` — EventBridge DLQ replay runbook
- `docs/cloudformation-templates-s3-cloudfront.md` — Template distribution guide
- `docs/audit-remediation/` — Audit remediation package

---

## Format

This changelog follows a reverse-chronological format, with the most recent changes at the top. Each entry includes:
- **Version/Phase/Step** — Major milestone identifier
- **Added** — New features, endpoints, tables, infrastructure
- **Changed** — Modifications to existing functionality
- **Deprecated** — Features marked for removal
- **Removed** — Deleted features
- **Fixed** — Bug fixes
- **Security** — Security-related changes
