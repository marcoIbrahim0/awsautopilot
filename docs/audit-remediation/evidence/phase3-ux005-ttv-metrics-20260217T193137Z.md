# UX-005 Onboarding Time-to-Value Metrics

- Captured at: `2026-02-17T19:31:37Z`
- Scope: onboarding first-value trigger timing (`integration_role_validated` -> first ingest queue trigger)
- Implementation references:
  - `/Users/marcomaher/AWS Security Autopilot/frontend/src/app/onboarding/page.tsx`
  - `/Users/marcomaher/AWS Security Autopilot/backend/routers/aws_accounts.py`

## Metric Summary

| Metric | Before UX-005 | After UX-005 | Delta |
|---|---:|---:|---:|
| First ingest trigger step | `processing` | `security-hub-config` | Earlier by 2 required gates |
| Blocking required gate checks before first ingest | 4 | 2 | -2 |
| Estimated time to first ingest trigger | 360s | 180s | -180s (-50.0%) |

## Measurement Method

1. Replay onboarding control flow from code paths (pre-change vs post-change trigger points).
2. Count required blocking gate checks between integration role validation and first ingest queue trigger.
3. Apply consistent modeling assumption of 90s per required gate check.

Assumption source:
- Onboarding welcome copy states estimated setup time of 12-20 minutes.
- 90s per required gate check models the lower-bound path consistently for before/after comparison.

## Interpretation

- UX-005 moves first ingest queueing from the final `processing` step to the `security-hub-config` step when safe.
- Required blocking gates remain enforced for onboarding completion:
  - Inspector
  - Security Hub
  - AWS Config
  - Control-plane readiness
- Only non-critical checks are async in flow (`Access Analyzer`).

> ❓ Needs verification: confirm modeled deltas with production onboarding telemetry once live tenant samples are available.
