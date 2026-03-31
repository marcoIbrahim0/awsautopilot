# Jira Remediation Sync Runbook

This runbook is the operator-facing guide for configuring Jira, proving provider drift handling, and debugging reconciliation for the Phase 3 `P1.5` and `P1.6` integration contracts.

> ❓ Needs verification: Run the new staged canary and retained production proof against a dedicated Jira canary project/workflow using the signed admin-webhook path described below.

Related docs:
- [Integration-first remediation operations](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/integration-first-remediation-operations.md)
- [Remediation system-of-record sync](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/remediation-system-of-record-sync.md)
- [Live P1.6 Jira production proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260321T202330Z-phase3-p1-6-live/notes/final-summary.md)

## What This Covers

Use this runbook when you need to:

- configure Jira for a tenant
- trigger manual outbound ticket sync
- validate inbound webhook behavior
- prove that Jira drift does not overwrite `Action.status`
- run reconciliation back to the platform's canonical state
- debug the known live failure modes that were discovered and fixed during the March 21-24, 2026 production proof

## Required Jira Settings

The Jira integration requires these fields on `PATCH /api/integrations/settings/jira`:

| Field | Location | Required | Notes |
| --- | --- | --- | --- |
| `base_url` | `config.base_url` | yes | Jira Cloud site root, for example `https://ocypheris.atlassian.net` |
| `project_key` | `config.project_key` | yes | Jira project key, for example `KAN` |
| `user_email` | `secret_config.user_email` | yes | Atlassian account email that owns the API token |
| `api_token` | `secret_config.api_token` | yes | Atlassian API token, paired with the same email above |
| `webhook_token` | `secret_config.webhook_token` | no | Legacy shared secret fallback for inbound webhook calls; keep only while migrating older tenants |

Optional Jira fields already supported:

- `config.issue_type`
- `config.transition_map`
- `config.status_mapping`
- `config.external_status_mapping`
- `config.assignee_account_map`
- `config.canary_action_id`

Server-managed Jira webhook state:

- `config.health`
- `config.webhook_id`
- `config.webhook_name`
- `config.webhook_url`
- `secret_json.webhook_secret`

## How To Get The Jira Values

### `config.base_url`

Use the Jira site root only, not a login redirect URL.

Example:

```text
https://ocypheris.atlassian.net
```

### `config.project_key`

Open the Jira project and capture the short project key from the project sidebar or project settings.

The proven production proof used:

```text
KAN
```

### `secret_config.user_email`

Use the Atlassian account email for the user that owns the API token. The token must be paired with the same email when Jira REST calls are made.

For the retained live proof, the correct pair was:

```text
maromaher54@gmail.com
```

### `secret_config.api_token`

Create the token in Atlassian account security and copy it once at creation time. Atlassian does not let operators read an existing token value back later.

Console path:

**Atlassian account > Security > API tokens**

### `secret_config.webhook_token`

Generate a strong random shared secret locally. This token is not provided by Atlassian.

Example:

```bash
openssl rand -hex 32
```

This field is now a migration fallback only. New Jira validation should prefer the product-managed signed admin-webhook flow.

## Proven Live Tenant Configuration

The March 24, 2026 production proof passed with this Jira configuration shape:

```json
{
  "enabled": true,
  "outbound_enabled": true,
  "inbound_enabled": true,
  "auto_create": true,
  "reopen_on_regression": true,
  "config": {
    "base_url": "https://ocypheris.atlassian.net",
    "project_key": "KAN",
    "status_mapping": {
      "open": "In Progress",
      "in_progress": "In Progress",
      "resolved": "Done",
      "suppressed": "Done"
    },
    "transition_map": {
      "in progress": "11",
      "done": "31"
    },
    "assignee_account_map": {
      "<YOUR_PLATFORM_OWNER_KEY>": "<YOUR_JIRA_ACCOUNT_ID>"
    },
    "canary_action_id": "<YOUR_CANARY_ACTION_UUID>"
  },
  "secret_config": {
    "user_email": "<YOUR_JIRA_USER_EMAIL>",
    "api_token": "<YOUR_JIRA_API_TOKEN>"
  }
}
```

Why this differs from the default Jira table:

