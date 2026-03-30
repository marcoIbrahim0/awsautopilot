# Run Metadata

## Scope

- Run ID: `20260330T021500Z-remediation-determinism-production-signoff`
- Date: `2026-03-30`
- Production truth surface: `https://api.ocypheris.com`
- Tenant: `Marco`
- Tenant ID: `e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`
- Canary AWS account: `696505809372`
- Region: `eu-north-1`

## Package Role

- This package is the final signoff index for remediation-determinism production readiness.
- It consolidates the authoritative retained closure packages for:
  - Gate 1 / Phase 1
  - Gate 2 / Phase 2
  - Gate 3 / Phase 3
- It is documentation-only and does not add new live proof beyond the retained packages it references.

## Authoritative Inputs

- Gate 1 closure:
  - `docs/test-results/live-runs/20260330T011601Z-phase1-action-resolution-closure/`
- Gate 2 closure:
  - `docs/test-results/live-runs/20260330T012757Z-phase2-action-resolution-lag-closure/`
- Gate 3 closure:
  - `docs/test-results/live-runs/20260329T194129Z-remediation-determinism-phase3-production/`
- Important predecessor context:
  - `docs/test-results/live-runs/20260330T000053Z-remediation-determinism-phase1-phase2-closure/`
  - `docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/`

## Final Gate State

- Gate 0: `PASS`
- Gate 1A: `PASS`
- Gate 1B: `PASS`
- Gate 2A: `PASS`
- Gate 2B: `PASS`
- Gate 3A: `PASS`
- Gate 3B: `PASS`
- Gate 3C: `PASS`
- Gate 3D: `PASS`
- Gate 3E: `PASS`
- Gate 4: `PASS`
- Gate 5: `PASS`

## Adjacent Runtime Follow-Up

- Non-blocking issue retained during the Phase 1 closure run:
  - `attack_path_materialization` duplicate-key inserts on `attack_path_materialized_summaries`
  - retained evidence: `docs/test-results/live-runs/20260330T011601Z-phase1-action-resolution-closure/scenarios/wi1-postdeploy/aws/worker-tail-after-trust-fix.txt`
