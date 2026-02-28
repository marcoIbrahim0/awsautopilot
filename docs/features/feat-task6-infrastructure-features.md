# Infrastructure Feature Analysis (Task 6)

Preflight note: `docs/prod-readiness/04-audit-deployment-frontend-compliance.md` is missing in-repo. Per task instructions, audit-linked fields are marked `unknown (audit source missing)`.

## INFRASTRUCTURE FEATURE INVENTORY

| Feature ID | Feature Name | Category | What it does | Implementation file(s) | Current state (implemented / partial / missing / unknown) | Required for production (yes / no / nice to have) | Known issues from audit files (finding ID or none) |
|---|---|---|---|---|---|---|---|
| INF-001 | SQLAlchemy runtime database engines | Database (ORM, connection pooling) | Provides async API DB engine and sync worker DB engine with connection pre-ping and Neon SSL handling. | `backend/database.py`, `backend/workers/database.py`, `backend/config.py` | implemented | yes | unknown (audit source missing) |
| INF-002 | Alembic migrations + revision guard | Database (migrations) | Enforces DB schema-at-head at API/worker startup and runs Alembic migration lineage. | `backend/services/migration_guard.py`, `backend/main.py`, `backend/workers/main.py`, `alembic/`, `alembic.ini` | implemented | yes | unknown (audit source missing) |
| INF-003 | DR backup and restore controls | Database (backup) | Defines AWS Backup vault/plan/selection, restore operator role, and backup/restore failure alarms. | `infrastructure/cloudformation/dr-backup-controls.yaml`, `docs/disaster-recovery-runbook.md` | partial (separate stack/runbook; not coupled to base runtime deploy) | yes | unknown (audit source missing) |
| INF-004 | Serverless build pipeline stack | Deployment pipeline (build/release) | Provisions build S3 source bucket, ECR repos, and CodeBuild project to build/push API/worker images. | `infrastructure/cloudformation/saas-serverless-build.yaml`, `scripts/deploy_saas_serverless.sh` | implemented | yes | unknown (audit source missing) |
| INF-005 | Runtime deployment automation scripts | Deployment pipeline (release) | Deploys serverless runtime and ECS runtime stacks with parameterized env/secrets and image tags. | `scripts/deploy_saas_serverless.sh`, `scripts/deploy_saas_ecs_dev.sh`, `infrastructure/cloudformation/saas-serverless-httpapi.yaml`, `infrastructure/cloudformation/saas-ecs-dev.yaml` | implemented | yes | unknown (audit source missing) |
| INF-006 | CI quality + security gates | Deployment pipeline (CI/CD) | Enforces backend/worker/frontend test matrices, migration gate, and dependency governance scans in GitHub Actions. | `.github/workflows/backend-ci.yml`, `.github/workflows/worker-ci.yml`, `.github/workflows/frontend-ci.yml`, `.github/workflows/migration-gate.yml`, `.github/workflows/dependency-governance.yml` | partial (strong CI; no in-repo auto-CD workflow) | yes | unknown (audit source missing) |
| INF-007 | Split environment configuration model | Environment configuration | Centralizes runtime config (env vars/feature flags/queue URLs/service toggles) with service-specific env files. | `backend/config.py`, `docs/deployment/secrets-config.md` | implemented | yes | unknown (audit source missing) |
| INF-008 | Secrets Manager runtime injection | Environment configuration (secrets management) | Injects `DATABASE_URL`, `JWT_SECRET`, and `CONTROL_PLANE_EVENTS_SECRET` into ECS/Lambda runtimes; supports manual secret rotation runbook. | `infrastructure/cloudformation/saas-ecs-dev.yaml`, `infrastructure/cloudformation/saas-serverless-httpapi.yaml`, `docs/deployment/secrets-config.md` | implemented | yes | unknown (audit source missing) |
| INF-009 | ECS network plane (VPC/ALB/SG/TLS) | Networking (VPC, load balancer, DNS) | Creates VPC, public subnets, IGW/route table, ALB listeners, target group health checks, and optional TLS listener. | `infrastructure/cloudformation/saas-ecs-dev.yaml` | implemented | yes | unknown (audit source missing) |
| INF-010 | Serverless API domain mapping | Networking (DNS/custom domain) | Exposes HTTP API endpoint with optional custom domain, certificate binding, and API mapping. | `infrastructure/cloudformation/saas-serverless-httpapi.yaml` | implemented | yes | unknown (audit source missing) |
| INF-011 | CDN layer for frontend/API edge caching | Networking (CDN) | No CloudFront/CDN infrastructure is defined in Task 6 Priority 1 templates. | no in-repo implementation found | missing | nice to have | unknown (audit source missing) |
| INF-012 | WAF edge protection stack | Networking + Alerting | Creates WAFv2 ACL, managed rule groups, rate limiting, optional IP allow-list, and WAF CloudWatch alarms. | `infrastructure/cloudformation/edge-protection.yaml` | partial (template exists; attachment depends on passing API/ALB ARN params) | yes | unknown (audit source missing) |
| INF-013 | Tenant-scoped export object storage | Storage (S3/file handling) | Stores evidence packs and baseline reports in tenant-prefixed S3 keys and serves presigned URLs. | `backend/services/evidence_export_s3.py`, `backend/services/evidence_export.py`, `infrastructure/cloudformation/saas-serverless-httpapi.yaml` | implemented | yes | unknown (audit source missing) |
| INF-014 | Tenant support-file storage access | Storage (S3/file handling) | Lists/downloads only tenant-visible support files and generates scoped presigned S3 URLs. | `backend/routers/support_files.py`, `backend/models/support_file.py`, `infrastructure/cloudformation/saas-serverless-httpapi.yaml` | implemented | yes | unknown (audit source missing) |
| INF-015 | Multi-queue SQS + DLQ + quarantine topology | Queue and async processing infrastructure | Provisions ingest/events/inventory/export queues with DLQs, plus contract quarantine queue and least-privilege queue IAM policies. | `infrastructure/cloudformation/sqs-queues.yaml` | implemented | yes | unknown (audit source missing) |
| INF-016 | Worker trigger and job dispatch fabric | Queue and async processing infrastructure | Wires Lambda event-source mappings / ECS pollers to queue jobs and dispatches handlers by `job_type`. | `infrastructure/cloudformation/saas-serverless-httpapi.yaml`, `backend/workers/main.py`, `backend/workers/jobs/__init__.py`, `backend/utils/sqs.py` | implemented | yes | unknown (audit source missing) |
| INF-017 | CloudWatch runtime log infrastructure | Logging infrastructure | Creates per-service log groups for API and worker runtimes (Lambda and ECS) with retention settings. | `infrastructure/cloudformation/saas-serverless-httpapi.yaml`, `infrastructure/cloudformation/saas-ecs-dev.yaml`, `docs/deployment/monitoring-alerting.md` | implemented | yes | unknown (audit source missing) |
| INF-018 | Metrics collection and readiness SLO snapshots | Metrics and monitoring infrastructure | Collects SQS lag/depth and dependency health into `/ready` output; docs define CloudWatch metric coverage. | `backend/services/health_checks.py`, `backend/main.py`, `docs/deployment/monitoring-alerting.md` | partial (core metrics present; dashboarding/extended metrics manual) | yes | unknown (audit source missing) |
| INF-019 | Alarming and notification hooks | Alerting infrastructure | Defines CloudWatch alarms across SQS, WAF, EventBridge, and AWS Backup with optional SNS action wiring. | `infrastructure/cloudformation/sqs-queues.yaml`, `infrastructure/cloudformation/edge-protection.yaml`, `infrastructure/cloudformation/control-plane-forwarder-template.yaml`, `infrastructure/cloudformation/reconcile-scheduler-template.yaml`, `infrastructure/cloudformation/dr-backup-controls.yaml` | implemented | yes | unknown (audit source missing) |
| INF-020 | Health and readiness endpoints | Health checks and readiness probes | Exposes `/health` and dependency-aware `/ready` endpoints, and ALB target group health checks on `/health`. | `backend/main.py`, `backend/services/health_checks.py`, `infrastructure/cloudformation/saas-ecs-dev.yaml` | implemented | yes | unknown (audit source missing) |
| INF-021 | JWT/cookie/CSRF authentication substrate | Authentication infrastructure (JWT, session, token storage) | Implements JWT access tokens, cookie + CSRF enforcement, password hashing, and tenant control-plane token hashing/fingerprint storage. | `backend/auth.py`, `backend/models/tenant.py`, `backend/config.py` | implemented | yes | unknown (audit source missing) |
| INF-022 | Tenant isolation substrate | Multi-tenancy infrastructure (tenant isolation mechanism) | Enforces tenant-scoped DB schema relations/indexes and tenant-filtered API query patterns. | `backend/models/*.py`, `backend/routers/aws_accounts.py`, `backend/routers/findings.py`, `backend/routers/actions.py`, `backend/routers/remediation_runs.py` | implemented | yes | unknown (audit source missing) |
| INF-023 | Transactional + digest email delivery | Email delivery infrastructure | Sends invites, weekly digests, and baseline-report-ready notices using SMTP-backed service (local mode logs). | `backend/services/email.py`, `backend/workers/jobs/weekly_digest.py` | partial (SES-native production delivery not implemented) | nice to have | unknown (audit source missing) |
| INF-024 | Scheduler and cron ingress | Scheduler infrastructure | Supports EventBridge-driven reconciliation scheduling and secret-protected internal cron endpoints (weekly digest + reconciliation ticks). | `infrastructure/cloudformation/reconcile-scheduler-template.yaml`, `backend/routers/internal.py`, `backend/workers/jobs/weekly_digest.py` | implemented | yes | unknown (audit source missing) |

