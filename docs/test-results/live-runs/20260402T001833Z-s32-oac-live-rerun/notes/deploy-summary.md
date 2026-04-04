# Deploy Summary

- Supported deploy path: `/Users/marcomaher/AWS Security Autopilot/scripts/deploy_saas_serverless.sh`
- Region: `eu-north-1`
- Image tag: `20260402T002927Z`
- CodeBuild ID: `security-autopilot-dev-serverless-image-builder:7f09641c-d260-4405-9e3c-840fe73200bd`

## Result

- Runtime stack update: success
- Lambda rollout:
  - `security-autopilot-dev-api -> 20260402T002927Z`
  - `security-autopilot-dev-worker -> 20260402T002927Z`
- Runtime/DB alignment before deploy: `at_head`
- Alembic upgrade: completed without new migrations
- Runtime/DB alignment after deploy: `at_head`

## Notes

- The deploy was required after the first live rerun exposed invalid Terraform syntax in the newly generated S3.2 bundle.
- No `/docs/Production/` edits were required for this task.
