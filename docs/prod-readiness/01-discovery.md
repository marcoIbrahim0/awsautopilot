# 01 Discovery - Control and Action Input Contract

> Scope date: 2026-02-25 historical discovery snapshot.
>
> Current contract note (2026-03-19): current `master` exposes PR-only remediation surfaces. Historical `direct_fix` and `both` labels below are preserved as extraction-time evidence from the pre-de-scope snapshot, not as current product behavior.

## Objective

Define the canonical discovery contract for production-readiness validation tasks.
This document is validation input only and does not define architecture design, resource design, or remediation design.

## Authoritative Sources

Discovery and consolidation were derived from the following production-readiness artifacts:

- [`06-task1-file-map.md`](06-task1-file-map.md)
- [`06-task2-raw-controls.md`](06-task2-raw-controls.md)
- [`06-task3-raw-action-types.md`](06-task3-raw-action-types.md)
- [`06-task4-raw-id-registries.md`](06-task4-raw-id-registries.md)
- [`06-task5-raw-direct-fix.md`](06-task5-raw-direct-fix.md)
- [`06-task6-raw-pr-bundle.md`](06-task6-raw-pr-bundle.md)
- Consolidated inventory: [`06-control-action-inventory.md`](06-control-action-inventory.md)

## Normalization Rules

1. Conflict precedence: `registry entry > class definition > comment`.
2. Canonical control-ID casing follows the registry mapping.
3. Alias controls are retained as explicit control rows when they are represented in the consolidated inventory.
4. Literal `UNKNOWN` placeholders in raw extraction files are treated as unresolved metadata and must be surfaced in validation flags.
5. Architecture-objective metadata IDs are tracked separately from runtime controls.

## Canonical Schemas

### Control schema

| Field | Requirement | Description |
| --- | --- | --- |
| `Control ID` | Required | Canonical ID (for example `S3.2`, `EC2.53`). |
| `Control Name` | Required | Canonical control title from consolidated inventory. |
| `AWS Service` | Required | Primary AWS service namespace associated with the control. |
| `What it checks` | Required | Runtime posture/signal that determines open vs resolved state. |
| `Action Type` | Required | One of the historical extraction values `direct_fix`, `pr_bundle`, `both`, `pr_only`, or `INFRA_METADATA_ONLY`. Current product contract is PR-only. |

### Action schema

| Field | Requirement | Description |
| --- | --- | --- |
| `Action ID` | Required | Canonical action ID. |
| `Action Name` | Required | Canonical action title from consolidated inventory. |
| `Type` | Required | Historical extraction label: `direct-fix`, `pr-bundle`, or both. Current product contract is PR-only. |
| `AWS API or IaC resource` | Required | Concrete API operation(s) and/or IaC resource(s); `UNKNOWN` when unresolved. |

## Classification Vocabulary

- `direct_fix`: historical extraction label for the pre-2026-03-19 direct API mutation path. Current product contract disables this path.
- `pr_bundle`: action executes through IaC patch/PR bundle path.
- `both`: historical extraction label for controls/actions that exposed both direct-fix and PR-bundle paths in the snapshot. Current product contract exposes only customer-run PR-bundle flow.
- `pr_only`: explicit unsupported-remediation classification used for inventory-only visibility signals.
- `INFRA_METADATA_ONLY`: architecture/audit metadata, not a runtime remediation control.
- `UNCLASSIFIED`: missing or unresolved classification and always a validation failure.
- `UNKNOWN`: missing source evidence for a required field and always a validation flag.

## Runtime Coverage Boundary

For downstream validation and coverage counts:

- Include controls with snapshot `Action Type` values: `direct_fix`, `pr_bundle`, `both`, `pr_only`.
- Exclude controls with `Action Type = INFRA_METADATA_ONLY` from runtime coverage totals.
- Current excluded metadata-only row: `ARC-008` (`ArchitectureObjectiveId` traceability metadata).

## Discovery Snapshot (2026-02-25)

From the consolidated inventory:

- Runtime controls to cover: `25`
- Controls with historical direct-fix capability in the snapshot: `4`
- Controls with PR-bundle capability: `25` (includes explicit `pr_only` unsupported controls)
- Distinct AWS services represented in runtime controls: `11`
- Action IDs inventoried: `19`
- Action IDs with unresolved `AWS API or IaC resource` in the snapshot: `pr_only`, `direct_fix`, `pr_bundle`

## Validation Gate Requirements

Any downstream validation output (for example Task 1 input validation) must:

1. List all runtime controls (excluding `INFRA_METADATA_ONLY` rows) with canonical service and action-type mapping.
2. List all action IDs with normalized type and concrete API/IaC mapping.
3. Produce coverage totals and distinct service-category counts.
4. Flag all unresolved values:
   - `Action Type = UNCLASSIFIED`
   - `AWS Service = UNKNOWN`
   - `What it checks = UNKNOWN`
   - `AWS API or IaC resource = UNKNOWN`

## Completion Criteria

Discovery is complete for downstream scenario tasks only when:

- Runtime controls and action IDs are fully enumerated from the consolidated inventory.
- Runtime/metadata boundary is explicit (`ARC-008` excluded from runtime coverage counts).
- Remaining unresolved values are explicitly flagged and tracked, not silently ignored.