## PERFORMANCE AND SCALING CHARACTERISTICS

| Component | Scales how | Current bottleneck | Breaks at what scale | Horizontal scale ready |
|-----------|-----------|-------------------|---------------------|----------------------|
| API runtime (Lambda HTTP API / ECS API service) | Lambda concurrency or ECS `DesiredCount` behind API Gateway/ALB | PostgreSQL connection capacity and cold starts (Lambda path) | unknown (no in-repo load threshold) | yes |
| Worker runtime (queue consumers) | More Lambda reserved concurrency or ECS worker task count | Low-concurrency production profile (`WorkerReservedConcurrency=1` in production profile) and DB write throughput | unknown; queue age/depth alarms are the first explicit saturation signal | partial |
| PostgreSQL primary store | Vertical scaling (instance class/storage), optional RDS HA settings | Single primary DB + shared connection pools | unknown (capacity target not codified) | partial |
| SQS async pipeline | Queue depth can absorb burst; consumers scale independently | Consumer throughput, not queue capacity | unknown (queue limits not codified in repo) | yes |
| Export/report generation | Export queue workers + S3 object writes | Export worker batch defaults (`ExportBatchSize=1`) and report rendering time | unknown | partial |
| EventBridge forwarder/scheduler | API Destination invocation rate limits (`5`/`50` RPS defaults in templates) | SaaS ingest endpoint throughput and DLQ replay operational cadence | unknown | yes |

