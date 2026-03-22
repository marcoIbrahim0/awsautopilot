# Local Development Guide

Use this section to run API, worker, frontend, and tests locally.

## Canonical Runtime Env Files

- Backend runtime: `/Users/marcomaher/AWS Security Autopilot/backend/.env`
- Worker runtime: `/Users/marcomaher/AWS Security Autopilot/backend/workers/.env`
- Frontend public vars: `/Users/marcomaher/AWS Security Autopilot/frontend/.env`
- Deploy/ops scripts: `/Users/marcomaher/AWS Security Autopilot/config/.env.ops`
- Root `.env` is backup-only and not a runtime source.

## Start Here

1. [Environment setup](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/environment.md)
2. [Backend development](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/backend.md)
3. [Worker development](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/worker.md)
4. [Frontend development](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/frontend.md)
5. [Testing](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/tests.md)

## Common Commands

```bash
# migrate DB
./venv/bin/alembic current
./venv/bin/alembic heads
./venv/bin/alembic upgrade heads

# run API
./venv/bin/uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# run worker
PYTHONPATH=. ./venv/bin/python -m backend.workers.main

# run tests
PYTHONPATH=. ./venv/bin/pytest

# recompute actions safely for one tenant/account (idempotent)
PYTHONPATH=. ./venv/bin/python scripts/recompute_account_actions.py --tenant-id <TENANT_UUID> --account-id <ACCOUNT_ID> [--region <REGION>]
```

## Related

- [Docs index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/README.md)
- [Deployment guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/deployment/README.md)
