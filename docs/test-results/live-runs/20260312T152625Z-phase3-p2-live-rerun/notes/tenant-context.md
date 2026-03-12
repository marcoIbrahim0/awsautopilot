# Tenant Context

- Run ID: `20260312T152625Z-phase3-p2-live-rerun`
- Date tested (UTC): `2026-03-12`
- Frontend: `https://ocypheris.com`
- API: `https://api.ocypheris.com`
- Operator email: `marco.ibrahim@ocypheris.com`
- User ID: `7c43e0b3-6e98-43af-826f-f4eeaa5af674`
- Tenant: `Valens` (`9f7616d8-af04-43ca-99cd-713625357b70`)
- Account: `696505809372`
- Region: `us-east-1`
- Validated Security Hub import role:
  - role ARN: `arn:aws:iam::696505809372:role/CodexP2SecurityHubImportRole`
  - external ID: `ocypheris-p2-e2e-20260312`

## Live Runtime State Used

- The rerun started from the already-deployed March 12 runtime:
  - API Lambda `security-autopilot-dev-api`
  - Worker Lambda `security-autopilot-dev-worker`
  - `ACTIONS_THREAT_INTELLIGENCE_HALF_LIFE_HOURS=72`
- Synthetic Security Hub findings were already imported and ingested before this validation pass.
- Standard scoped recompute was already known to fail in production on the security graph path.

## Observed Production Defects Still Active

- Standard scoped recompute still fails on live production with:
  - `ValueError: security graph node missing for key=action:0ca64b94-9dcb-4a97-91b0-27b0341865bc`
- The graph-bypass recompute workaround is still required for this tenant/account scope.
- The trusted-config action detail payload contains a human-readable explanation string that overstates heuristic exploit points even though the numeric threat-intel fields are correct.

## Primary Artifacts

- Auth proof: [01-auth-me.body.json](../evidence/api/01-auth-me.body.json)
- Initial synthetic import request: [02-securityhub-batch-import-open.request.json](../evidence/api/02-securityhub-batch-import-open.request.json)
- Initial graph-bypass recompute result: [06c-recompute-actions-graph-bypassed.json](../evidence/api/06c-recompute-actions-graph-bypassed.json)
- Live action list used for candidate discovery: [07-actions-list.body.json](../evidence/api/07-actions-list.body.json)
- Assumed-role proof for cleanup: [09b-assumed-role-caller-identity.json](../evidence/api/09b-assumed-role-caller-identity.json)
- Post-cleanup Security Hub state: [12-securityhub-synthetic-findings-after-cleanup.json](../evidence/api/12-securityhub-synthetic-findings-after-cleanup.json)
