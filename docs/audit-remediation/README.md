# Audit Remediation Package

Use this folder as the execution source of truth for the architecture, security, implementation, and UX findings.

## Documents

1. `00-program-plan.md` - program-level sequencing, governance, and completion standards.
   Includes detailed execution and expected outputs for Phases 0-4.
2. `01-priority-backlog.md` - normalized issue backlog with full source-finding traceability.
3. `02-architecture-plan.md` - detailed remediation tasks for `ARC-*` issues.
4. `03-security-plan.md` - detailed remediation tasks for `SEC-*` issues.
5. `04-implementation-plan.md` - detailed remediation tasks for `IMP-*` issues.
6. `05-ux-plan.md` - detailed remediation tasks for `UX-*` issues.
7. `phase2-architecture-closure-checklist.md` - closure evidence checklist for `ARC-002` through `ARC-007`.
8. `phase3-architecture-closure-checklist.md` - closure evidence checklist for `ARC-008` and `ARC-009`.
9. `phase3-security-closure-checklist.md` - closure evidence checklist for `SEC-008` and `SEC-010`.
10. `06-multi-agent-execution-plan.md` - phased parallel execution plan to close open remediation scope.
11. `phase4-required-check-governance.md` - final required-check matrix and branch-protection governance baseline.

## How to Execute

1. Start from `01-priority-backlog.md` and sort by `Priority` and `Target Phase`.
2. Pull implementation detail from the matching domain plan.
3. Require acceptance criteria and validation evidence before closing each ID.
4. Run weekly burndown against open `P0` and `P1` items first.
