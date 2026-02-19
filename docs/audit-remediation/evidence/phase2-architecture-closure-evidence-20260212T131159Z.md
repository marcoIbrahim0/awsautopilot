# Phase 2 Architecture Closure Evidence

Generated at: `2026-02-12T13:11:59.857563+00:00`  
Region: `eu-north-1`  
AWS Account: `029037611564`

## Required Operational Proof (`ARC-002` to `ARC-007`)

- `ARC-002` load/starvation proof:
  - `docs/audit-remediation/evidence/phase2-arc002-arc006-load-20260212T125856Z.md`
  - `docs/audit-remediation/evidence/phase2-arc002-arc006-load-20260212T125856Z.json`
- `ARC-003` fail+resume proof (forced mid-fan-out failure with checkpointed resume):
  - `docs/audit-remediation/evidence/phase2-arc003-failure-resume-20260212T130046Z.txt`
- `ARC-004` EventBridge target failure injection to DLQ (after retries):
  - `docs/audit-remediation/evidence/phase2-arc004-failure-injection-20260212T130923Z.md`
  - Synthetic event id: `31fa71a0-370e-83fd-0af0-db3bc639c350`
  - Rule ARN: `arn:aws:events:eu-north-1:029037611564:rule/SecurityAutopilotArc004FiRule20260212130820`
  - Target ARN: `arn:aws:events:eu-north-1:029037611564:api-destination/SecurityAutopilotArc004FiDest20260212130820/3b754c29-86e2-4f89-af32-c780897df850`
  - Target DLQ URL: `https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-arc004-fi-dlq-20260212130820`
  - DLQ visible after injection: `1`
  - Sample DLQ message id: `52dd3412-7455-4da9-a2d9-1e567c97d9cb`
  - Sample `ERROR_CODE`: `SDK_CLIENT_ERROR`
  - Sample `ERROR_MESSAGE`: `Unable to invoke ApiDestination endpoint: API destination endpoint cannot be reached.`
  - Ephemeral drill resources were removed after capture.
- `ARC-005` synthetic alarm triggers (queue backlog + DLQ ingress) across ingest/events/inventory/export:
  - `docs/audit-remediation/evidence/phase2-arc005-synthetic-alarm-drill-20260212T131050Z.md`
  - Trigger timestamp: `2026-02-12T13:10:20Z`
  - Recovery timestamp: `2026-02-12T13:10:50Z`
  - Triggered + recovered alarms:
    - `security-autopilot-ingest-queue-depth`
    - `security-autopilot-events-queue-depth`
    - `security-autopilot-inventory-queue-depth`
    - `security-autopilot-export-report-queue-depth`
    - `security-autopilot-ingest-dlq-ingress`
    - `security-autopilot-events-dlq-ingress`
    - `security-autopilot-inventory-dlq-ingress`
    - `security-autopilot-export-report-dlq-ingress`
- `ARC-006` mixed-load latency isolation proof:
  - `docs/audit-remediation/evidence/phase2-arc002-arc006-load-20260212T125856Z.md`
  - `docs/audit-remediation/evidence/phase2-arc002-arc006-load-20260212T125856Z.json`
- `ARC-007` CI evidence (contract compatibility + quarantine path checks):
  - `docs/audit-remediation/evidence/phase2-ci-gate-20260212T130032Z.txt`
  - `docs/audit-remediation/evidence/phase2-orchestration-api-gate-20260212T130038Z.txt`

## Customer-Account Forwarder Rollout Readiness Evidence

- Forwarder stack status (`customer account / monitored region gate`):
  - Stack: `SecurityAutopilotControlPlaneForwarder`
  - Status: `UPDATE_COMPLETE`
  - Last updated: `2026-02-12T12:20:02.483000+00:00`
- Rule + target enforcement:
  - Rule: `SecurityAutopilotControlPlaneApiCallsRule-eu-north-1` (`ENABLED`)
  - Target has explicit DLQ + retry:
    - DLQ ARN: `arn:aws:sqs:eu-north-1:029037611564:security-autopilot-control-plane-target-dlq-eu-north-1`
    - `MaximumRetryAttempts=8`
    - `MaximumEventAgeInSeconds=3600`
- Onboarding readiness gate contract tests:
  - `docs/audit-remediation/evidence/phase2-forwarder-readiness-gate-tests-20260212T130053Z.txt`

## DLQ Alarmed Backlog Remediation (`events` + `inventory`)

- Before (latest prior evidence snapshot):
  - `docs/audit-remediation/evidence/phase2-architecture-20260212T124542Z.md`
  - `EventsFastLaneDLQURL visible=10`
  - `InventoryReconcileDLQURL visible=138`
  - DLQ depth/age alarms were `ALARM`
- Remediation actions:
  - Drained stale backlog from `security-autopilot-events-fastlane-dlq`
  - Drained stale backlog from `security-autopilot-inventory-reconcile-dlq`
  - Waited for CloudWatch reevaluation
- After (fresh evidence snapshot):
  - `docs/audit-remediation/evidence/phase2-architecture-20260212T131159Z.md`
  - `EventsFastLaneDLQURL visible=0`
  - `InventoryReconcileDLQURL visible=0`
  - `security-autopilot-events-dlq-depth` / `security-autopilot-events-dlq-age` -> `OK`
  - `security-autopilot-inventory-dlq-depth` / `security-autopilot-inventory-dlq-age` -> `OK`

## Deploy Outputs

- `security-autopilot-sqs-queues`: `UPDATE_COMPLETE` (last updated `2026-02-12T11:49:12.876000+00:00`)
- `SecurityAutopilotControlPlaneForwarder`: `UPDATE_COMPLETE` (last updated `2026-02-12T12:20:02.483000+00:00`)
- `security-autopilot-reconcile-scheduler`: `CREATE_COMPLETE` (last updated `2026-02-12T11:55:54.563000+00:00`)

## Sign-Off Package

- Test artifacts attached:
  - `docs/audit-remediation/evidence/phase2-ci-gate-20260212T130032Z.txt`
  - `docs/audit-remediation/evidence/phase2-orchestration-api-gate-20260212T130038Z.txt`
  - `docs/audit-remediation/evidence/phase2-arc003-failure-resume-20260212T130046Z.txt`
  - `docs/audit-remediation/evidence/phase2-forwarder-readiness-gate-tests-20260212T130053Z.txt`
- Deploy outputs attached:
  - `docs/audit-remediation/evidence/phase2-architecture-20260212T131159Z.md`
- Alarm evidence attached:
  - `docs/audit-remediation/evidence/phase2-architecture-20260212T131159Z.md`
  - Synthetic trigger/recovery evidence in this file (`ARC-005` section)
- On-call owner acknowledgement:
  - Owner: `arn:aws:iam::029037611564:user/AutoPilotAdmin`
  - Ack timestamp: `2026-02-12T13:12:40Z`
  - Scope: `Phase 2 architecture closure package review and acceptance for ARC-002 through ARC-007`

## Machine-Readable Artifact

- `docs/audit-remediation/evidence/phase2-architecture-closure-evidence-20260212T131159Z.json`