## OPERATIONAL RUNBOOK COVERAGE

| Operational task | Runbook exists | Automated | Manual steps required | Who can perform it |
|-----------------|---------------|-----------|----------------------|-------------------|
| Deploy new version | yes (`docs/Production/deployment.md`, `docs/deployment/README.md`) | partial (scripted deploy, operator-triggered) | choose release tag, run deploy script, validate health/CORS/logs | Platform engineer / DevOps |
| Roll back a failed deploy | yes (`docs/Production/deployment.md`, `docs/deployment/ci-cd.md`) | partial (scripted rollback redeploy) | capture previous tag, redeploy, re-verify | Platform engineer / DevOps |
| Restore database from backup | yes (`docs/disaster-recovery-runbook.md`, `docs/deployment/database.md`) | no | select recovery point, start restore job, validate `/ready`, collect evidence | Platform engineer / DB operator |
| Add a new AWS account for a tenant | yes (`docs/customer-guide/connecting-aws.md`) | no | deploy ReadRole/WriteRole stack(s), paste ARNs into onboarding/settings, validate AssumeRole | Tenant AWS admin + tenant admin |
| Rotate JWT secret | yes (`docs/deployment/secrets-config.md`) | no | generate new secret, update Secrets Manager, restart/redeploy services | Platform engineer / security operator |
| Rotate AWS role credentials | no (STS role-based; no static creds stored) | no | redeploy role templates with updated trust/external-id policy and reconnect account as needed | Tenant AWS admin + SaaS admin |
| Investigate a stuck remediation run | yes (`docs/audit-remediation/deployer-runbook-phase1-phase3.md`) | no | inspect pending runs, resend queue job, inspect queue depth and worker logs | Platform engineer / on-call |
| Investigate a failed export | partial (`docs/customer-guide/troubleshooting.md` export section) | no | inspect export queue/DLQ, verify S3 access, retry export with reduced scope | Platform engineer / support engineer |
| Onboard a new tenant | yes (`docs/customer-guide/account-creation.md`) | partial (tenant/user records auto-created at signup) | user signup, onboarding wizard, AWS account connection | Tenant admin / customer operator |
| Remove a tenant and their data | no in-repo operator runbook found | no | ad hoc DB/S3 cleanup via internal tooling or SQL/scripts (procedure not documented) | SaaS admin + platform engineer |

