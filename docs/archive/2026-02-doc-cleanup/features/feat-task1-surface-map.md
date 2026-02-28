SECTION 1 — FRONTEND SURFACE MAP

| Route | Page File Path | Primary purpose in one sentence |
|-------|---------------|--------------------------------|
| `/` | `frontend/src/app/page.tsx` | Root entrypoint that routes users to onboarding, findings, or login based on auth/onboarding state. |
| `/accept-invite` | `frontend/src/app/accept-invite/page.tsx` | Accepts an invitation token and completes invited-user account activation. |
| `/accounts` | `frontend/src/app/accounts/page.tsx` | Manages connected AWS accounts, role status, and ingestion/reconciliation actions. |
| `/actions` | `frontend/src/app/actions/page.tsx` | Legacy actions route that currently redirects users to `/findings`. |
| `/actions/[id]` | `frontend/src/app/actions/[id]/page.tsx` | Legacy action-detail route that currently redirects users to `/findings`. |
| `/actions/group` | `frontend/src/app/actions/group/page.tsx` | Shows grouped actions for batch review and grouped remediation/PR-bundle execution. |
| `/admin/control-plane` | `frontend/src/app/admin/control-plane/page.tsx` | SaaS-admin operations page for global control-plane health, lag, and queue/event status. |
| `/admin/control-plane/[tenantId]` | `frontend/src/app/admin/control-plane/[tenantId]/page.tsx` | Tenant-level control-plane drill-down for shadow/authoritative status and event diagnostics. |
| `/admin/tenants` | `frontend/src/app/admin/tenants/page.tsx` | SaaS-admin tenant list/search page for selecting a tenant to inspect or support. |
| `/admin/tenants/[tenantId]` | `frontend/src/app/admin/tenants/[tenantId]/page.tsx` | SaaS-admin tenant detail workspace with tabs for overview, users, accounts, findings, actions, runs, exports, notes, and files. |
| `/audit-log` | `frontend/src/app/audit-log/page.tsx` | Displays tenant audit events and filtering around security operations changes. |
| `/baseline-report` | `frontend/src/app/baseline-report/page.tsx` | Requests, monitors, and views 48-hour baseline report outputs and recommendations. |
| `/exceptions` | `frontend/src/app/exceptions/page.tsx` | Lists and manages remediation exceptions including expiry and approval status. |
| `/exports` | `frontend/src/app/exports/page.tsx` | Creates and tracks evidence/compliance exports and related report requests. |
| `/findings` | `frontend/src/app/findings/page.tsx` | Primary findings workbench with filters, source controls, refresh, and action orchestration entrypoints. |
| `/findings/[id]` | `frontend/src/app/findings/[id]/page.tsx` | Displays full details for a single finding and related metadata. |
| `/landing` | `frontend/src/app/landing/page.tsx` | Public marketing page describing product value, flow, trust model, and conversion CTAs. |
| `/login` | `frontend/src/app/login/page.tsx` | Auth login page for existing users. |
| `/onboarding` | `frontend/src/app/onboarding/page.tsx` | Guided onboarding wizard for role setup, account validation, and first ingestion checks. |
| `/pr-bundles` | `frontend/src/app/pr-bundles/page.tsx` | Shows PR bundle run history and links to create a new bundle. |
| `/pr-bundles/create` | `frontend/src/app/pr-bundles/create/page.tsx` | Builder page for selecting actions/accounts/filters before generating a PR bundle. |
| `/pr-bundles/create/summary` | `frontend/src/app/pr-bundles/create/summary/page.tsx` | Final review page summarizing selected actions and executing grouped PR-bundle runs. |
| `/remediation-runs/[id]` | `frontend/src/app/remediation-runs/[id]/page.tsx` | Run detail page for remediation execution status, logs, and artifacts. |
| `/reset-password` | `frontend/src/app/reset-password/page.tsx` | Completes password reset for users with reset tokens. |
| `/session-expired` | `frontend/src/app/session-expired/page.tsx` | Session timeout page that prompts secure re-authentication. |
| `/settings` | `frontend/src/app/settings/page.tsx` | Tenant settings hub for notifications, Slack, team/org controls, and control mappings. |
| `/signup` | `frontend/src/app/signup/page.tsx` | User registration page for creating a new tenant account. |
| `/support-files` | `frontend/src/app/support-files/page.tsx` | Tenant support file listing page for shared file retrieval and status visibility. |
| `/top-risks` | `frontend/src/app/top-risks/page.tsx` | Risk summary dashboard highlighting highest-priority exposure metrics and trends. |