- the default canonical-to-Jira `open -> To Do` mapping is documented in the feature spec
- the proved live `KAN` workflow did not expose a workable path back to `To Do`
- the tenant-level `status_mapping` therefore made `In Progress` the preferred external state for both `open` and `in_progress`

## Configure Jira On A Tenant

Example:

```bash
curl -X PATCH https://api.ocypheris.com/api/integrations/settings/jira \
  -H "Authorization: Bearer <YOUR_JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "outbound_enabled": true,
    "inbound_enabled": true,
    "auto_create": true,
    "reopen_on_regression": true,
    "config": {
      "base_url": "https://ocypheris.atlassian.net",
      "project_key": "KAN",
      "status_mapping": {
        "open": "In Progress",
        "in_progress": "In Progress",
        "resolved": "Done",
        "suppressed": "Done"
      },
      "transition_map": {
        "in progress": "11",
        "done": "31"
      }
    },
    "secret_config": {
      "user_email": "<YOUR_JIRA_USER_EMAIL>",
      "api_token": "<YOUR_JIRA_API_TOKEN>",
      "webhook_token": "<YOUR_JIRA_WEBHOOK_TOKEN>"
    }
  }'
```

Verify with:

```bash
curl -H "Authorization: Bearer <YOUR_JWT>" \
  https://api.ocypheris.com/api/integrations/settings
```

## Product-Managed Jira Admin Actions

Use these admin-only product endpoints after saving the Jira settings:

- `POST /api/integrations/settings/jira/validate`
- `POST /api/integrations/settings/jira/webhook/sync`
- `POST /api/integrations/settings/jira/canary-sync`

Expected Jira settings health fields from `GET /api/integrations/settings`:

- `health.status`
- `health.credentials_valid`
- `health.project_valid`
- `health.issue_type_valid`
- `health.transition_map_valid`
- `health.webhook_registered`
- `health.signed_webhook_enabled`
- `health.webhook_mode`
- `health.last_validated_at`
- `health.last_inbound_at`
- `health.last_outbound_at`
- `health.last_provider_error`

Suggested operator sequence:

1. Save Jira credentials and config.
2. `POST /api/integrations/settings/jira/validate`
3. `POST /api/integrations/settings/jira/webhook/sync`
4. Confirm `health.webhook_registered=true` and `health.signed_webhook_enabled=true`.
5. Run `POST /api/integrations/settings/jira/canary-sync` using `config.canary_action_id` or an explicit request body.

Example validation request:

```bash
curl -X POST https://api.ocypheris.com/api/integrations/settings/jira/validate \
  -H "Authorization: Bearer <YOUR_JWT>"
```

Example webhook registration / repair:

```bash
curl -X POST https://api.ocypheris.com/api/integrations/settings/jira/webhook/sync \
  -H "Authorization: Bearer <YOUR_JWT>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Rotate the Jira webhook secret only when you are ready to update the Jira admin webhook immediately:

```bash
curl -X POST https://api.ocypheris.com/api/integrations/settings/jira/webhook/sync \
  -H "Authorization: Bearer <YOUR_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"rotate_secret": true}'
```

Queue the dedicated canary action:

```bash
curl -X POST https://api.ocypheris.com/api/integrations/settings/jira/canary-sync \
  -H "Authorization: Bearer <YOUR_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"action_id":"<YOUR_CANARY_ACTION_UUID>"}'
```

## Discover Jira Transition IDs

Do not invent transition IDs. Fetch them from Jira for the actual workflow attached to the issue.

Example:

```bash
curl -u "<YOUR_JIRA_USER_EMAIL>:<YOUR_JIRA_API_TOKEN>" \
  -H "Accept: application/json" \
  "https://ocypheris.atlassian.net/rest/api/3/issue/KAN-7/transitions"
```

Use the returned IDs to populate `config.transition_map`.

For the retained live proof:

- `In Progress` used transition `11`
- `Done` used transition `31`

## Manual Outbound Sync

Trigger outbound creation/update manually:

```bash
curl -X POST \
  -H "Authorization: Bearer <YOUR_JWT>" \
  "https://api.ocypheris.com/api/integrations/actions/<YOUR_ACTION_ID>/sync"
