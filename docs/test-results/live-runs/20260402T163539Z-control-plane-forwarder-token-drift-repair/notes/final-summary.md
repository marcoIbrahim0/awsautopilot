# Final Summary

## Result

`PASS`. The remaining live control-plane freshness issue for account `696505809372` was caused by customer forwarder delivery/auth drift, and the real steady-state path is now re-proved in both `eu-north-1` and `us-east-1`.

No `S3.5` remediation bug was reopened:
- action `3970aa2f-edc5-4870-87bd-fa986dad3d98` remains `resolved`
- finding `69507c08-bbb8-491d-9ec0-543278d96a2b` remains `RESOLVED`
- the shadow overlay remains `RESOLVED` with `inventory_confirmed_compliant`

## Root Cause

The stale readiness issue was not in raw AWS and not in the SaaS readiness calculation.

Retained proof narrows the fault to the customer EventBridge forwarder path:
- pre-repair metrics in `evidence/metrics/pre-repair-eu-north-1.json` show real allowlisted events continued to match and invoke while `FailedInvocations` also stayed non-zero during the stale window
- the earlier retained April 2 diagnostic run had already shown synthetic control-plane events immediately turned readiness green, proving the SaaS intake/readiness path still worked when fresh supported input arrived
- the repaired customer stacks now prove the missing operator guardrail: `evidence/aws/connection-token-match-eu-north-1.json` and `evidence/aws/connection-token-match-us-east-1.json` both show the deployed EventBridge connection secret matches the tenant's current fingerprint `cptok-OA...hkhc`

The practical root cause is therefore forwarder credential/config drift on the customer side, not a broken SaaS runtime path.

## Live Repair

The live repair stayed narrow:
1. Rotated the tenant control-plane token on production and captured the new current fingerprint in `evidence/api/auth-me-postrepair.json`.
2. Updated both customer `SecurityAutopilotControlPlaneForwarder` stacks from the current repo template with the current token.
3. Verified both customer regions now include the expected DLQ/alarm resources:
   - `ControlPlaneTargetDLQ`
   - `ControlPlaneTargetDLQPolicy`
   - `ControlPlaneRuleFailedInvocationsAlarm`
   - `ControlPlaneTargetDLQDepthAlarm`
4. Added a repo-side operator guardrail:
   - `scripts/verify_control_plane_forwarder.sh` now fails in Phase 1 if `/api/auth/me control_plane_token_fingerprint` does not match the EventBridge connection secret stored in Secrets Manager
   - focused regression coverage was added in `tests/test_control_plane_forwarder_audit.py`

No serverless/runtime deploy was required for the live fix because the production SaaS intake path was already functioning; the broken component was the customer forwarder configuration.

## Production Verification

### Real live freshness

Fresh real CloudTrail evidence was retained for both safe account-level control-plane writes:
- `eu-north-1` event `8d899066-0163-4550-ada5-44535918ccc2`
- `us-east-1` event `3e5e847d-0b79-42a4-b6ad-f94dbc83e610`

Both came from real `PutAccountPublicAccessBlock` calls that simply reasserted the already-safe account-level public-access-block state.

Fresh DB rows in `evidence/db/control-plane-ingest-status-postrepair.tsv` prove the real path advanced:
- `eu-north-1`: `last_event_time=2026-04-02 16:28:36+00:00`, `last_intake_time=2026-04-02 16:28:43.797036+00:00`
- `us-east-1`: `last_event_time=2026-04-02 16:28:36+00:00`, `last_intake_time=2026-04-02 16:28:45.458799+00:00`

Fresh readiness proof in `evidence/api/readiness-postrepair.json` shows:
- `overall_ready=true`
- no missing regions
- both configured regions recent on real live events

Fresh worker persistence proof in `evidence/db/control-plane-events-postrepair.json` shows both events were ingested and safely marked `dropped` with `drop_reason=no_supported_targets_after_enrichment`, which is expected for account-level public-access-block events that advance freshness but do not create a bucket-scoped shadow target.

### EventBridge delivery health

Pre-repair metrics:
- `evidence/metrics/pre-repair-eu-north-1.json`: `MatchedEvents=142`, `Invocations=148`, `FailedInvocations=148`
- `evidence/metrics/pre-repair-us-east-1.json`: `MatchedEvents=3`, `Invocations=3`, `FailedInvocations=1`

Post-repair metrics:
- `evidence/metrics/post-repair-eu-north-1.json`: `MatchedEvents=1`, `Invocations=1`, `FailedInvocations=0`
- `evidence/metrics/post-repair-us-east-1.json`: `MatchedEvents=1`, `Invocations=1`, `FailedInvocations=0`

This is the key steady-state proof that the real upstream path is healthy again.

### Connection-token audit and verifier guardrail

Current customer forwarder secrets:
- `evidence/aws/connection-token-match-eu-north-1.json`: `matches_current_token=true`
- `evidence/aws/connection-token-match-us-east-1.json`: `matches_current_token=true`

Current customer verifier runs:
- `evidence/aws/verify-forwarder-eu-north-1.txt`
- `evidence/aws/verify-forwarder-us-east-1.txt`

Both now pass:
- `PASS Phase 1` wiring and token audit
- `PASS Phase 2` synthetic injection
- `PASS Phase 3` SaaS receipt/readiness confirmation

Synthetic events are retained only as the new operator guardrail check. The live closure decision above is based on the real CloudTrail events and real readiness/DB advancement.

### Logs

Filtered live log windows were retained in:
- `evidence/logs/api-window.json`
- `evidence/logs/worker-window.json`

These show the expected API and worker invocations in the same 16:28 UTC verification window as the real control-plane events.

## Local Validation

Focused local checks passed:

```bash
bash -n scripts/verify_control_plane_forwarder.sh
DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1/test' \
DATABASE_URL_FALLBACK='postgresql+asyncpg://postgres:postgres@127.0.0.1/test' \
PRIMARY_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1/test' \
PYTHONPATH=. /opt/homebrew/bin/pytest \
  tests/test_control_plane_forwarder_audit.py \
  tests/test_control_plane_token_lifecycle.py -q
```

Result:
- `10 passed`
- only existing local pytest config warnings about unknown `asyncio_*` config options under the Homebrew pytest environment

## Conclusion

The truthful terminal outcome is a deployed live repair plus a production-ready guardrail:
- real live control-plane freshness now advances again for account `696505809372`
- both customer regions are current on real events
- the customer forwarder connections now match the current tenant token
- the repo verifier now detects token drift before it can silently age readiness out again