SECTION 2 — BACKEND API SURFACE MAP

| Router File | URL Prefix | Number of endpoints | Primary domain |
|-------------|-----------|---------------------|---------------|
| `backend/routers/action_groups.py` | `/api/action-groups` | 4 | Grouped action retrieval and group-level execution workflow. |
| `backend/routers/actions.py` | `/api/actions` | 6 | Action listing/detail and remediation option/approval entrypoints. |
| `backend/routers/auth.py` | `/api/auth` | 6 | Authentication, signup/login, identity lookup, and auth lifecycle operations. |
| `backend/routers/aws_accounts.py` | `/api/aws/accounts` | 16 | AWS account onboarding, validation, role/connectivity checks, and ingest triggers. |
| `backend/routers/baseline_report.py` | `/api/baseline-report` | 3 | Baseline report request, list, and detail retrieval. |
| `backend/routers/control_mappings.py` | `/api/control-mappings` | 3 | Compliance/control mapping management for evidence/compliance features. |
| `backend/routers/control_plane.py` | `/api/control-plane` | 1 | Control-plane event ingestion endpoint for forwarder pipeline intake. |
| `backend/routers/exceptions.py` | `/api/exceptions` | 4 | Exception create/list/update/expiry governance. |
| `backend/routers/exports.py` | `/api/exports` | 3 | Evidence/compliance export creation, listing, and download access. |
| `backend/routers/findings.py` | `/api/findings` | 3 | Findings list/detail operations and related finding-level access patterns. |
| `backend/routers/internal.py` | `/api/internal` | 10 | Internal scheduled/admin-only enqueue and reconciliation orchestration endpoints. |
| `backend/routers/meta.py` | `/api/meta` | 1 | Service metadata/readiness utility endpoint(s). |
| `backend/routers/reconciliation.py` | `/api/reconciliation` | 6 | Reconciliation health, status, and reconciliation-control APIs. |
| `backend/routers/remediation_runs.py` | `/api/remediation-runs` | 12 | Remediation run lifecycle, status, logs, artifact and PR-execution controls. |
| `backend/routers/saas_admin.py` | `/api/saas` | 25 | SaaS-admin cross-tenant operations, diagnostics, and support tooling APIs. |
| `backend/routers/support_files.py` | `/api/support-files` | 2 | Support file upload/list/download orchestration for tenant support workflows. |
| `backend/routers/users.py` | `/api/users` | 10 | Tenant user management, invites, role updates, and self-profile operations. |

SECTION 3 — WORKER AND JOB SURFACE MAP

| Job Name | File Path | Trigger type (API-enqueued / scheduled / event-driven) |
|---------|----------|-------------------------------------------------------|
| `worker_queue_poller` | `backend/workers/main.py` | event-driven |
| `worker_lambda_handler` | `backend/workers/lambda_handler.py` | event-driven |
| `ingest_findings` | `backend/workers/jobs/ingest_findings.py` | API-enqueued |
| `ingest_access_analyzer` | `backend/workers/jobs/ingest_access_analyzer.py` | API-enqueued |
| `ingest_inspector` | `backend/workers/jobs/ingest_inspector.py` | API-enqueued |
| `ingest_control_plane_events` | `backend/workers/jobs/ingest_control_plane_events.py` | event-driven |
| `compute_actions` | `backend/workers/jobs/compute_actions.py` | API-enqueued |
| `reconcile_inventory_global_orchestration` | `backend/workers/jobs/reconcile_inventory_global_orchestration.py` | scheduled |
| `reconcile_inventory_shard` | `backend/workers/jobs/reconcile_inventory_shard.py` | event-driven |
| `reconcile_recently_touched_resources` | `backend/workers/jobs/reconcile_recently_touched_resources.py` | scheduled |
| `remediation_run` | `backend/workers/jobs/remediation_run.py` | API-enqueued |
| `execute_pr_bundle_plan` | `backend/workers/jobs/remediation_run_execution.py` | API-enqueued |
| `execute_pr_bundle_apply` | `backend/workers/jobs/remediation_run_execution.py` | API-enqueued |
| `generate_export` | `backend/workers/jobs/evidence_export.py` | API-enqueued |
| `generate_baseline_report` | `backend/workers/jobs/generate_baseline_report.py` | API-enqueued |
| `weekly_digest` | `backend/workers/jobs/weekly_digest.py` | scheduled |
| `backfill_finding_keys` | `backend/workers/jobs/backfill_finding_keys.py` | API-enqueued |
| `backfill_action_groups` | `backend/workers/jobs/backfill_action_groups.py` | API-enqueued |

