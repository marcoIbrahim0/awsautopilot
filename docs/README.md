# AWS Security Autopilot Documentation

AWS Security Autopilot operationalizes AWS-native security services by turning findings into actions, managing exceptions, executing approved remediation workflows, and producing evidence artifacts.

## Quick Navigation

### Developers
- [Local development guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/README.md)
- [Prod-readiness package](/Users/marcomaher/AWS%20Security%20Autopilot/docs/prod-readiness/README.md)
- [Reconciliation quality review](/Users/marcomaher/AWS%20Security%20Autopilot/docs/reconciliation_quality_review.md)
- [Item 17 medium/low-confidence control coverage plan](/Users/marcomaher/AWS%20Security%20Autopilot/docs/prod-readiness/17-medium-low-confidence-control-coverage-plan.md)
- [Remediation safety model](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-safety-model.md)
- [Action score explainability](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/action-score-explainability.md)
- [Toxic-combination prioritization](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/toxic-combination-prioritization.md)
- [Root-key remediation lifecycle UI](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/root-key-remediation-lifecycle-ui.md)
- [Communication + Governance layer](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/communication-governance-layer.md)
- [Ownership-based risk queues](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/ownership-risk-queues.md)
- [Shared Security + Engineering execution guidance](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/shared-execution-guidance.md)
- [Handoff-free closure](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/handoff-free-closure.md)
- [Secret migration connectors](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/secret-migration-connectors.md)
- [Queue contract quarantine runbook](/Users/marcomaher/AWS%20Security%20Autopilot/docs/queue-contract-quarantine-runbook.md)

### Operators / SaaS owners
- [Deployment guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/deployment/README.md)
- [Production deployment profile](/Users/marcomaher/AWS%20Security%20Autopilot/docs/Production/deployment.md)
- [Runbooks index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/runbooks/README.md)
- [Live E2E testing docs](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/README.md)
- [Post-test logical-solutions backlog](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/post-test-logical-solutions-backlog.md)
- [Root-key safe remediation technical spec (planned)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/root-key-safe-remediation-spec.md)
- [Root-key safe remediation acceptance matrix (planned)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/root-key-safe-remediation-acceptance-matrix.md)
- [Root-key safe remediation implementation checklist (planned)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/root-key-safe-remediation-implementation-checklist.md)
- [Control-plane event monitoring](/Users/marcomaher/AWS%20Security%20Autopilot/docs/control-plane-event-monitoring.md)
- [Item 16 high-confidence live status rollout policy](/Users/marcomaher/AWS%20Security%20Autopilot/docs/prod-readiness/16-high-confidence-live-status-rollout.md)

### Customers
- [Customer guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/README.md)
- [Connect WriteRole guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/connect-write-role.md)

### Auditors / compliance
- [Audit remediation package](/Users/marcomaher/AWS%20Security%20Autopilot/docs/audit-remediation/README.md)
- [Phase 4 required-check governance](/Users/marcomaher/AWS%20Security%20Autopilot/docs/audit-remediation/phase4-required-check-governance.md)
- [Disaster recovery runbook](/Users/marcomaher/AWS%20Security%20Autopilot/docs/disaster-recovery-runbook.md)

## Documentation Structure

### Active folders
- `/docs/deployment/` — deployment, infra, DB, secrets, monitoring docs
- `/docs/local-dev/` — backend/worker/frontend/test local workflows
- `/docs/customer-guide/` — customer-facing onboarding and troubleshooting
- `/docs/runbooks/` — operator runbooks for no-UI and incident workflows
- `/docs/live-e2e-testing/` — live test tracker, runbook, templates
- `/docs/prod-readiness/` — production-readiness artifacts and scripts
- `/docs/audit-remediation/` — audit remediation plans, checklists, evidence references
- `/docs/features/` — active entrypoint (historical snapshot files archived)
- `/docs/archive/` — archived historical docs moved from active navigation

### Archived snapshots
- [2026-02 docs cleanup archive](/Users/marcomaher/AWS%20Security%20Autopilot/docs/archive/2026-02-doc-cleanup/README.md)

### Planned documentation areas (not implemented)
- API reference docs tree (`docs/api/`)
- Data-model docs tree (`docs/data-model/`)
- Owner/client architecture docs trees (`docs/architecture/owner/`, `docs/architecture/client/`)
- ADR docs tree (`docs/decisions/`)

## System Overview

- Frontend: Next.js (`frontend/src/app`)
- API: FastAPI (`backend/main.py`)
- Worker: SQS consumers (`backend/workers/main.py`)
- DB: PostgreSQL + Alembic
- Queue families: ingest, events-fastlane, inventory-reconcile, export-report, contract-quarantine
- Storage: S3 export/support/template buckets
- Auth and tenancy: JWT + tenant-scoped access

## Notes on Source of Truth

For live endpoint and payload behavior, treat source code as authoritative:

- Backend route definitions: `/Users/marcomaher/AWS Security Autopilot/backend/routers/`
- Frontend API contract calls: `/Users/marcomaher/AWS Security Autopilot/frontend/src/lib/api.ts`

Historical audit/snapshot docs remain available under `/docs/archive/` and should not be used as current API contract references.

## Versioning

- [Changelog](/Users/marcomaher/AWS%20Security%20Autopilot/docs/CHANGELOG.md)
