# AWS Security Autopilot Documentation

AWS Security Autopilot operationalizes AWS-native security services by turning findings into actions, managing exceptions, generating customer-run PR bundles, and producing evidence artifacts. Customer `WriteRole` and `direct_fix` execution are currently out of scope.

## Quick Navigation

### Developers
- [Repo agent instructions](/Users/marcomaher/AWS%20Security%20Autopilot/AGENTS.md)
- [Local development guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/README.md)
- [Prod-readiness package](/Users/marcomaher/AWS%20Security%20Autopilot/docs/prod-readiness/README.md)
- [Reconciliation quality review](/Users/marcomaher/AWS%20Security%20Autopilot/docs/reconciliation_quality_review.md)
- [Item 17 medium/low-confidence control coverage plan](/Users/marcomaher/AWS%20Security%20Autopilot/docs/prod-readiness/17-medium-low-confidence-control-coverage-plan.md)
- [Remediation safety model](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-safety-model.md)
- [Remediation profile resolution spec (planned)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/README.md)
- [Remediation profile resolution implementation plan (planned)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/implementation-plan.md)
- [Action score explainability](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/action-score-explainability.md)
- [Threat-intelligence weighting](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/threat-intelligence-weighting.md)
- [Toxic-combination prioritization](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/toxic-combination-prioritization.md)
- [Security Graph foundation](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/security-graph-foundation.md)
- [Graph-backed action context](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/graph-backed-action-context.md)
- [Attack Path view](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/attack-path-view.md)
  Current shipped bounded action-detail story plus the Phase-1 `/attack-paths` surface, Phase-2 shared path records/ranking, Phase-3 triage workflow views/remediation rollups, the bounded Phase-4 runtime/code-to-cloud/workflow projections, and the March 22 materialized read-model optimization for production-ready list/detail latency
- [Attack Path enterprise implementation plan](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/attack-path-enterprise-implementation-plan.md)
- [Phase 3.5 roadmap](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/phase-3-5-roadmap.md)
- [Root-key remediation lifecycle UI](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/root-key-remediation-lifecycle-ui.md)
- [Communication + Governance layer](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/communication-governance-layer.md)
- [Integration-first remediation operations](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/integration-first-remediation-operations.md)
- [UI/UX redesign implementation](/Users/marcomaher/AWS%20Security%20Autopilot/docs/ui-ux-redesign-implementation.md)
- [Remediation system-of-record sync](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/remediation-system-of-record-sync.md)
- [Recommendation mode matrix](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/recommendation-mode-matrix.md)
- [Ownership-based risk queues](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/ownership-risk-queues.md)
- [Shared Security + Engineering execution guidance](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/shared-execution-guidance.md)
- [Handoff-free closure](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/handoff-free-closure.md)
- [Repo-aware PR automation](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/repo-aware-pr-automation.md)
- [Business impact matrix](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/business-impact-matrix.md)
- [Firebase email verification signup flow](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/firebase-email-verification-signup.md)
- [Secret migration connectors](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/secret-migration-connectors.md)
- [Help Desk Platform](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/help-desk-platform.md)
- [Queue contract quarantine runbook](/Users/marcomaher/AWS%20Security%20Autopilot/docs/queue-contract-quarantine-runbook.md)
- [Final to-do list](/Users/marcomaher/AWS%20Security%20Autopilot/docs/final-to-do/final-to-do)

### Operators / SaaS owners
- [Deployment guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/deployment/README.md)
- [Production deployment profile](/Users/marcomaher/AWS%20Security%20Autopilot/docs/Production/deployment.md)
- [Runbooks index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/runbooks/README.md)
- [Jira remediation sync runbook](/Users/marcomaher/AWS%20Security%20Autopilot/docs/runbooks/jira-remediation-sync-runbook.md)
- [Serverless lifecycle cost-control runbook](/Users/marcomaher/AWS%20Security%20Autopilot/docs/runbooks/serverless-lifecycle-cost-control.md)
- [Live E2E testing docs](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/README.md)
- [Post-test logical-solutions backlog](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/post-test-logical-solutions-backlog.md)
- [Root-key safe remediation technical spec (planned)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/root-key-safe-remediation-spec.md)
- [Root-key safe remediation acceptance matrix (planned)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/root-key-safe-remediation-acceptance-matrix.md)
- [Root-key safe remediation implementation checklist (planned)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/root-key-safe-remediation-implementation-checklist.md)
- [Control-plane event monitoring](/Users/marcomaher/AWS%20Security%20Autopilot/docs/control-plane-event-monitoring.md)
- [Item 16 high-confidence live status rollout policy](/Users/marcomaher/AWS%20Security%20Autopilot/docs/prod-readiness/16-high-confidence-live-status-rollout.md)

### Customers
- [Customer guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/README.md)
- [Help Hub and support cases](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/help-hub.md)
- [WriteRole status (out of scope)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/connect-write-role.md)

### Auditors / compliance
- [Trust package](/Users/marcomaher/AWS%20Security%20Autopilot/docs/trust/README.md)
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
- `/docs/trust/` — buyer-facing trust review package and current least-privilege evidence
- `/docs/remediation-profile-resolution/` — planned remediation profile resolution spec, implementation plan, and Wave 0 contract lock
- `/docs/prod-readiness/` — production-readiness artifacts and scripts
- `/docs/audit-remediation/` — audit remediation plans, checklists, evidence references
- `/docs/features/` — active entrypoint (historical snapshot files archived)
- `/docs/final-to-do/` — remaining product/UX follow-ups that still need implementation
- `/docs/archive/` — archived historical docs moved from active navigation

### Archived snapshots
- [2026-02 docs cleanup archive](/Users/marcomaher/AWS%20Security%20Autopilot/docs/archive/2026-02-doc-cleanup/README.md)
- [2026-03 docs cleanup archive](/Users/marcomaher/AWS%20Security%20Autopilot/docs/archive/2026-03-doc-cleanup/README.md)

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

- Repo-level agent workflow and binding startup instructions live in [AGENTS.md](/Users/marcomaher/AWS%20Security%20Autopilot/AGENTS.md).

For live endpoint and payload behavior, treat source code as authoritative:

- Backend route definitions: `/Users/marcomaher/AWS Security Autopilot/backend/routers/`
- Frontend API contract calls: `/Users/marcomaher/AWS Security Autopilot/frontend/src/lib/api.ts`
- Frontend admin/reporting route contract:
  - Settings tabs: `/Users/marcomaher/AWS Security Autopilot/frontend/src/app/settings/`
  - Exports workspace: `/Users/marcomaher/AWS Security Autopilot/frontend/src/app/exports/`
  - `/settings?tab=...` is canonical for account/team/org/integrations/governance/remediation defaults and baseline report
  - `/exports` is the canonical exports and compliance workspace
  - `/baseline-report` redirects into Settings

Historical audit/snapshot docs remain available under `/docs/archive/` and should not be used as current API contract references.

## Versioning

- [Changelog](/Users/marcomaher/AWS%20Security%20Autopilot/docs/CHANGELOG.md)
