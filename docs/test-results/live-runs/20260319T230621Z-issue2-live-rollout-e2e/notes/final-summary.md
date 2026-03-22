# Issue 2 Live Rollout And E2E Summary (2026-03-19/20 UTC)

## Scope

Targeted live rollout and validation for issue 2:

- publish the new ReadRole and WriteRole templates with staged execution-role narrowing
- deploy the live serverless runtime with `SAAS_EXECUTION_ROLE_ARNS`
- verify the live API advertises the new template versions and execution-role launch parameters
- verify the live frontend preserves `param_SaaSExecutionRoleArns` in user-visible Launch Stack flows

## What shipped live

- Published customer templates:
  - `read-role/v1.5.6.yaml`
  - `write-role/v1.4.4.yaml`
- Deployed the serverless runtime successfully after patching the deploy script to resolve missing runtime secrets from Secrets Manager when not present in `config/.env.ops`.
- Ran the required post-deploy migration:

```bash
/bin/zsh -lc 'set -a; source config/.env.ops; set +a; ./venv/bin/alembic upgrade heads'
```

- Verified live runtime state:
  - `GET https://api.ocypheris.com/health` -> `200`
  - `GET https://api.ocypheris.com/ready` -> `ready=true`
  - both live Lambdas now expose `SAAS_EXECUTION_ROLE_ARNS=arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-api,arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-worker`

## Live validation

### API

Authenticated live API evidence is stored under:

- [issue2-api-summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260319T230621Z-issue2-live-rollout-e2e/evidence/api/issue2-api-summary.json)
- [auth-me.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260319T230621Z-issue2-live-rollout-e2e/evidence/api/auth-me.json)
- [validate.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260319T230621Z-issue2-live-rollout-e2e/evidence/api/validate.json)

Confirmed live API behavior:

- `GET /api/auth/me` now advertises:
  - `read_role_template_url=https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/read-role/v1.5.6.yaml`
  - `write_role_template_url=https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/write-role/v1.4.4.yaml`
- the live ReadRole launch URL includes `param_SaaSExecutionRoleArns`
- the connected live account `696505809372` is still returned, but `POST /api/aws/accounts/696505809372/validate` currently returns `status=error`

Interpretation:

- the SaaS-side rollout is live
- the existing customer ReadRole trust policy for account `696505809372` has not yet been updated to the new contract that allows tagged/source-identity assume-role traffic

### Browser

Initial live browser smoke proved the authenticated Accounts page rendered, but it also exposed a frontend regression:

- custom Launch Stack URL builders were rebuilding CloudFormation URLs with `SaaSAccountId` and `ExternalId` only
- that dropped `param_SaaSExecutionRoleArns` whenever the stack name was customized
- the WriteRole link always went through that rebuild path, so it was affected immediately

That frontend bug was fixed in the repo, validated locally, and redeployed live to Cloudflare as version `1babbd85-ef34-413a-bea0-bc3b5e0427ed`.

Fresh live browser evidence after deploy is stored in:

- [issue2-ui-summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260319T230621Z-issue2-live-rollout-e2e/evidence/ui/issue2-ui-summary.json)
- [issue2-live-account-detail.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260319T230621Z-issue2-live-rollout-e2e/evidence/screenshots/issue2-live-account-detail.png)
- [issue2-live-reconnect-modal.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260319T230621Z-issue2-live-rollout-e2e/evidence/screenshots/issue2-live-reconnect-modal.png)

Confirmed live browser behavior after deploy:

- `https://ocypheris.com/accounts` renders successfully for the authenticated live tenant
- the existing connected account still shows `error`, matching the live API validate result
- the reconnect modal shows `Template version: v1.5.6`
- a custom ReadRole stack name still preserves `param_SaaSExecutionRoleArns`
- a custom WriteRole stack name still preserves `param_SaaSExecutionRoleArns`

## Result

`PARTIAL`

Issue 2 is now live on the SaaS side:

- templates published
- runtime deployed
- STS audit context live
- frontend Launch Stack link preservation bug fixed and deployed

Issue 2 is not yet fully closed for already connected customers because the real customer account in this environment still needs its ReadRole stack updated to the new trust policy before validation returns to `validated`.
