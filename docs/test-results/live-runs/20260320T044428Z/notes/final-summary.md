# Template Rollout Recovery Summary (2026-03-20 UTC)

## Scope

Close the March 20 live template rollout after the intermediate broken deploy:

- publish `read-role/v1.5.9.yaml` and `write-role/v1.4.7.yaml`
- redeploy the live serverless runtime so `/api/auth/me` advertises the new versions
- recover the bad `backend/auth.py` / `cloudformation_templates.py` mismatch that broke the live API
- rerun the live API and browser proof on `https://api.ocypheris.com` and `https://ocypheris.com/accounts`

## What changed

- Published the new customer templates to `security-autopilot-templates`:
  - `cloudformation/read-role/v1.5.9.yaml`
  - `cloudformation/write-role/v1.4.7.yaml`
- Re-uploaded those objects with `ServerSideEncryption=AES256` so the bucket does not depend on a KMS key for template fetches.
- Corrected the repo defaults and publish/upload helpers to point at the new versions.
- Redeployed the live serverless runtime from a clean temporary snapshot after overlaying the matching `backend/services/cloudformation_templates.py` dependency for the newer `backend/auth.py`.
- Ran `alembic upgrade heads` after the repaired deploy.
- Updated the template publish helper so it now reflects the real contract: private S3 bucket + presigned Launch Stack `TemplateURL`, not anonymous public S3 reads.

## Live validation

### API

Recovered retained API evidence:

- [live-template-rollout-recovered-summary-20260320T051409Z.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T044428Z/evidence/api/live-template-rollout-recovered-summary-20260320T051409Z.json)
- [auth-me-recovered-20260320T051409Z.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T044428Z/evidence/api/auth-me-recovered-20260320T051409Z.json)
- [validate-recovered-20260320T051409Z.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T044428Z/evidence/api/validate-recovered-20260320T051409Z.json)
- [accounts-recovered-20260320T051409Z.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T044428Z/evidence/api/accounts-recovered-20260320T051409Z.json)
- [health-recovered-20260320T051409Z.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T044428Z/evidence/api/health-recovered-20260320T051409Z.json)
- [ready-recovered-20260320T051409Z.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T044428Z/evidence/api/ready-recovered-20260320T051409Z.json)

Confirmed live API behavior:

- `GET /api/auth/me` now advertises:
  - `read_role_template_url=https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/read-role/v1.5.9.yaml`
  - `write_role_template_url=https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/write-role/v1.4.7.yaml`
- Both Launch Stack URLs again include `param_SaaSExecutionRoleArns`.
- `POST /api/aws/accounts/696505809372/validate` returned:
  - `status=validated`
  - `permissions_ok=true`
  - `authoritative_mode_allowed=true`
- `GET /api/aws/accounts` shows account `696505809372` as `validated`.
- `GET /health` returned `{"status":"ok","app":"AWS Security Autopilot"}`.
- `GET /ready` returned `ready=true`.

### Browser

Recovered retained browser evidence:

- [live-template-rollout-ui-summary-20260320T051409Z.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T044428Z/evidence/ui/live-template-rollout-ui-summary-20260320T051409Z.json)
- [live-template-rollout-accounts-validated.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T044428Z/evidence/screenshots/live-template-rollout-accounts-validated.png)
- [live-template-rollout-connect-modal-v1.5.9.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T044428Z/evidence/screenshots/live-template-rollout-connect-modal-v1.5.9.png)
- [live-template-rollout-account-detail-v1.4.7.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T044428Z/evidence/screenshots/live-template-rollout-account-detail-v1.4.7.png)

Confirmed live browser behavior:

- `https://ocypheris.com/accounts` renders for the authenticated tenant.
- The Accounts page shows:
  - `Total accounts = 1`
  - `Healthy = 1`
  - connected account `696505809372`
  - `validated` + `Healthy`
- The shared `Connect AWS account` modal shows `Template version: v1.5.9`.
- The modal ReadRole Launch Stack link preserves `param_SaaSExecutionRoleArns`.
- The account detail modal shows the validated account state, current ReadRole ARN, no connected WriteRole, and a WriteRole Launch Stack link that also preserves `param_SaaSExecutionRoleArns`.

## Operational note

- Anonymous raw S3 fetches for the template bucket can still return `403` because account-level public-access blocks remain enabled. That is now treated as the expected security posture, not a publish failure.
- The current Launch Stack path works through presigned S3 `TemplateURL` values generated by the SaaS runtime.

## Residual notes

- CloudWatch logs show no further `ImportModuleError` after the repaired deploy.
- The first post-deploy cold-start burst logged several `INIT_REPORT ... Status: timeout` lines before the API settled; subsequent requests succeeded.
- `/ready` still embeds non-fatal `cloudwatch:GetMetricStatistics` access-denied warnings when queue lag metadata is populated. Readiness remains `true`.
- The live frontend still logs one minified React `#418` error on the Accounts page, but the page rendered and the required live flows completed successfully.

## Result

`PASS`

This run supersedes the broken intermediate state captured earlier in the same folder and closes the live rollout for template versions `v1.5.9` / `v1.4.7`.