SECTION 4 — AWS INTEGRATION SURFACE MAP

| AWS Service | Integration type (read / write / both) | Used for | File(s) that implement it |
|------------|--------------------------------------|---------|--------------------------|
| AWS STS | both | Assuming customer roles and validating caller identity during onboarding/reconciliation. | `backend/services/aws.py`, `backend/services/aws_account_orchestration.py`, `backend/workers/jobs/reconcile_inventory_global_orchestration.py` |
| Amazon SQS | both | Enqueueing jobs from API and consuming/deleting worker messages across job queues. | `backend/utils/sqs.py`, `backend/workers/main.py`, `backend/routers/internal.py`, `backend/routers/aws_accounts.py` |
| Amazon S3 | both | Export/baseline artifact storage, support files, and template/source artifact handling. | `backend/services/evidence_export.py`, `backend/services/baseline_report_service.py`, `backend/routers/support_files.py`, `backend/routers/exports.py` |
| AWS Security Hub | both | Ingesting findings, readiness checks, and enabling Security Hub as a remediation path. | `backend/workers/services/security_hub.py`, `backend/workers/services/direct_fix.py`, `backend/services/aws_account_orchestration.py` |
| Amazon GuardDuty | both | Detector/readiness checks and GuardDuty enablement remediation. | `backend/workers/services/inventory_reconcile.py`, `backend/workers/services/direct_fix.py`, `backend/services/aws_account_orchestration.py` |
| IAM Access Analyzer | read | Analyzer/finding ingestion into the platform action pipeline. | `backend/workers/services/access_analyzer.py`, `backend/workers/jobs/ingest_access_analyzer.py`, `backend/services/aws_account_orchestration.py` |
| Amazon Inspector v2 | read | Inspector finding ingestion for vulnerability/control visibility. | `backend/workers/services/inspector.py`, `backend/workers/jobs/ingest_inspector.py`, `backend/services/aws_account_orchestration.py` |
| Amazon EC2 | both | Security group, EBS encryption, snapshot controls, inventory reads, and direct fixes. | `backend/workers/services/inventory_reconcile.py`, `backend/workers/services/direct_fix.py`, `backend/services/remediation_runtime_checks.py` |
| Amazon S3 Control | both | Account-level S3 public-access-block evaluation and remediation. | `backend/workers/services/direct_fix.py`, `backend/services/remediation_runtime_checks.py`, `backend/workers/services/inventory_reconcile.py` |
| AWS Config | read | Recorder/delivery posture checks and reconciliation visibility. | `backend/workers/services/inventory_reconcile.py`, `backend/services/aws_account_orchestration.py` |
| AWS CloudTrail | read | Trail/logging posture evaluation and reconciliation checks. | `backend/workers/services/inventory_reconcile.py`, `backend/services/tenant_reconciliation.py` |
| AWS Systems Manager (SSM) | both | Document-sharing control visibility and PR-bundle generation for remediation workflows. | `backend/workers/services/inventory_reconcile.py`, `backend/services/pr_bundle.py` |
| AWS Identity and Access Management (IAM) | both | Root-key/account posture checks and role/policy lifecycle handling. | `backend/workers/services/inventory_reconcile.py`, `backend/services/aws_account_cleanup.py`, `backend/services/tenant_reconciliation.py` |
| Amazon RDS | read | RDS public-access and encryption posture as inventory-only controls. | `backend/workers/services/inventory_reconcile.py`, `backend/services/tenant_reconciliation.py` |
| Amazon EKS | read | EKS public-endpoint posture as inventory-only control signal. | `backend/workers/services/inventory_reconcile.py`, `backend/services/tenant_reconciliation.py` |
| AWS KMS | read | Encryption key validation checks for encryption-related remediation/runtime checks. | `backend/services/remediation_runtime_checks.py` |
| AWS CloudFormation | both | Deploying/validating customer role stacks and template lifecycle handling. | `backend/routers/aws_accounts.py`, `backend/services/cloudformation_templates.py` |
| Amazon EventBridge | both | Control-plane event forwarding and scheduled reconciliation/digest invocations. | `infrastructure/cloudformation/control-plane-forwarder-template.yaml`, `infrastructure/cloudformation/reconcile-scheduler-template.yaml` |
| Amazon CloudWatch | both | Health/queue metrics checks and alarm resources for forwarder, scheduler, queues, and DR. | `backend/services/health_checks.py`, `infrastructure/cloudformation/sqs-queues.yaml`, `infrastructure/cloudformation/control-plane-forwarder-template.yaml` |
| AWS Backup | both | DR backup vault/plan/selection and restore-governance controls. | `infrastructure/cloudformation/dr-backup-controls.yaml` |
| AWS WAFv2 | both | Edge protection (managed rules, IP allow/rate limits) for public API surface. | `infrastructure/cloudformation/edge-protection.yaml` |
| AWS Lambda | both | API/worker serverless runtime and SQS event-source processing. | `infrastructure/cloudformation/saas-serverless-httpapi.yaml`, `backend/workers/lambda_handler.py` |

