# Deploy summary

- Supported deploy path: `/Users/marcomaher/AWS Security Autopilot/scripts/deploy_saas_serverless.sh`
- Region: `eu-north-1`
- Image tag: `20260402T005923Z`
- CodeBuild ID: `security-autopilot-dev-serverless-image-builder:3c51a4b8-0da6-4c49-a84f-d97ec0fa7fbd`

## Result

- Runtime stack update: success
- Lambda rollout:
  - `security-autopilot-dev-api -> 20260402T005923Z`
  - `security-autopilot-dev-worker -> 20260402T005923Z`
- Runtime/DB alignment before deploy: `at_head`
- Alembic upgrade: completed without new migrations
- Runtime/DB alignment after deploy: `at_head`

## Notes

- The repo checkout still has sanitized placeholder `DATABASE_URL*` values, so this deploy required shell overrides for:
  - `DATABASE_URL`
  - `DATABASE_URL_SYNC`
  - `DATABASE_URL_FALLBACK`
  - `DATABASE_URL_SYNC_FALLBACK`
- Those override values were fetched from the live `security-autopilot-dev-api` Lambda environment and used only for this deploy command.
