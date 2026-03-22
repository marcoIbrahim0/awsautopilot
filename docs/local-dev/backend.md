# Backend Development

## Run API

```bash
./venv/bin/uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Endpoints:
- `GET /health`
- `GET /ready`
- `GET /health/ready`
- `PATCH /api/aws/accounts/{account_id}` supports `role_read_arn`, `role_write_arn`, `regions`, and `status`; `role_write_arn` is deprecated/out of scope and is cleared, while ReadRole/region updates still revalidate STS before the account record is persisted.
- `POST /api/aws/accounts/{account_id}/validate` now fails closed with `200` + structured `warnings` / `authoritative_mode_block_reasons` when a required AWS probe cannot be executed (for example, AWS Config probe/runtime mismatch), instead of raising `500`.

Health semantics:
- `GET /health` is liveness-only and returns app process status.
- `GET /ready` and `GET /health/ready` require a successful DB ping plus supported SQS queue attribute reads; queue lag fields are best-effort CloudWatch metrics and do not fail readiness on their own.
- When queue-lag metric collection cannot be read, the readiness payload now returns stable `oldest_message_age_error` markers (`metric_access_denied` or `metric_unavailable`) instead of leaking raw AWS exception text into the response body.

Actions owner queues:
- `GET /api/actions` supports `owner_type`, `owner_key`, and `owner_queue=open|expiring|overdue|expiring_exceptions|blocked_fixes`.
- Action list/detail payloads now include `owner_type`, `owner_key`, `owner_label`, and additive `sla` metadata.
- Owner-queue responses include additive `owner_queue_counters` totals for `open`, `expiring`, `overdue`, `blocked_fixes`, and `expiring_exceptions`.
- Action list/detail payloads include `score`, `score_components`, and `score_factors`; `exploit_signals` can now carry additive threat-intel `provenance[]`, and toxic-combination prioritization can add a separate `toxic_combinations` factor.
- `GET /api/actions/{id}` also includes additive `context_incomplete` so action detail makes fail-closed toxic-combination gating explicit.
- `GET /api/actions/{id}` now also includes additive `execution_guidance[]` entries with PR-only `blast_radius`, `pre_checks`, `expected_outcome`, `post_checks`, and `rollback` guidance per actionable strategy.
- `GET /api/actions/{id}` now also includes additive `implementation_artifacts[]` entries that deep-link engineering to the latest PR bundle or change summary for that action; historical runs may still expose legacy direct-fix records.
- `GET /api/actions/{id}` now also includes additive `graph_context` with explicit `available` / `unavailable` status, bounded `connected_assets[]`, `identity_path[]`, `blast_radius_neighborhood[]`, and `truncated_sections[]` when conservative graph traversal caps are hit.
- `GET /api/actions/{id}` now also includes additive `attack_path_view` with explicit `available` / `partial` / `unavailable` / `context_incomplete` states plus bounded `path_nodes[]`, `path_edges[]`, `entry_points[]`, `target_assets[]`, and prioritization summaries derived from the existing detail contracts.
- `GET /api/actions/{id}` and `GET /api/actions/{id}/remediation-options` now also include additive `recommendation` with matrix-derived `default_mode`, effective `mode`, `advisory`, `enforced_by_policy`, `rationale`, `matrix_position`, and auditable `evidence`.
- `Action.status` is now the canonical remediation state system of record for platform actions; external systems cannot overwrite it directly.
- External provider drift now persists in `action_remediation_sync_states` and `action_remediation_sync_events`, with `sync_status` of `in_sync` or `drifted` plus source-aware audit decisions.
- `POST /api/internal/reconciliation/remediation-state-sync` enqueues `reconcile_action_remediation_sync` jobs so drifted Jira, ServiceNow, or Slack statuses can be reconciled back to the internal canonical state through the existing integration-sync queue.
- `GET /api/remediation-runs/{id}` now also includes additive `artifact_metadata` with normalized `implementation_artifacts[]`, `evidence_pointers[]`, and `closure_checklist[]` while preserving the raw `artifacts` payload.
- Remediation-run deep links now rely on stable anchors in the UI contract: `#run-activity`, `#run-generated-files`, and `#run-closure`.
- `POST /api/remediation-runs` and `POST /api/remediation-runs/group-pr-bundle` now accept additive optional `repo_target` metadata with `provider`, `repository`, `base_branch`, optional `head_branch`, and optional `root_path` for provider-agnostic PR payload generation.
- Strategy-backed `pr_only` run creation is now an observed client contract: frontend callers preflight `GET /api/actions/{id}/remediation-options`, choose a valid non-exception `pr_only` strategy from that payload, and send `strategy_id` plus any safely derivable `strategy_inputs` on `POST /api/remediation-runs` or `POST /api/remediation-runs/group-pr-bundle`.
- CloudTrail guided remediation options now expose specialized dependency checks instead of the unspecialized hard-fail fallback: `cloudtrail_cost_impact`, `cloudtrail_log_bucket_prereq`, and optional `cloudtrail_existing_trail_present`, plus runtime default trail context when `DescribeTrails` succeeds.
- Summary/grouped PR-bundle flows now fail closed on the client side when dependency checks require manual review, required inputs cannot be derived safely, or grouped actions do not converge on the same derived strategy payload.
- Successful PR-bundle runs now attach additive `diff_summary`, `rollback_notes`, and `control_mapping_context` artifacts; when `repo_target` is configured they also attach `pr_payload`.
- Downloaded PR bundle zips now include `pr_automation/diff_summary.json`, `pr_automation/rollback_notes.md`, `pr_automation/control_mapping_context.json`, and `pr_automation/pr_payload.json` when repository metadata is present.
- Historical direct-fix runs may still carry additive `artifacts.direct_fix_approval` metadata, but current `POST /api/remediation-runs` rejects new `direct_fix` requests and stays PR-only.
- Blocked unapproved direct-mutation attempts write `audit_log.event_type=remediation_mutation_blocked` before the run is finalized as failed.

