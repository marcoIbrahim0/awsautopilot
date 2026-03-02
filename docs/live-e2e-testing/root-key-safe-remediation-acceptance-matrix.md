# Root-Key Safe Remediation Acceptance Matrix

> Scope date: 2026-03-02
>
> Source spec: [root-key-safe-remediation-spec.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/root-key-safe-remediation-spec.md)
>
> ⚠️ Status: Planned — rollout gates define go/no-go criteria; full runtime orchestration is not yet implemented.

## 1) Gate Model

### MVP gate
- Objective: schema + repository safety contracts are correct and test-covered.
- Required: migration/model/store tests pass; no destructive migration behavior.

### Safe Rollout gate
- Objective: flagged runtime path can be enabled for limited tenants safely.
- Required: strict tenant scoping, idempotency, retry, rollback, and closure-path behavior validated in staging/live test account.

### GA gate
- Objective: production-wide enablement with stable closure and policy preservation.
- Required: no open P0/P1 defects, evidence-backed SLA compliance, operator runbooks finalized.

## 2) Acceptance Test Cases

| Case ID | Gate | Test type | Scenario | Expected outcome | Evidence required |
|---|---|---|---|---|---|
| `RK-MIG-001` | MVP | Positive | Apply migration upgrade to head | All 5 root-key tables and enums exist | Alembic upgrade log + schema diff artifact |
| `RK-MIG-002` | MVP | Negative | Execute migration downgrade | All root-key tables/enums removed cleanly | Alembic downgrade log |
| `RK-MOD-001` | MVP | Positive | Validate ORM constraints | Tenant-scoped unique/check constraints exist | Unit test output + model metadata snapshot |
| `RK-ISO-001` | MVP | Auth | Cross-tenant run/event read attempt | Denied/not found (no cross-tenant data leak) | Query/response evidence + test assertion |
| `RK-ISO-002` | MVP | Auth | Child write with non-tenant-owned `run_id` | Fail closed (`ValueError`/`404`) | Unit test output + error payload |
| `RK-IDEM-001` | MVP | Retry | Create run with same idempotency key twice | Second call returns existing run, no duplicate row | Unit test + DB unique key evidence |
| `RK-IDEM-002` | MVP | Retry | Concurrent insert race on dependency fingerprint | Integrity race resolves to existing row (idempotent) | Unit test output |
| `RK-LOCK-001` | MVP | Negative | Update run with stale `lock_version` | No state mutation; conflict surfaced | Unit test output |
| `RK-SEC-001` | MVP | Negative | Actor/payload metadata includes secret-like keys | Persisted metadata is redacted | Unit test output showing `<REDACTED>` |
| `RK-SM-001` | Safe Rollout | Positive | Valid transition path to `completed` | Only allowed transitions accepted | Integration test trace + event history |
| `RK-SM-002` | Safe Rollout | Negative | Invalid transition attempt (e.g., `completed -> migration`) | Rejected fail-closed | API response + event evidence |
| `RK-UNK-001` | Safe Rollout | Negative | Unknown dependency appears during flow | Transition to `needs_attention` + external task created | Event + task rows + API response |
| `RK-POL-001` | Safe Rollout | Positive | Disable-first then delete path | Delete step blocked until disable verification passes | Transition/event sequence artifact |
| `RK-RBK-001` | Safe Rollout | Retry | Policy-preservation regression during delete window | Transition to `rolled_back` with reason | Event rows + rollback reason evidence |
| `RK-CLS-001` | Safe Rollout | Positive | Closure protocol success (`ingest/compute/reconcile`) | Run reaches `completed`, action/finding resolved | Poll trace + final detail payload |
| `RK-CLS-002` | Safe Rollout | Negative | Closure protocol timeout | Run transitions to `failed` or `needs_attention` per policy | Timeout trace + final state evidence |
| `RK-AUTH-001` | Safe Rollout | Auth | Missing/invalid auth on root-key APIs | `401/403` deny closed | HTTP transcript |
| `RK-VSN-001` | Safe Rollout | Positive | Contract-version header validation | Supported version accepted; unsupported rejected | API response matrix |
| `RK-FE-001` | Safe Rollout | Positive | Root-key lifecycle UI timeline render | Run timeline shows transition states, timestamps, and evidence links | Frontend component test output + screenshot |
| `RK-FE-002` | Safe Rollout | Negative | Unknown dependency wizard fail-closed behavior | Wizard blocks continuation without explicit acknowledgement and supports rollback path | Frontend component test output |
| `RK-FE-003` | Safe Rollout | Auth | Role-based UI action controls | Non-admin users cannot trigger mutating transitions/task completion | Frontend component test output + UI capture |
| `RK-GA-001` | GA | Positive | Live production canary across multiple tenants | No cross-tenant leak; no duplicate side effects | Canary report + audit logs |
| `RK-GA-002` | GA | Positive | SLA conformance on closure cycles | >= 99% meet configured closure SLA | Metrics report + dashboards |
| `RK-GA-003` | GA | Negative | Operator escalation path | Manual task flow closes or fails with explicit reason | External task logs + runbook evidence |

## 3) Pass/Fail Criteria

### MVP pass criteria
- `RK-MIG-*`, `RK-MOD-*`, `RK-ISO-*`, `RK-IDEM-*`, `RK-LOCK-*`, `RK-SEC-*` all pass.
- No destructive migration actions.
- Feature flags default to behavior-preserving values (`false` for new path).

### Safe Rollout pass criteria
- All MVP criteria pass.
- `RK-SM-*`, `RK-UNK-*`, `RK-POL-*`, `RK-RBK-*`, `RK-CLS-*`, `RK-AUTH-*`, `RK-VSN-*`, `RK-FE-*` pass in staging or limited live canary.
- No P0 regressions in remediation closure or policy preservation.

### GA pass criteria
- All Safe Rollout criteria pass.
- `RK-GA-*` pass with production evidence.
- On-call/operator playbook completed and linked.

### Fail conditions (all gates)
- Any cross-tenant read/write leak.
- Any non-idempotent duplicate side effect after retry/replay.
- Any fail-open behavior on auth/validation/internal errors.
- Any plaintext secret exposure in orchestration logs/artifacts.

## 4) Evidence Checklist

| Artifact | MVP | Safe Rollout | GA |
|---|---|---|---|
| Migration logs (`upgrade`/`downgrade`) | Required | Optional | Optional |
| Unit test output for schema/store/model | Required | Required | Required |
| API auth/contract transcripts | Optional | Required | Required |
| Transition event timeline | Optional | Required | Required |
| Policy-preservation summary | Optional | Required | Required |
| Closure polling evidence | Optional | Required | Required |
| SLA/metrics report | Optional | Optional | Required |
| Runbook/operator sign-off | Optional | Required | Required |

## 5) Execution Checklist

1. Complete MVP tests and archive evidence.
2. Enable feature flags only in staging canary tenants.
3. Run Safe Rollout test cases and verify policy-preservation/closure outcomes.
4. Resolve all P0/P1 issues before GA decision.
5. Publish GA evidence packet and operator sign-off.