```

Expected outcome:

- one `integration_sync_tasks` row is created or reused appropriately
- Jira issue is created or updated
- `action_external_links` stores Jira issue key/id and external status

For the retained proof:

- action `0ca64b94-9dcb-4a97-91b0-27b0341865bc`
- Jira issue `KAN-7`

## Create Real Jira Drift

Move the Jira issue to a conflicting status with Jira REST using the discovered transition ID.

Example transition to `Done`:

```bash
curl -X POST \
  -u "<YOUR_JIRA_USER_EMAIL>:<YOUR_JIRA_API_TOKEN>" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  "https://ocypheris.atlassian.net/rest/api/3/issue/KAN-7/transitions" \
  -d '{"transition":{"id":"31"}}'
```

Then read the issue back and capture its status:

```bash
curl -u "<YOUR_JIRA_USER_EMAIL>:<YOUR_JIRA_API_TOKEN>" \
  -H "Accept: application/json" \
  "https://ocypheris.atlassian.net/rest/api/3/issue/KAN-7"
```

## Send The Inbound Webhook

The inbound Jira webhook route is:

- `POST /api/integrations/webhooks/jira`

Headers:

- `X-Hub-Signature`
- `X-External-Event-Id`

Legacy fallback header still accepted during migration:

- `X-Integration-Webhook-Token`

Minimum practical payload shape:

```json
{
  "issue": {
    "id": "10000",
    "key": "KAN-7",
    "self": "https://ocypheris.atlassian.net/rest/api/3/issue/10000",
    "fields": {
      "status": {
        "name": "Done"
      }
    }
  },
  "timestamp": 1774313640000
}
```

Example legacy fallback replay:

```bash
curl -X POST https://api.ocypheris.com/api/integrations/webhooks/jira \
  -H "Content-Type: application/json" \
  -H "X-Integration-Webhook-Token: <YOUR_JIRA_WEBHOOK_TOKEN>" \
  -H "X-External-Event-Id: jira-live-drift-<UNIQUE_ID>" \
  -d '{
    "issue": {
      "id": "10000",
      "key": "KAN-7",
      "self": "https://ocypheris.atlassian.net/rest/api/3/issue/10000",
      "fields": {
        "status": {
          "name": "Done"
        }
      }
    },
    "timestamp": 1774313640000
  }'
```

For the signed admin-webhook path, Jira should send `X-Hub-Signature: sha256=<HMAC_HEX>` over the raw JSON request body using the product-managed webhook secret stored in `secret_json.webhook_secret`.

## What To Verify After The Webhook

The webhook must not overwrite the platform's canonical remediation state.

Verify:

- `Action.status` is unchanged
- `action_remediation_sync_states.sync_status = drifted`
- `action_remediation_sync_states.preferred_external_status` matches the tenant Jira mapping
- latest `action_remediation_sync_events` row records `resolution_decision = preserve_internal_canonical`
- `integration_event_receipts` shows the webhook receipt as processed
- action detail now exposes a Jira `External Sync` panel with the link key/URL, external status, sync state, assignee mapping state, and recent sync-event timeline

Useful DB checks:

```sql
select id, status
from actions
where id = '<YOUR_ACTION_ID>';

select provider, external_ref, external_status, canonical_internal_status, preferred_external_status, sync_status, resolution_decision, conflict_reason
from action_remediation_sync_states
where tenant_id = '<YOUR_TENANT_ID>' and action_id = '<YOUR_ACTION_ID>' and provider = 'jira';

select event_type, source, external_status, internal_status_before, internal_status_after, mapped_internal_status, preferred_external_status, resolution_decision, decision_detail, created_at
from action_remediation_sync_events
where tenant_id = '<YOUR_TENANT_ID>' and action_id = '<YOUR_ACTION_ID>' and provider = 'jira'
order by created_at desc
limit 10;

