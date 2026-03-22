# Attack Path Account-Scope Live E2E Summary

- Run ID: `20260321T184710Z-attack-path-account-scope-live-e2e`
- Date (UTC): `2026-03-21T18:47:10Z`
- Frontend: `https://ocypheris.com`
- Backend: `https://api.ocypheris.com`
- Result: `FAIL`

## Scope

Validate the live behavior for the three account-scoped controls that were expected to stop showing the fail-closed attack-path message:

- `SSM.7`
- `IAM.4`
- `Config.1`

Target account: `696505809372`

## Live API result

Using a short-lived same-operator bearer for tenant `9f7616d8-af04-43ca-99cd-713625357b70`, the live action-detail API still returned the fail-closed attack-path state for representative account-scoped actions:

- `SSM.7` action `e8be6f05-0e5e-4bdc-818e-f551cd62ccb5`
  - `graph_context.status="available"`
  - `attack_path_view.status="context_incomplete"`
  - `score_components.relationship_context=null`
  - `score_components.toxic_combinations.context_incomplete=true`
- `IAM.4` action `84a23bb8-d6f7-4c1b-87ff-87f9cc7c469c`
  - `graph_context.status="available"`
  - `attack_path_view.status="context_incomplete"`
  - `score_components.relationship_context=null`
  - `score_components.toxic_combinations.context_incomplete=true`
- `Config.1` action `7d51a23a-9af2-4a82-ae75-67561c01cf8e`
  - `graph_context.status="available"`
  - `attack_path_view.status="context_incomplete"`
  - `score_components.relationship_context=null`
  - `score_components.toxic_combinations.context_incomplete=true`

The underlying finding producer path is still present on live for at least one affected finding:

- finding `cc4e2b7a-a2d1-443d-9bd6-5fb0ac2d7e25` (`SSM.7`, `us-east-1`)
  - `raw_json.relationship_context.complete=true`
  - `raw_json.relationship_context.confidence=1.0`
  - `raw_json.relationship_context.scope="account"`

This means the live failure is not simply “the finding never got relationship context.” The current live action-detail payload is still missing the relationship-context value the new attack-path logic expects on the action detail contract.

## Live UI result

An authenticated headed browser session reached the live app and loaded the dedicated action-detail page for `IAM.4` action `84a23bb8-d6f7-4c1b-87ff-87f9cc7c469c`.

The rendered page still showed:

`Relationship context is incomplete, so the attack story stays fail-closed and bounded to directly observed evidence.`

The same live page also rendered:

`Relationship context is incomplete, so this story stays fail-closed and bounded.`

The browser console also recorded one `403` on `POST /api/auth/refresh`. That error is expected in this synthetic session because the browser was authenticated only with an injected access-token cookie and no matching CSRF cookie for refresh; it does not explain the attack-path payload mismatch.

## Evidence

- Browser screenshot: `/Users/marcomaher/AWS Security Autopilot/output/playwright/live-attack-path-e2e/.playwright-cli/page-2026-03-21T18-46-34-075Z.png`
- Browser action-detail snapshot: `/Users/marcomaher/AWS Security Autopilot/output/playwright/live-attack-path-e2e/.playwright-cli/page-2026-03-21T18-46-21-770Z.yml`
- Browser top-risks snapshot: `/Users/marcomaher/AWS Security Autopilot/output/playwright/live-attack-path-e2e/.playwright-cli/page-2026-03-21T18-45-49-588Z.yml`
- Browser console log: `/Users/marcomaher/AWS Security Autopilot/output/playwright/live-attack-path-e2e/.playwright-cli/console-2026-03-21T18-46-20-555Z.log`

## Conclusion

The live E2E check failed. Production still shows the old fail-closed account-scope attack-path behavior.

Most likely remaining live gap:

- the new backend logic is not deployed to the live runtime, or
- the live action rows have not been recomputed onto a contract that includes usable `score_components.relationship_context` for these account-scoped actions.
