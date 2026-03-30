# Final Summary

## Scope

- Date: March 25-26, 2026 UTC
- Account: `696505809372`
- Deployed backend image: `20260325T234858Z`
- Deployed frontend version: `29856335-2b51-42c5-b640-46be9fc37bbb`
- Frontend/API: `https://ocypheris.com` / `https://api.ocypheris.com`
- Focus: deploy the findings remediation-visibility changes and verify the live findings UI after rollout

## Result

- Deployment: PASS.
  - `./scripts/deploy_saas_serverless.sh` completed successfully and updated the live runtime stack.
  - `cd frontend && npm run deploy` completed successfully and published the current frontend bundle.
  - Post-deploy `GET /health` and `GET /ready` both returned healthy live responses.

- Live findings UI verification: PASS.
  - The deployed findings list now opens with the `Open` status filter active by default, and the live page visibly renders `Status: Open`.
  - A live resolved finding detail page for finding `20e1eb80-f39c-49cd-8be1-c42e46aa5ac9` now shows the new resolved-history explanation: `This finding is already resolved, so there is no current remediation action to generate.`
  - A live sibling-scope detail page for finding `451488ac-8ce5-45d3-8831-162228242381` now shows the new account-scope explanation: `This finding family is remediated at account scope. Open the account-level row for the runnable fix.`
  - A live sibling-scope detail page for finding `d903df85-8486-4e6c-a6fe-83dc82199a34` now shows the new resource-scope explanation: `This finding family is remediated on affected resource rows. Open the resource-level row for the runnable fix.`

- Live API verification: PASS.
  - Authenticated browser-backed requests to `https://api.ocypheris.com/api/findings` and `https://api.ocypheris.com/api/findings/grouped` returned the new remediation-visibility metadata on the live deployed backend.
  - The live evidence confirms the deployed API now distinguishes `historical_resolved`, `managed_on_account_scope`, and `managed_on_resource_scope` instead of collapsing everything to the old generic fallback.

## Important Interpretation

- The detailed explanation copy is live and correct on production.
- The short state labels on the detail page currently render as uppercase badge text (`RESOLVED HISTORY`, `MANAGED AT ACCOUNT SCOPE`, `MANAGED ON RESOURCE ROWS`) rather than title-case prose. That is cosmetic, not a blocker for this rollout.
- Browser-authenticated API checks for the deployed findings flows must hit `https://api.ocypheris.com` directly. `https://ocypheris.com/api/*` is not a proxy for these backend routes and returns frontend `404` responses.

## Evidence References

- [health.json](../evidence/api/health.json)
- [ready.json](../evidence/api/ready.json)
- [groupedS39.json](../evidence/api/groupedS39.json)
- [groupedS313.json](../evidence/api/groupedS313.json)
- [flatResolvedS32.json](../evidence/api/flatResolvedS32.json)
- [flatResolvedCloudTrail.json](../evidence/api/flatResolvedCloudTrail.json)
- [deploy-findings-session-check.json](../evidence/ui/deploy-findings-session-check.json)
- [findings-default-open.json](../evidence/ui/findings-default-open.json)
- [finding-historical-resolved.json](../evidence/ui/finding-historical-resolved.json)
- [finding-managed-account-scope.json](../evidence/ui/finding-managed-account-scope.json)
- [finding-managed-resource-scope.json](../evidence/ui/finding-managed-resource-scope.json)
- [deploy-postcheck-summary.json](../evidence/ui/deploy-postcheck-summary.json)
