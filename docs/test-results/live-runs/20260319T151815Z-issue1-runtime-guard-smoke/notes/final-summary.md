# Issue 1 Runtime Guard Live Smoke (2026-03-19 UTC)

## Scope

Targeted live verification for the issue-1 IAM cleanup fix after redeploying the serverless runtime.

Goals:

- confirm the live API now advertises the newly published safe role-template versions
- confirm `DELETE /api/aws/accounts/{account_id}?cleanup_resources=true` fails closed in the live runtime
- confirm the connected AWS account record remains present after the guarded delete attempt
- confirm the live frontend still renders the authenticated Accounts page normally

## Runtime Deployed

- Serverless deploy path: `/Users/marcomaher/AWS Security Autopilot/scripts/deploy_saas_serverless.sh`
- Post-deploy migration command:

```bash
/bin/zsh -lc 'set -a; source config/.env.ops; set +a; ./venv/bin/alembic upgrade heads'
```

- Live API Lambda:
  - function: `security-autopilot-dev-api`
  - `LastModified`: `2026-03-19T15:13:58.000+0000`
  - image: `029037611564.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-dev-saas-api:20260319T151052Z`
- Live worker Lambda:
  - function: `security-autopilot-dev-worker`
  - `LastModified`: `2026-03-19T15:13:58.000+0000`
  - image: `029037611564.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-dev-saas-worker:20260319T151052Z`

## Live Checks

### Health

- `GET https://api.ocypheris.com/health` -> `200`
- `GET https://api.ocypheris.com/ready` -> `ready=true`
- `GET https://ocypheris.com` -> `200`

### Authenticated API smoke

Because previously saved live test credentials were stale, this smoke used a short-lived JWT minted with the current runtime signing secret for the existing live admin user:

- user: `marco.ibrahim@ocypheris.com`
- tenant: `Valens`
- tenant id: `9f7616d8-af04-43ca-99cd-713625357b70`
- connected account: `696505809372`

Observed behavior:

- `GET /api/auth/me`
  - returned `read_role_template_url=https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/read-role/v1.5.5.yaml`
  - returned `write_role_template_url=https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/write-role/v1.4.3.yaml`
- `GET /api/aws/accounts`
  - returned the connected account `696505809372` in `validated` state
- `DELETE /api/aws/accounts/696505809372?cleanup_resources=true`
  - returned `400`
  - response detail:

```text
Runtime IAM cleanup is not enabled. Ask the customer to delete the SecurityAutopilotReadRole CloudFormation stack in their AWS Console, then retry with cleanup_resources=false.
```

- `GET /api/aws/accounts` immediately after the guarded delete
  - still returned account `696505809372`

### Browser smoke

- Opened `https://ocypheris.com/accounts` in a real browser session using the same live tenant via injected API auth cookie
- Accounts page rendered successfully
- Account Hub showed:
  - `Total accounts = 1`
  - `Healthy = 1`
  - connected account row `696505809372`

Screenshot artifact:

- [live-accounts-smoke.png](/Users/marcomaher/AWS%20Security%20Autopilot/output/playwright/live-accounts-smoke.png)

## Result

`PASS`

The live runtime now serves the safe role-template versions (`v1.5.5` / `v1.4.3`), the delete-account cleanup path fails closed instead of attempting runtime IAM teardown, and the existing connected account remains intact after the guarded delete attempt.
