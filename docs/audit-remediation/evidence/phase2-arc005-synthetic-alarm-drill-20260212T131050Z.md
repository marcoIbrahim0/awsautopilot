# ARC-005 Synthetic Alarm Drill Evidence

Generated at: `2026-02-12T13:10:50Z`  
Region: `eu-north-1`

## Trigger Window

- Synthetic `ALARM` set at: `2026-02-12T13:10:20Z`
- Synthetic `OK` recovery set at: `2026-02-12T13:10:50Z`

## Queue Backlog Alarm Triggers

- `security-autopilot-ingest-queue-depth` -> `ALARM` -> `OK`
- `security-autopilot-events-queue-depth` -> `ALARM` -> `OK`
- `security-autopilot-inventory-queue-depth` -> `ALARM` -> `OK`
- `security-autopilot-export-report-queue-depth` -> `ALARM` -> `OK`

## DLQ Ingress Alarm Triggers

- `security-autopilot-ingest-dlq-ingress` -> `ALARM` -> `OK`
- `security-autopilot-events-dlq-ingress` -> `ALARM` -> `OK`
- `security-autopilot-inventory-dlq-ingress` -> `ALARM` -> `OK`
- `security-autopilot-export-report-dlq-ingress` -> `ALARM` -> `OK`

## Verification

- Post-drill alarm inventory confirms all triggered alarms returned to `OK`.
- Queue and DLQ steady-state snapshot is recorded in:
  - `docs/audit-remediation/evidence/phase2-architecture-20260212T131159Z.md`
