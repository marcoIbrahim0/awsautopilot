# Phase 3 P1.6 Live Summary

- Run ID: `20260321T202330Z-phase3-p1-6-live`
- Date (UTC): `2026-03-21T20:23:30Z`
- Backend: `https://api.ocypheris.com`
- Jira base URL: `https://ocypheris.atlassian.net`
- Jira project key from browser session: `KAN`
- Final closure date (UTC): `2026-03-24T02:14:36Z`
- Result: `PASS`

## What passed

- Re-read the binding `.cursor` rules, project status, task history, docs index, feature docs, and prior March 12 P1 evidence before touching code or live.
- Reconfirmed the live tenant baseline on `Valens` (`9f7616d8-af04-43ca-99cd-713625357b70`) and the target action `0ca64b94-9dcb-4a97-91b0-27b0341865bc` (`EBS default encryption should be enabled`, status `open`).
- Confirmed live API auth and integration routes still respond after a fresh short-lived operator bearer minted from the current production JWT contract.
- Confirmed the live database is at `0049_action_group_metadata_only_bucket (head)`.
- Found and fixed a real P1.6 blocker in the code: inbound provider webhooks were still applying mapped external status onto `Action.status`, violating the remediation system-of-record contract.
- Fixed and deployed two additional live blockers uncovered during the rerun:
  - `backend/workers/jobs/attack_path_materialization.py` now uses an isolated async engine/session per Lambda invocation, which cleared the Lambda/Python 3.12 event-loop teardown poison on the shared ingest queue.
  - `backend/services/integration_sync.py` now makes reconciliation dedupe drift-aware, so repeat sync back to the same canonical provider state can be re-queued after real drift.
- Ran focused regression coverage after the final fixes:
  - `PYTHONPATH=. ./venv/bin/pytest tests/test_phase3_p1_5_integrations_bidirectional.py tests/test_phase3_p1_6_system_of_record_sync.py tests/test_attack_path_materialization_worker.py`
  - Result: `21 passed`
- Deployed the final live backend/worker runtime fixes with the standard serverless path.
- Verified both live Lambdas now run image tag `20260324T020950Z`.
- Revalidated post-deploy:
  - `GET /api/auth/me` -> `200`
  - `GET /api/integrations/settings` -> `200` with Jira enabled, webhook configured, and tenant mapping `open -> In Progress`
  - ingest queue health returned to zero visible and zero invisible messages
  - fresh worker logs no longer show `RuntimeError: Event loop is closed` or `attached to a different loop`
- Proven strict live Jira workflow on the retained issue `KAN-7`:
  1. live reconciliation restored the previously drifted Jira issue to `In Progress`
  2. real Jira drift was re-created by transitioning `KAN-7` to `Done`
  3. live webhook `jira-live-drift-final-20260324T0214Z` was accepted and processed
  4. `Action.status` remained `open`
  5. `action_remediation_sync_states` recorded `sync_status=drifted` and `preferred_external_status=In Progress`
  6. `action_remediation_sync_events` recorded `preserve_internal_canonical`
  7. final reconciliation request enqueued successfully
  8. a fresh outbound sync task row `c3225686-ba7d-4293-be35-244bddda143a` was created and completed `success`
  9. Jira returned to `In Progress`
  10. `action_external_links.external_status` returned to `In Progress`
  11. `action_remediation_sync_states.sync_status` returned to `in_sync`
  12. `action_remediation_sync_events` recorded both `reconciliation_queued` and `reconciliation_applied`

## Key evidence

- Runtime and queue health:
  - `evidence/runtime/66-api-function-reconcile-fix.json`
  - `evidence/runtime/66-worker-function-reconcile-fix.json`
  - `evidence/runtime/62-ingest-queue-health-before-final-rerun.json`
  - `evidence/runtime/72-worker-tail-final.log`
- Drift proof:
  - `evidence/jira/69-issue-kan-7-after-final-drift.json`
  - `evidence/api/70-jira-webhook-drift-final.body.json`
  - `evidence/db/70-post-final-webhook-drift-db.txt`
- Final reconciliation proof:
  - `evidence/api/71-reconciliation-request-final.body.json`
  - `evidence/jira/72-issue-kan-7-final-after-reconciliation.json`
  - `evidence/db/72-final-reconciliation-db.txt`

## P1.6 status on live

`PASS` on March 24, 2026.

Phase 3 P1.6 is now fully validated end to end on production for Jira with real provider drift, preserved internal canonical status, explicit drift recording, and successful reconciliation back to the platform’s configured preferred external state.
