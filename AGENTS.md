# AWS Security Autopilot Agent Guide

This repository requires explicit startup reads on every task. Treat `.cursor/` as the binding source of truth for workflow, review, and documentation rules.

## Required Startup Reads

Before doing any work, read these in order:

1. [.cursor/rules/core-behavior.mdc](/Users/marcomaher/AWS%20Security%20Autopilot/.cursor/rules/core-behavior.mdc)
2. [.cursor/rules/console-protocol.mdc](/Users/marcomaher/AWS%20Security%20Autopilot/.cursor/rules/console-protocol.mdc)
3. [.cursor/rules/production-docs-protection.mdc](/Users/marcomaher/AWS%20Security%20Autopilot/.cursor/rules/production-docs-protection.mdc)
4. [.cursor/notes/project_status.md](/Users/marcomaher/AWS%20Security%20Autopilot/.cursor/notes/project_status.md)
5. [.cursor/notes/task_index.md](/Users/marcomaher/AWS%20Security%20Autopilot/.cursor/notes/task_index.md)
6. Relevant sections in [.cursor/notes/task_log.md](/Users/marcomaher/AWS%20Security%20Autopilot/.cursor/notes/task_log.md) and any referenced archive/history notes
7. [docs/README.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/README.md)

If the task touches docs, identify affected documents before editing code and update the docs in the same task.

## Binding Repo Rules

- `.cursor/` instructions override generic agent habits.
- If the task is ambiguous, clarify before changing files.
- Before writing code or docs, provide a short step-by-step plan and wait for approval.
- Do not assume AWS service or control names; verify them against repo source and current docs first.
- Treat [/docs/Production/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/Production/) as protected. Edit it only when the user explicitly asks for it.
- Root `master` is the only authoritative branch for deployable code.
- `frontend/` is ordinary tracked monorepo content. Do not recreate a separate frontend repo, gitlink, or submodule workflow.
- Production frontend deploys must run from `/Users/marcomaher/AWS Security Autopilot/frontend` inside the root repo on `master`.
- After every successful task, update:
  - [.cursor/notes/task_log.md](/Users/marcomaher/AWS%20Security%20Autopilot/.cursor/notes/task_log.md)
  - [.cursor/notes/task_index.md](/Users/marcomaher/AWS%20Security%20Autopilot/.cursor/notes/task_index.md)
- Documentation is part of the task, not follow-up work.

## Canonical Env And Runtime Files

- Backend runtime: [/Users/marcomaher/AWS Security Autopilot/backend/.env](/Users/marcomaher/AWS%20Security%20Autopilot/backend/.env)
- Worker runtime: [/Users/marcomaher/AWS Security Autopilot/backend/workers/.env](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/.env)
- Frontend public vars: [/Users/marcomaher/AWS Security Autopilot/frontend/.env](/Users/marcomaher/AWS%20Security%20Autopilot/frontend/.env)
- Deploy/ops scripts: [/Users/marcomaher/AWS Security Autopilot/config/.env.ops](/Users/marcomaher/AWS%20Security%20Autopilot/config/.env.ops)
- Root `.env` is backup-only and not a runtime source.

## Canonical Daily Commands

Run these from the repo root. Prefer `./venv/bin/*` over `./.venv/*` in this workspace.

```bash
# migrations
./venv/bin/alembic current
./venv/bin/alembic heads
./venv/bin/alembic upgrade heads

# API
./venv/bin/uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# worker
PYTHONPATH=. ./venv/bin/python -m backend.workers.main

# tests
PYTHONPATH=. ./venv/bin/pytest

# frontend
cd frontend && npm install && npm run dev
```

## Scoped Maintenance Commands

```bash
# recompute actions safely for one tenant/account scope
PYTHONPATH=. ./venv/bin/python scripts/recompute_account_actions.py \
  --tenant-id <TENANT_UUID> \
  --account-id <ACCOUNT_ID> \
  [--region <REGION>]

# backfill relationship_context for existing Security Hub findings
PYTHONPATH=. ./venv/bin/python scripts/backfill_finding_relationship_context.py \
  --tenant-id <TENANT_UUID> \
  --account-id <ACCOUNT_ID> \
  --region <REGION> \
  --recompute-actions

# no-UI PR-bundle validation flow
PYTHONPATH=. ./venv/bin/python scripts/run_no_ui_pr_bundle_agent.py \
  --api-base https://api.ocypheris.com \
  --account-id 029037611564 \
  --region eu-north-1
```

## Operator And Deploy Workflows

- Serverless deploy path: [/Users/marcomaher/AWS Security Autopilot/scripts/deploy_saas_serverless.sh](/Users/marcomaher/AWS%20Security%20Autopilot/scripts/deploy_saas_serverless.sh)
- The serverless deploy script updates runtime images/config only. After every runtime deploy, run the DB upgrade separately against the same database:

```bash
/bin/zsh -lc 'set -a; source config/.env.ops; set +a; ./venv/bin/alembic upgrade heads'
```

- If the migration guard blocks startup, use the same `config/.env.ops` sourcing pattern and then re-run:

```bash
/bin/zsh -lc 'set -a; source config/.env.ops; set +a; ./venv/bin/python scripts/check_migration_gate.py'
```

## Advanced Grouped-Bundle / Wave 6 Notes

These are advanced debugging or retained live-proof workflows, not the default day-to-day path.

- Grouped customer-run bundles execute through `run_all.sh` and should be run with the target AWS mutation profile:

```bash
AWS_PROFILE=<TARGET_PROFILE> AWS_REGION=eu-north-1 bash ./run_all.sh
```

- If the generated callback host does not resolve locally, replay the saved callback payloads against `POST /api/internal/group-runs/report` on the retained local API.
- Current grouped-runner fixes expect `~/.terraform.d/plugin-cache` to serve as the AWS provider mirror and the runner logic to stay aligned with `hashicorp/aws 5.100.0`.
- Grouped customer-run bundles now always source the checked-in `infrastructure/templates/run_all.sh` template; there is no external S3 runner override in the active contract.

## Key Links

- [Documentation index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/README.md)
- [Local development guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/README.md)
- [Deployment guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/deployment/README.md)
- [Runbooks index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/runbooks/README.md)
- [No-UI PR bundle agent runbook](/Users/marcomaher/AWS%20Security%20Autopilot/docs/runbooks/no-ui-pr-bundle-agent.md)
- [S3 PR-bundle E2E debug plan](/Users/marcomaher/AWS%20Security%20Autopilot/docs/runbooks/s3-pr-bundle-e2e-debug-plan.md)
- [Live SaaS E2E tracker runbook](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/live-saas-e2e-tracker-runbook.md)