SECTION 5 — INFRASTRUCTURE SURFACE MAP

| Component | Type | File(s) | Purpose |
|-----------|------|---------|---------|
| Serverless runtime stack | CloudFormation stack | `infrastructure/cloudformation/saas-serverless-httpapi.yaml` | Runs API Gateway HTTP API + Lambda API/worker runtime with queue event source mappings. |
| Serverless build stack | CloudFormation stack | `infrastructure/cloudformation/saas-serverless-build.yaml` | Provisions build-time ECR/S3/CodeBuild resources for container image pipeline. |
| Queue and DLQ stack | CloudFormation stack | `infrastructure/cloudformation/sqs-queues.yaml` | Provides ingest/events/reconcile/export queues, DLQs, quarantine queue, and IAM queue policies. |
| Control-plane forwarder | CloudFormation stack | `infrastructure/cloudformation/control-plane-forwarder-template.yaml` | Deploys customer-side EventBridge rule and API Destination to push control-plane events into SaaS. |
| Reconciliation scheduler | CloudFormation stack | `infrastructure/cloudformation/reconcile-scheduler-template.yaml` | Schedules recurring global inventory reconciliation calls to internal SaaS endpoints. |
| Customer read-role provisioning | CloudFormation stack | `infrastructure/cloudformation/read-role-template.yaml` | Creates customer ReadRole trust/policies for ingestion and readiness checks. |
| Customer write-role provisioning | CloudFormation stack | `infrastructure/cloudformation/write-role-template.yaml` | Creates customer WriteRole for approved direct-fix remediations. |
| Edge protection | CloudFormation stack | `infrastructure/cloudformation/edge-protection.yaml` | Adds WAF ACL/rate limiting and alarm guardrails for public API endpoints. |
| DR backup controls | CloudFormation stack | `infrastructure/cloudformation/dr-backup-controls.yaml` | Implements backup vault/plan/selection plus recovery/restore governance and alarms. |
| ECS dev runtime stack | CloudFormation stack | `infrastructure/cloudformation/saas-ecs-dev.yaml` | Alternative runtime with VPC + ALB + ECS Fargate API/worker services and runtime secrets wiring. |
| ECS dev IaC module | Terraform module | `infrastructure/terraform/saas-ecs-dev/main.tf`, `infrastructure/terraform/saas-ecs-dev/network.tf`, `infrastructure/terraform/saas-ecs-dev/ecs.tf`, `infrastructure/terraform/saas-ecs-dev/alb.tf` | Terraform-based deployment path for VPC/network, ECS services, ALB, IAM, and queue wiring. |
| Finding scenario harness | Terraform scenario suite | `infrastructure/finding-scenarios/**/*.tf`, `infrastructure/finding-scenarios/README.md` | Creates controlled misconfiguration scenarios used for detection/remediation validation. |

SECTION 6 — READING LIST FOR WAVE 2

FOR TASK 2 (frontend features):
  Priority 1 files: [`frontend/src/app/findings/page.tsx`, `frontend/src/app/accounts/page.tsx`, `frontend/src/app/onboarding/page.tsx`, `frontend/src/app/actions/group/page.tsx`, `frontend/src/app/exports/page.tsx`, `frontend/src/app/settings/page.tsx`, `frontend/src/app/pr-bundles/page.tsx`, `frontend/src/app/pr-bundles/create/page.tsx`, `frontend/src/app/pr-bundles/create/summary/page.tsx`, `frontend/src/app/remediation-runs/[id]/page.tsx`]
  Priority 2 files: [`frontend/src/app/top-risks/page.tsx`, `frontend/src/app/exceptions/page.tsx`, `frontend/src/app/baseline-report/page.tsx`, `frontend/src/app/support-files/page.tsx`, `frontend/src/app/admin/tenants/page.tsx`, `frontend/src/app/admin/tenants/[tenantId]/page.tsx`, `frontend/src/app/admin/control-plane/page.tsx`, `frontend/src/app/admin/control-plane/[tenantId]/page.tsx`, `frontend/src/lib/api.ts`, `frontend/src/contexts/AuthContext.tsx`]