## MULTI-TENANCY ISOLATION MECHANISM

- Database layer:
  - Most domain tables include `tenant_id` FK to `tenants.id` with tenant-scoped indexes/constraints (for example `findings`, `actions`, `aws_accounts`, `exceptions`, `remediation_runs`, `evidence_exports`).
  - Example: `Finding` unique scope includes `tenant_id + source + finding_key`; `AwsAccount` is unique on `tenant_id + account_id`.
- API layer:
  - JWT payload carries `tenant_id` (`backend/auth.py`), and authenticated request routing resolves tenant from `current_user.tenant_id` first (`resolve_tenant_id` in `backend/routers/aws_accounts.py`).
  - Query paths enforce tenant predicates (`...where(Model.tenant_id == tenant_uuid)`) across findings/actions/remediation/export endpoints.
- Worker layer:
  - Queue job contracts include `tenant_id` for all tenant-scoped jobs (`backend/utils/sqs.py`), and handlers operate using that tenant scope in DB queries/updates.
  - Account quarantine logic in worker is tenant+account keyed, preventing cross-tenant status mutation.
- Storage layer:
  - Export artifacts and baseline reports are written under tenant-prefixed keys (`exports/{tenant_id}/...`, `baseline-reports/{tenant_id}/...`).
  - Support file listing/download requires DB row match on `SupportFile.tenant_id == current_user.tenant_id` before presigned URL issuance.
- Queue layer:
  - Shared SQS queues are used (not per-tenant queues), but contract schema requires tenant context fields and rejects malformed payloads to quarantine.
  - Contract enforcement in worker prevents unknown/missing schema payloads from entering normal processing.

## DEPENDENCY VERSION AND SECURITY POSTURE

Latest-stable evidence source: registry queries executed on 2026-02-27 (`pip index versions`, `npm view`, HashiCorp checkpoint/registry APIs). CVE evidence source: `pip-audit` (backend + worker requirements) and `npm audit --audit-level=high` (frontend lockfile graph) executed on 2026-02-27.

| Dependency | Current version | Latest stable | Known CVEs | Upgrade urgency |
|-----------|----------------|--------------|-----------|----------------|
| FastAPI | `>=0.109.0,<1.0.0` (`backend/requirements.txt`) | `0.133.1` | none found by `pip-audit` | medium (not pinned; broad range) |
| SQLAlchemy | `>=2.0.0,<3.0.0` (`backend/requirements.txt`) | `2.0.47` | none found by `pip-audit` | medium (not pinned; broad range) |
| Alembic | `>=1.13.0,<2.0.0` (`backend/requirements.txt`) | `1.18.4` | none found by `pip-audit` | medium (not pinned; broad range) |
| boto3 | `>=1.34.0,<2.0.0` (`backend/requirements.txt`, `backend/workers/requirements.txt`) | `1.42.58` | none found by `pip-audit` | medium (not pinned; broad range) |
| PyJWT | `>=2.8.0,<3.0.0` (`backend/requirements.txt`) | `2.11.0` | none found by `pip-audit` | medium (not pinned; broad range) |
| bcrypt | `>=4.0.0,<5.0.0` (`backend/requirements.txt`) | `5.0.0` | none found by `pip-audit` | medium (major upgrade available; current cap blocks v5) |
| Next.js | `16.1.6` (`frontend/package-lock.json`) | `16.1.6` | no direct Next advisory from current audit; frontend graph has transitive `ajv`/`minimatch` advisories | low |
| React | `19.2.3` (`frontend/package-lock.json`) | `19.2.4` | no direct React advisory from current audit; frontend graph has transitive `ajv`/`minimatch` advisories | low |
| Terraform CLI | `>=1.5.0` (`infrastructure/terraform/saas-ecs-dev/main.tf`) | `1.14.6` | unknown (no Terraform CLI CVE scan artifact in repo) | medium |
| Terraform AWS Provider | `>=5.0.0` (`infrastructure/terraform/saas-ecs-dev/main.tf`) | `6.34.0` | unknown (no provider CVE scan artifact in repo) | medium-high |

