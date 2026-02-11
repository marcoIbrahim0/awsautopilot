# Persistent Action Groups and Compliance-Confirmed Success

## Overview

This feature introduces immutable, append-only action groups that are persisted in the database and used by the group UI and run lifecycle APIs.

Core guarantees:

- Group membership is immutable (`UNIQUE(action_id)` in memberships).
- Recompute only appends membership for newly created actions.
- Group counters are driven by `action_group_action_state`, not by ad-hoc execution outcomes.
- `run_successful_confirmed` can only come from trusted AWS confirmation signals.

## Data Model

Migration: `alembic/versions/0030_action_groups_persistent.py`

Tables:

- `action_groups`
- `action_group_memberships`
- `action_group_runs`
- `action_group_run_results`
- `action_group_action_state`

The migration includes additive backfill for existing actions into groups/memberships and initializes state rows to `not_run_yet`.

## Confirmation Semantics

Service: `backend/services/action_run_confirmation.py`

- Execution attempts/results always move state to `run_not_successful`.
- Success is only promoted by trusted post-run confirmation:
  - Security Hub finding resolved signal.
  - Control-plane reconcile/shadow resolved signal.

No API path marks `run_successful_confirmed` directly from apply success.

## Bundle Run Reporting

Token service: `backend/services/bundle_reporting_tokens.py`

- Signed callback token claims:
  - `tenant_id`, `group_run_id`, `group_id`, `allowed_action_ids`, `exp`, `jti`.
- Callback endpoint:
  - `POST /api/internal/group-runs/report`
  - events: `started`, `finished`.
- Downloaded bundles emit callback events from wrapper runner script and persist replay payloads locally when callback delivery fails.

## Public APIs

Router: `backend/routers/action_groups.py`

- `GET /api/action-groups`
- `GET /api/action-groups/{group_id}`
- `GET /api/action-groups/{group_id}/runs`
- `POST /api/action-groups/{group_id}/bundle-run`

## Backfill Job

- Worker: `worker/jobs/backfill_action_groups.py`
- Internal enqueue endpoint: `POST /api/internal/backfill-action-groups`

The backfill is chunked and idempotent. Legacy run mapping is best-effort and avoids ambiguous guessing.
