# Issue 2 Live Closure Rerun Summary (2026-03-20 UTC)

## Scope

Authoritative live closure rerun for Issue 2:

- update the connected customer account `696505809372` to the current ReadRole trust contract
- rerun the live API validation gates until the account returned to `validated`
- rerun the live browser checks on `https://ocypheris.com/accounts`
- retain the final passing evidence package under this March 20 rerun folder

## What changed during the closure rerun

- Updated the customer account `696505809372` stack `SecurityAutopilotReadRole` in `eu-north-1` to the current published template line, ending on `read-role/v1.5.8.yaml`.
- Re-published the customer templates as:
  - `read-role/v1.5.8.yaml`
  - `write-role/v1.4.6.yaml`
- Added a `TemplateVersion` custom-resource property so the live ReadRole helper re-applies trust-policy changes when the template version changes.
- After the customer-side trust update, the live runtime no longer failed at the old trust-boundary step, but Lambda-originated STS `SourceIdentity` and `TagSession` calls still hit AWS authorization failures.
- Adjusted the live runtime to use a deterministic `RoleSessionName` fallback for SaaS execution-role sessions instead of sending `SourceIdentity` and STS session tags from those Lambda sessions.
- Fixed the next live blocker exposed by the passing STS path: `describe_compliance_by_config_rule` does not accept `Limit`, so the AWS Config validation probe now omits that unsupported argument.
- Redeployed the live serverless runtime after each runtime fix and ran `alembic upgrade heads` against the live database after each deploy.

## Live validation

### API

Passing retained API evidence:

- [issue2-closure-api-summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T003851Z-issue2-live-closure-rerun/evidence/api/issue2-closure-api-summary.json)
- [auth-me-post-config-probe-fix-20260320T015139Z.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T003851Z-issue2-live-closure-rerun/evidence/api/auth-me-post-config-probe-fix-20260320T015139Z.json)
- [validate-post-config-probe-fix-20260320T015139Z.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T003851Z-issue2-live-closure-rerun/evidence/api/validate-post-config-probe-fix-20260320T015139Z.json)
- [accounts-after-validated-20260320T015247Z.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T003851Z-issue2-live-closure-rerun/evidence/api/accounts-after-validated-20260320T015247Z.json)

Confirmed live API behavior:

- `GET /api/auth/me` advertises:
  - `read_role_template_url=https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/read-role/v1.5.8.yaml`
  - `write_role_template_url=https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/write-role/v1.4.6.yaml`
- `POST /api/aws/accounts/696505809372/validate` returned:
  - `status=validated`
  - `permissions_ok=true`
  - `authoritative_mode_allowed=true`
  - `authoritative_mode_block_reasons=[]`
- `GET /api/aws/accounts` now shows account `696505809372` as `validated`

### Browser

Passing retained browser evidence:

- [issue2-closure-ui-summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T003851Z-issue2-live-closure-rerun/evidence/ui/issue2-closure-ui-summary.json)
- [issue2-live-accounts-validated.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T003851Z-issue2-live-closure-rerun/evidence/screenshots/issue2-live-accounts-validated.png)
- [issue2-live-account-detail-validated.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T003851Z-issue2-live-closure-rerun/evidence/screenshots/issue2-live-account-detail-validated.png)
- [issue2-live-connect-modal-custom-stack-links.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T003851Z-issue2-live-closure-rerun/evidence/screenshots/issue2-live-connect-modal-custom-stack-links.png)

Confirmed live browser behavior:

- `https://ocypheris.com/accounts` renders successfully for the authenticated live tenant
- the connected account shows `validated` and `Healthy` in the Accounts table
- the account detail modal shows the validated account state and current ReadRole ARN
- the shared account-connect modal shows `Template version: v1.5.8`
- a custom ReadRole stack name preserves `param_SaaSExecutionRoleArns`
- a custom WriteRole stack name preserves `param_SaaSExecutionRoleArns`

Current UI note:

- the healthy-state Accounts surface does not expose a separate reconnect button today
- the same launch-link builder was re-validated through the shared `Connect AWS account` modal plus the validated account detail workflow

## Result

`PASS`

This March 20 rerun is the authoritative passing proof for Issue 2.

The earlier March 19/20 package under `20260319T230621Z-issue2-live-rollout-e2e` remains a truthful partial pre-closure attempt. This March 20 package supersedes it as the final closure evidence because it includes:

- the customer-side ReadRole trust update
- the live runtime fallback that avoids Lambda-originated STS audit-field failures
- the AWS Config validation probe fix
- the final `validated` API and UI proof for account `696505809372`
