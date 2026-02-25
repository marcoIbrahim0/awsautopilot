# Task 3 Control Coverage Validation (Architecture 1 + Architecture 2)

This document validates that Architecture 1 and Architecture 2 together cover all runtime inventory controls from [`06-control-action-inventory.md`](06-control-action-inventory.md) with no overlap and no unassigned controls.

## Validation inputs

- Inventory source: [`07-task1-input-validation.md`](07-task1-input-validation.md), Section 1 control list (25 controls)
- Architecture 1 source: [`07-task2-arch1-scenario.md`](07-task2-arch1-scenario.md), control coverage plan
- Architecture 2 source: [`07-task3-arch2-scenario.md`](07-task3-arch2-scenario.md), control coverage plan

Validation timestamp (UTC): 2026-02-25

## Assignment table

| Control ID | Assigned architecture |
| --- | --- |
| S3.1 | Architecture 1 |
| SecurityHub.1 | Architecture 2 |
| GuardDuty.1 | Architecture 2 |
| S3.2 | Architecture 1 |
| S3.4 | Architecture 1 |
| EC2.53 | Architecture 1 |
| CloudTrail.1 | Architecture 2 |
| Config.1 | Architecture 2 |
| SSM.7 | Architecture 2 |
| EC2.182 | Architecture 2 |
| EC2.7 | Architecture 2 |
| S3.5 | Architecture 1 |
| IAM.4 | Architecture 2 |
| S3.9 | Architecture 1 |
| S3.11 | Architecture 1 |
| S3.15 | Architecture 1 |
| S3.3 | Architecture 1 |
| S3.8 | Architecture 1 |
| S3.17 | Architecture 1 |
| EC2.13 | Architecture 1 |
| EC2.18 | Architecture 1 |
| EC2.19 | Architecture 1 |
| RDS.PUBLIC_ACCESS | Architecture 2 |
| RDS.ENCRYPTION | Architecture 2 |
| EKS.PUBLIC_ENDPOINT | Architecture 2 |

## Validation result

- Total controls in inventory: 25
- Controls assigned to Architecture 1: 14
- Controls assigned to Architecture 2: 11
- Overlap between Architecture 1 and Architecture 2: 0
- Unassigned controls: 0
- Result: PASS
