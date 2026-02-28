# Backend Development

## Run API

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Endpoints:
- `GET /health`
- `GET /ready`
- `GET /health/ready`

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
