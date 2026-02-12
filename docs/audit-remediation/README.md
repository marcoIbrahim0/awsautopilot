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

## How to Execute

1. Start from `01-priority-backlog.md` and sort by `Priority` and `Target Phase`.
2. Pull implementation detail from the matching domain plan.
3. Require acceptance criteria and validation evidence before closing each ID.
4. Run weekly burndown against open `P0` and `P1` items first.