Integration-first remediation ops:
- `GET /api/integrations/settings` lists the tenant's current provider settings for `jira`, `servicenow`, and `slack`, with `secret_configured` / `webhook_configured` booleans instead of raw secrets.
- `PATCH /api/integrations/settings/{provider}` accepts additive provider settings fields: `enabled`, `outbound_enabled`, `inbound_enabled`, `auto_create`, `reopen_on_regression`, `config`, `secret_config`, and `clear_secret_config`.
- `POST /api/integrations/actions/{id}/sync` plans a tenant-scoped outbound sync task for one action and enqueues `job_type=integration_sync` on the ingest queue.
- `POST /api/integrations/webhooks/{provider}` requires `X-Integration-Webhook-Token` and optional `X-External-Event-Id`; inbound events are receipt-key idempotent, can sync assignee metadata, and record external status drift without overwriting canonical `Action.status`.
- Provider links and sync persistence now live in tenant-scoped tables: `tenant_integration_settings`, `action_external_links`, `integration_sync_tasks`, `integration_event_receipts`, `action_remediation_sync_states`, and `action_remediation_sync_events`.

Tenant/user settings:
- `GET /api/users/me/governance-settings` returns the tenant-scoped governance notification toggle and webhook-configured state for the current user context.
- `PATCH /api/users/me/governance-settings` accepts additive governance settings updates: `governance_notifications_enabled` and `governance_webhook_url`; sending an empty string clears the stored webhook.
- `GET /api/users/me/remediation-settings` returns the current tenant remediation defaults, including approved CIDRs, bastion groups, CloudTrail defaults, Config defaults, S3 access-log defaults, and S3 encryption defaults.
- `PATCH /api/users/me/remediation-settings` accepts partial remediation-default updates and preserves omitted fields.

Toxic-combination config:
- `ACTIONS_TOXIC_COMBINATIONS_ENABLED`
- `ACTIONS_TOXIC_COMBINATION_MAX_BOOST`
- `ACTIONS_TOXIC_COMBINATION_RULES_JSON`

Threat-intelligence decay config:
- `ACTIONS_THREAT_INTELLIGENCE_HALF_LIFE_HOURS`

`ACTIONS_THREAT_INTELLIGENCE_HALF_LIFE_HOURS` controls decay for trusted exploit-signal weighting and defaults to `72` hours.

- Security Hub ingest now persists `finding.raw_json.relationship_context` from canonical finding metadata, and `scripts/backfill_finding_relationship_context.py` can enrich older Security Hub rows before a scoped action recompute:

```bash
PYTHONPATH=. ./venv/bin/python scripts/backfill_finding_relationship_context.py \
  --tenant-id <YOUR_TENANT_ID_HERE> \
  --account-id <YOUR_ACCOUNT_ID_HERE> \
  --region <YOUR_REGION_HERE> \
  --recompute-actions
```

`<YOUR_TENANT_ID_HERE>` is environment-specific; use the tenant you want to refresh.

Swagger:
- `http://localhost:8000/docs`

## Router Prefixes (mounted under `/api`)

- `/api/auth`
- `/api/aws/accounts`
- `/api/findings`
- `/api/actions`
- `/api/action-groups`
- `/api/remediation-runs`
- `/api/exceptions`
- `/api/exports`
- `/api/baseline-report`
- `/api/users`
- `/api/reconciliation`
- `/api/control-plane`
- `/api/integrations`
- `/api/internal`
- `/api/saas`
- `/api/support-files`
- `/api/meta`

## Auth Model

- Cookie session + CSRF is primary browser mode.
- Bearer token is supported for API-style calls.
- Signup has two valid local contracts:
  - `201 AuthResponse` when `FIREBASE_PROJECT_ID` is unset
  - `202 SignupPendingResponse` when Firebase email verification is enabled
- The Firebase flow also adds:
  - `POST /api/auth/verify/resend`
  - `POST /api/auth/verify/firebase-sync`
  - `/verify-email/pending` and `/verify-email/callback` on the frontend
- In the current fallback, signup verification email delivery is Firebase-managed from the frontend. SMTP is not required for the signup verification path.

## Quick API Smoke

```bash
# health
curl http://localhost:8000/health

# signup
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Test Tenant","name":"Test User","email":"test@example.com","password":"password123"}'

# login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

## Migration Guard

Startup enforces DB head revision by default via `DB_REVISION_GUARD_ENABLED=true`.

Serverless note:
- local `uvicorn` still enforces the DB head revision during FastAPI startup/lifespan
- Lambda serverless runtime now memoizes both FastAPI bootstrap and the DB revision guard on first invocation in [`backend/lambda_handler.py`](/Users/marcomaher/AWS%20Security%20Autopilot/backend/lambda_handler.py), so the runtime no longer spends its init phase on import-time schema checks

## Related

- [Environment setup](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/environment.md)
- [Worker development](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/worker.md)
- [Integration-first remediation operations](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/integration-first-remediation-operations.md)
- [Repo-aware PR automation](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/repo-aware-pr-automation.md)
- [Remediation system-of-record sync](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/remediation-system-of-record-sync.md)
- [Recommendation mode matrix](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/recommendation-mode-matrix.md)
- [Integration-first remediation operations](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/integration-first-remediation-operations.md)