FOR TASK 3 (backend API features):
  Priority 1 files: [`backend/main.py`, `backend/routers/aws_accounts.py`, `backend/routers/findings.py`, `backend/routers/actions.py`, `backend/routers/action_groups.py`, `backend/routers/remediation_runs.py`, `backend/routers/exports.py`, `backend/routers/exceptions.py`, `backend/routers/reconciliation.py`, `backend/routers/internal.py`]
  Priority 2 files: [`backend/routers/auth.py`, `backend/routers/users.py`, `backend/routers/baseline_report.py`, `backend/routers/control_mappings.py`, `backend/routers/control_plane.py`, `backend/routers/saas_admin.py`, `backend/routers/support_files.py`, `backend/services/action_engine.py`, `backend/services/pr_bundle.py`, `backend/services/control_scope.py`]

FOR TASK 4 (worker features):
  Priority 1 files: [`backend/workers/main.py`, `backend/workers/lambda_handler.py`, `backend/workers/jobs/__init__.py`, `backend/workers/jobs/ingest_findings.py`, `backend/workers/jobs/compute_actions.py`, `backend/workers/jobs/remediation_run.py`, `backend/workers/jobs/remediation_run_execution.py`, `backend/workers/jobs/evidence_export.py`, `backend/workers/jobs/generate_baseline_report.py`, `backend/workers/jobs/weekly_digest.py`]
  Priority 2 files: [`backend/workers/jobs/reconcile_inventory_global_orchestration.py`, `backend/workers/jobs/reconcile_inventory_shard.py`, `backend/workers/jobs/reconcile_recently_touched_resources.py`, `backend/workers/jobs/ingest_access_analyzer.py`, `backend/workers/jobs/ingest_inspector.py`, `backend/workers/jobs/ingest_control_plane_events.py`, `backend/workers/jobs/backfill_finding_keys.py`, `backend/workers/jobs/backfill_action_groups.py`, `backend/workers/services/inventory_reconcile.py`, `backend/utils/sqs.py`]

FOR TASK 5 (AWS integration features):
  Priority 1 files: [`backend/services/aws.py`, `backend/services/aws_account_orchestration.py`, `backend/workers/services/security_hub.py`, `backend/workers/services/access_analyzer.py`, `backend/workers/services/inspector.py`, `backend/workers/services/inventory_reconcile.py`, `backend/workers/services/direct_fix.py`, `backend/services/remediation_runtime_checks.py`, `backend/services/cloudformation_templates.py`, `backend/routers/aws_accounts.py`]
  Priority 2 files: [`backend/services/tenant_reconciliation.py`, `backend/services/health_checks.py`, `backend/services/evidence_export.py`, `backend/services/baseline_report_service.py`, `backend/routers/control_plane.py`, `backend/routers/internal.py`, `infrastructure/cloudformation/control-plane-forwarder-template.yaml`, `infrastructure/cloudformation/reconcile-scheduler-template.yaml`, `infrastructure/cloudformation/read-role-template.yaml`, `infrastructure/cloudformation/write-role-template.yaml`]

FOR TASK 6 (infrastructure features):
  Priority 1 files: [`infrastructure/cloudformation/saas-serverless-httpapi.yaml`, `infrastructure/cloudformation/sqs-queues.yaml`, `infrastructure/cloudformation/saas-serverless-build.yaml`, `infrastructure/cloudformation/saas-ecs-dev.yaml`, `infrastructure/cloudformation/control-plane-forwarder-template.yaml`, `infrastructure/cloudformation/reconcile-scheduler-template.yaml`, `infrastructure/cloudformation/read-role-template.yaml`, `infrastructure/cloudformation/write-role-template.yaml`, `infrastructure/cloudformation/edge-protection.yaml`, `infrastructure/cloudformation/dr-backup-controls.yaml`]
  Priority 2 files: [`infrastructure/terraform/saas-ecs-dev/main.tf`, `infrastructure/terraform/saas-ecs-dev/network.tf`, `infrastructure/terraform/saas-ecs-dev/ecs.tf`, `infrastructure/terraform/saas-ecs-dev/alb.tf`, `infrastructure/terraform/saas-ecs-dev/ecr.tf`, `infrastructure/finding-scenarios/README.md`, `infrastructure/finding-scenarios/stacks/cspm_insecure_bundle/main.tf`, `scripts/deploy_saas_serverless.sh`, `scripts/deploy_saas_ecs_dev.sh`, `docs/deployment/README.md`]
