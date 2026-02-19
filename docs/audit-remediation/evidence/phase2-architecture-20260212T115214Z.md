# Phase 2 Architecture Evidence Snapshot

Generated at: `2026-02-12T11:52:14.334005+00:00`
Region: `eu-north-1`
AWS Account: `029037611564`
AWS Arn: `arn:aws:iam::029037611564:user/AutoPilotAdmin`

## Stack Status

| Stack | Name | Status |
| --- | --- | --- |
| sqs | security-autopilot-sqs-queues | UPDATE_COMPLETE |
| forwarder | security-autopilot-control-plane-forwarder | NOT_FOUND |
| reconcile | security-autopilot-reconcile-scheduler | NOT_FOUND |

## Queue Snapshot

| Queue Output Key | Visible | Not Visible | Delayed |
| --- | --- | --- | --- |
| IngestQueueURL | 0 | 0 | 0 |
| IngestDLQURL | 0 | 0 | 0 |
| EventsFastLaneQueueURL | 0 | 0 | 0 |
| EventsFastLaneDLQURL | 10 | 0 | 0 |
| InventoryReconcileQueueURL | 0 | 0 | 0 |
| InventoryReconcileDLQURL | 138 | 0 | 0 |
| ExportReportQueueURL | 0 | 0 | 0 |
| ExportReportDLQURL | 0 | 0 | 0 |
| ContractQuarantineQueueURL | 0 | 0 | 0 |

## Alarm Inventory

Total alarms matched: `22`

- `security-autopilot-contract-quarantine-age` (OK) [AWS/SQS:ApproximateAgeOfOldestMessage]
- `security-autopilot-contract-quarantine-depth` (OK) [AWS/SQS:ApproximateNumberOfMessagesVisible]
- `security-autopilot-events-dlq-age` (ALARM) [AWS/SQS:ApproximateAgeOfOldestMessage]
- `security-autopilot-events-dlq-depth` (ALARM) [AWS/SQS:ApproximateNumberOfMessagesVisible]
- `security-autopilot-events-dlq-ingress` (OK) [AWS/SQS:NumberOfMessagesSent]
- `security-autopilot-events-queue-age` (OK) [AWS/SQS:ApproximateAgeOfOldestMessage]
- `security-autopilot-events-queue-depth` (OK) [AWS/SQS:ApproximateNumberOfMessagesVisible]
- `security-autopilot-export-report-dlq-age` (OK) [AWS/SQS:ApproximateAgeOfOldestMessage]
- `security-autopilot-export-report-dlq-depth` (OK) [AWS/SQS:ApproximateNumberOfMessagesVisible]
- `security-autopilot-export-report-dlq-ingress` (OK) [AWS/SQS:NumberOfMessagesSent]
- `security-autopilot-export-report-queue-age` (OK) [AWS/SQS:ApproximateAgeOfOldestMessage]
- `security-autopilot-export-report-queue-depth` (OK) [AWS/SQS:ApproximateNumberOfMessagesVisible]
- `security-autopilot-ingest-dlq-age` (OK) [AWS/SQS:ApproximateAgeOfOldestMessage]
- `security-autopilot-ingest-dlq-depth` (OK) [AWS/SQS:ApproximateNumberOfMessagesVisible]
- `security-autopilot-ingest-dlq-ingress` (OK) [AWS/SQS:NumberOfMessagesSent]
- `security-autopilot-ingest-queue-age` (OK) [AWS/SQS:ApproximateAgeOfOldestMessage]
- `security-autopilot-ingest-queue-depth` (OK) [AWS/SQS:ApproximateNumberOfMessagesVisible]
- `security-autopilot-inventory-dlq-age` (ALARM) [AWS/SQS:ApproximateAgeOfOldestMessage]
- `security-autopilot-inventory-dlq-depth` (ALARM) [AWS/SQS:ApproximateNumberOfMessagesVisible]
- `security-autopilot-inventory-dlq-ingress` (OK) [AWS/SQS:NumberOfMessagesSent]
- `security-autopilot-inventory-queue-age` (OK) [AWS/SQS:ApproximateAgeOfOldestMessage]
- `security-autopilot-inventory-queue-depth` (OK) [AWS/SQS:ApproximateNumberOfMessagesVisible]

## Artifact Files

- JSON: `docs/audit-remediation/evidence/phase2-architecture-20260212T115214Z.json`
- Markdown: `docs/audit-remediation/evidence/phase2-architecture-20260212T115214Z.md`
