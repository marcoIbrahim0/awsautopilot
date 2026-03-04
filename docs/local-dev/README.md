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
alembic upgrade head

# run API
uvicorn backend.main:app --reload

# run worker
PYTHONPATH=. python -m backend.workers.main

# run tests
pytest

# recompute actions safely for one tenant/account (idempotent)
PYTHONPATH=. ./venv/bin/python scripts/recompute_account_actions.py --tenant-id <TENANT_UUID> --account-id <ACCOUNT_ID> [--region <REGION>]
```

## Related

- [Docs index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/README.md)
- [Deployment guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/deployment/README.md)