select provider, receipt_key, processing_status, created_at
from integration_event_receipts
where tenant_id = '<YOUR_TENANT_ID>' and provider = 'jira'
order by created_at desc
limit 10;
```

## Run Reconciliation

Use the internal scheduler endpoint documented in the remediation system-of-record spec.

Example:

```bash
curl -X POST https://api.ocypheris.com/api/internal/reconciliation/remediation-state-sync \
  -H "Content-Type: application/json" \
  -H "X-Reconciliation-Scheduler-Secret: <YOUR_RECONCILIATION_SCHEDULER_SECRET>" \
  -d '{
    "tenant_id": "<YOUR_TENANT_ID>",
    "provider": "jira",
    "action_ids": ["<YOUR_ACTION_ID>"],
    "limit": 50
  }'
```

Verify:

- a fresh `integration_sync_tasks` row is queued
- the row reaches `success`
- Jira moves back to the tenant's preferred external status
- `action_external_links.external_status` matches Jira
- `action_remediation_sync_states.sync_status = in_sync`
- latest `action_remediation_sync_events` rows include `reconciliation_queued` and `reconciliation_applied`

## Expected Live End State

For the proven March 24 production slice:

- canonical action status remained `open`
- drifted Jira status was `Done`
- preferred Jira status was `In Progress`
- reconciliation returned Jira `KAN-7` to `In Progress`
- sync ledger returned to `in_sync`

## Current UI Checks

The Jira settings card should now show:

- credentials validity
- webhook registration state
- signed-webhook mode
- last validation timestamp
- last inbound and outbound sync timestamps
- last provider error

The single-action detail modal should now show a Jira `External Sync` panel whenever a Jira link exists, including:

- Jira issue key / URL
- external Jira status
- current sync state (`in_sync` or `drifted`)
- preferred Jira status
- assignee mapping state
- recent sync-event timeline

## Known Failure Modes And Fixes

### Jira token authenticates with the wrong email

Symptom:

- Jira REST returns `401 AUTHENTICATED_FAILED`

Cause:

- the API token is being paired with the wrong Atlassian email

Fix:

- verify the Atlassian account email that owns the token
- retest with `GET /rest/api/3/myself`

The retained live proof initially failed because the token was first paired with `marcoibrahim11@outlook.com` and only worked when paired with `maromaher54@gmail.com`.

### Jira workflow cannot reconcile back to the default `To Do`

Symptom:

- outbound sync succeeds in one direction but no truthful transition path exists back to the default preferred status

Cause:

- the Jira project workflow differs from the default Jira mapping table

Fix:

- fetch real transition IDs from Jira
- set tenant `status_mapping` and `transition_map` to match the actual project workflow

### Worker queue poison from `attack_path_materialization`

Symptom:

- shared ingest queue stops draining correctly
- worker logs show `RuntimeError: Event loop is closed`
- worker logs show `attached to a different loop`

Cause:

- the old attack-path worker path reused the shared async engine across Lambda event loops on Python 3.12

Fix:

- use the isolated async session/engine path now implemented in:
  - [backend/database.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/database.py)
  - [backend/workers/jobs/attack_path_materialization.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/jobs/attack_path_materialization.py)

### Reconciliation does not enqueue a fresh outbound sync after repeat drift

Symptom:

- sync state is still `drifted`
- reconciliation job runs
- no new outbound Jira task is created because the canonical payload matches a prior successful request

Cause:

- the old request-signature dedupe did not account for drift-version changes

Fix:

- use the drift-aware outbound signature behavior now implemented in [backend/services/integration_sync.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/integration_sync.py)

## Evidence Reference

The strict live proof for this runbook lives at:

- [Phase 3 P1.6 live Jira production proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260321T202330Z-phase3-p1-6-live/notes/final-summary.md)

Most useful retained artifacts:

- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260321T202330Z-phase3-p1-6-live/notes/final-summary.md)
- [Post-final webhook drift DB snapshot](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260321T202330Z-phase3-p1-6-live/evidence/db/70-post-final-webhook-drift-db.txt)
- [Final reconciliation DB snapshot](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260321T202330Z-phase3-p1-6-live/evidence/db/72-final-reconciliation-db.txt)
- [Final Jira webhook payload evidence](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260321T202330Z-phase3-p1-6-live/evidence/api/70-jira-webhook-drift-final.body.json)
- [Final reconciliation request evidence](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260321T202330Z-phase3-p1-6-live/evidence/api/71-reconciliation-request-final.body.json)
