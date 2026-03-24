# Persistent Action Groups and Compliance-Confirmed Success

## Overview

This feature introduces immutable, append-only action groups that are persisted in the database and used by the group UI and run lifecycle APIs.

Core guarantees:

- Group membership is immutable (`UNIQUE(action_id)` in memberships).
- Recompute only appends membership for newly created actions.
- Group counters are driven by `action_group_action_state`, not by ad-hoc execution outcomes.
- `run_successful_confirmed` can only come from trusted AWS confirmation signals.
- Successful PR bundle runs can now remain in a separate `run_successful_needs_followup` bucket when the bundle applied a safe additive change that is not expected to resolve the finding yet.

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
- Executable success is then classified into one of:
  - `run_successful_pending_confirmation` when the change should resolve after AWS source-of-truth catches up
  - `run_successful_needs_followup` when the change applied successfully but intentionally left a residual failing condition in place
- Success is only promoted to `run_successful_confirmed` by trusted post-run confirmation:
  - Security Hub finding resolved signal.
  - Control-plane reconcile/shadow resolved signal.
- Current explicit non-closing-success rule:
  - `sg_restrict_public_ports_guided` with `access_mode=close_public` adds restricted ingress but keeps the unrestricted public rule, so the finding stays open by design and the UI tells the user to remove the public rule.

No API path marks `run_successful_confirmed` directly from apply success.

## Bundle Run Reporting

Token service: `backend/services/bundle_reporting_tokens.py`

- Signed callback token claims:
  - `tenant_id`, `group_run_id`, `group_id`, `allowed_action_ids`, `exp`, `jti`.
- Callback endpoint:
  - `POST /api/internal/group-runs/report`
  - events: `started`, `finished`.
- Downloaded bundles emit callback events from wrapper runner script and persist replay payloads locally when callback delivery fails.
- Group bundle creation now fails closed for unchanged reruns:
  - active identical grouped requests still return `409`
  - latest successful identical grouped requests also return `409` with a no-changes reason until the canonical group membership or bundle-resolution inputs change

## Public APIs

Router: `backend/routers/action_groups.py`

- `GET /api/action-groups`
- `GET /api/action-groups/{group_id}`
- `GET /api/action-groups/{group_id}/runs`
- `POST /api/action-groups/{group_id}/bundle-run`

`GET /api/action-groups/{group_id}` also returns additive bundle-generation gating fields so the UI can disable unchanged reruns before submit:

- `can_generate_bundle`
- `blocked_reason`
- `blocked_detail`
- `blocked_by_run_id`

## Control ID Canonicalization

Findings can arrive under alias control IDs while action grouping and grouped remediation use the canonical remediation family for dedupe, run history, and bundle state.

Current canonicalization cases:

- `S3.3 -> S3.2` / `s3_bucket_block_public_access`
- `S3.8 -> S3.2` / `s3_bucket_block_public_access`
- `S3.13 -> S3.11` / `s3_bucket_lifecycle_configuration`
- `S3.17 -> S3.15` / `s3_bucket_encryption_kms`
- `EC2.13 -> EC2.53` / `sg_restrict_public_ports`
- `EC2.18 -> EC2.53` / `sg_restrict_public_ports`
- `EC2.19 -> EC2.53` / `sg_restrict_public_ports`

Practical effect:

- `GET /api/findings` can still show the source alias `control_id`.
- `GET /api/action-groups/{group_id}` member rows can show the canonical control ID instead.
- Pending-confirmation, grouped member status buckets, run history, and bundle-generation gating follow the canonical remediation family/member.

Example:

- `S3.8` findings can materialize into canonical grouped remediation family `S3.2` / `s3_bucket_block_public_access`, so the grouped view may show `S3.2` while the finding detail still shows `S3.8`.

## Backfill Job

- Worker: `worker/jobs/backfill_action_groups.py`
- Internal enqueue endpoint: `POST /api/internal/backfill-action-groups`

The backfill is chunked and idempotent. Legacy run mapping is best-effort and avoids ambiguous guessing.
