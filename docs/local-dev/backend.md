# Backend Development

## Run API

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Endpoints:
- `GET /health`
- `GET /ready`
- `GET /health/ready`
- `PATCH /api/aws/accounts/{account_id}` now supports `role_read_arn`, `role_write_arn`, `regions`, and `status`; ReadRole/region updates revalidate STS before the account record is persisted.
- `POST /api/aws/accounts/{account_id}/validate` now fails closed with `200` + structured `warnings` / `authoritative_mode_block_reasons` when a required AWS probe cannot be executed (for example, AWS Config probe/runtime mismatch), instead of raising `500`.

Health semantics:
- `GET /health` is liveness-only and returns app process status.
- `GET /ready` and `GET /health/ready` require a successful DB ping plus supported SQS queue attribute reads; queue lag fields are best-effort CloudWatch metrics and do not fail readiness on their own.

Actions owner queues:
- `GET /api/actions` supports `owner_type`, `owner_key`, and `owner_queue=open|expiring|overdue|expiring_exceptions|blocked_fixes`.
- Action list/detail payloads now include `owner_type`, `owner_key`, `owner_label`, and additive `sla` metadata.
- Owner-queue responses include additive `owner_queue_counters` totals for `open`, `expiring`, `overdue`, `blocked_fixes`, and `expiring_exceptions`.
- Action list/detail payloads include `score`, `score_components`, and `score_factors`; when toxic-combination prioritization is enabled, `score_factors` can include a `toxic_combinations` entry.
- `GET /api/actions/{id}` also includes additive `context_incomplete` so action detail makes fail-closed toxic-combination gating explicit.
- `GET /api/actions/{id}` now also includes additive `execution_guidance[]` entries with mode-aware `blast_radius`, `pre_checks`, `expected_outcome`, `post_checks`, and `rollback` guidance per actionable strategy.
- `GET /api/actions/{id}` now also includes additive `implementation_artifacts[]` entries that deep-link engineering to the latest PR bundle, change summary, or direct-fix record for that action.
- `GET /api/remediation-runs/{id}` now also includes additive `artifact_metadata` with normalized `implementation_artifacts[]`, `evidence_pointers[]`, and `closure_checklist[]` while preserving the raw `artifacts` payload.
- Remediation-run deep links now rely on stable anchors in the UI contract: `#run-activity`, `#run-generated-files`, and `#run-closure`.

Toxic-combination config:
- `ACTIONS_TOXIC_COMBINATIONS_ENABLED`
- `ACTIONS_TOXIC_COMBINATION_MAX_BOOST`
- `ACTIONS_TOXIC_COMBINATION_RULES_JSON`

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

## Related

- [Environment setup](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/environment.md)
- [Worker development](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/worker.md)
