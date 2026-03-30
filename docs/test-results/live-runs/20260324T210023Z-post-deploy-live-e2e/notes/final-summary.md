# Post-Deploy Live E2E Summary

## Result

- Status: `PARTIAL CHECKPOINT`
- Current stop phase: `fresh GuardDuty grouped run created; callback-driven state convergence proven; matrix not fully closed`
- Primary product findings:
  - `frontend/browser create path regression` fixed and redeployed
  - `callback/reporting convergence` proven on a fresh review-required grouped run
  - `duplicate no-change protection` proven on already-generated grouped families

## What Was Proven

- `GET /health` returned `HTTP/2 200`.
- `GET /ready` returned `HTTP/2 200`.
- The March 24 fallback-runtime tenant/operator context was repaired enough to re-enter the real findings/actions UI and execute live grouped-family flows in Playwright.
- A frontend fix was required for grouped bundle generation from `/actions/group`:
  - the page now resolves remediation options before create
  - sends `strategy_id` / `strategy_inputs`
  - blocks on review-required dependency warnings until `risk_acknowledged=true`
  - deployed frontend version: `e1934b17-7b3c-43f8-b0f8-e8c6a14b4ac7`
- `S3.1` (`s3_block_public_access`, `eu-north-1`) now proves the deployed end-to-end path truthfully:
  - browser create path reached the new duplicate-protection response instead of failing on missing `strategy_id`
  - deployed API returned exact duplicate guard `409 grouped_bundle_already_created_no_changes`
  - existing live run `9722f1a7-c1d6-427b-be43-b4d328168761` downloaded successfully
  - bundle was valid (`bundle_manifest.json`, `decision_log.md`, `run_all.sh`, `replay_group_run_reports.sh`)
  - local bundle apply succeeded against account `696505809372` with `AWS_PROFILE=test28-root`
  - callback replay landed on deployed `POST /api/internal/group-runs/report`
  - deployed refresh path completed: ingest `completed`, reconciliation run `798c5854-3155-4f8f-b8b7-45839bef9eab` `succeeded`
  - final group truth converged to `run_successful_confirmed`, `action_status=resolved`, `last_confirmation_source=control_plane_reconcile`
- `EC2.182` (`ebs_snapshot_block_public_access`, `eu-north-1`) now proves the fixed browser create path and risk-ack gate, then returns the same truthful exact duplicate guard for an unchanged already-generated group.
- `Config.1` (`aws_config_enabled`, `us-east-1`) now proves the fixed browser create path and risk-ack gate, then returns the same truthful exact duplicate guard for an unchanged already-generated group.
- `GuardDuty.1` (`enable_guardduty`, `us-east-1`) now proves the fresh grouped create and callback-driven convergence path:
  - Playwright triggered a real grouped bundle create
  - deployed API returned `201` on `POST /api/action-groups/049d8f9e-ab73-411a-8dd2-1494efc60ada/bundle-run`
  - new group run `91c8dea4-8f28-41d9-b13c-a9ae9b77fd0b` / remediation run `c44e376f-c4ec-459c-bfda-ba646f1e986e` were created
  - remediation run completed `success` and produced a truthful review-required bundle (`review_required_bundle`, zero executable actions)
  - before bundle execution, grouped projection was stale: group run stayed `started` and group detail still showed `not_run_yet`
  - executing the downloaded review-required bundle `run_all.sh` emitted the embedded callback to the deployed API
  - after callback delivery, the same group run converged to `finished` with `reporting_source=bundle_callback`
  - final grouped truth switched from `not_run_yet` to `run_finished_metadata_only`

## Current Remaining Gaps

1. The focused matrix is not yet fully closed in this run directory.
   - `S3.1` is proven end to end from an already-existing successful run plus duplicate guard.
   - `EC2.182` and `Config.1` prove the fixed create UI contract, but both hit exact duplicate/no-change guards instead of producing fresh new runs.
   - `GuardDuty.1` produced the fresh new run and proved callback-driven convergence, but no deployed refresh cycle was needed because the family is review-required metadata-only.
2. The group-page UX still surfaces duplicate/no-change `409` responses as an error banner instead of a clearer “existing bundle already available” handoff.
3. The fresh GuardDuty run showed a temporary projection gap:
   - remediation run status was already `success`
   - grouped run stayed `started` until the downloaded bundle executed and posted its callback
   - this is truthful behavior for the current grouped callback contract, but it remains an operator gotcha for review-required bundles

## Evidence

- Health/runtime:
  - [health headers](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/health.txt)
  - [ready headers](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/ready.txt)
  - [runtime tenant context](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/runtime-tenant-context.json)
- `S3.1` end-to-end proof:
  - [duplicate create response](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/s3-1-eu-north-1-create-duplicate.json)
  - [bundle ZIP headers](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/s3-1-eu-north-1-pr-bundle.headers)
  - [bundle manifest](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/bundles/pr-bundle-9722f1a7-c1d6-427b-be43-b4d328168761/bundle_manifest.json)
  - [bundle apply transcript](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/bundles/pr-bundle-9722f1a7-c1d6-427b-be43-b4d328168761-apply.log)
  - [callback replay accepted: started](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/started-1774390235.replay.body)
  - [callback replay accepted: finished](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/finished-1774390257.replay.body)
  - [post-apply group detail](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/s3-1-eu-north-1-group-detail-post-refresh.json)
- `GuardDuty.1` fresh create and callback convergence:
  - [group runs while stale (`started`)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/guardduty-us-east-1-group-runs-latest.json)
  - [remediation run success](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/guardduty-us-east-1-remediation-run.json)
  - [downloaded review-required bundle ZIP headers](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/guardduty-us-east-1-pr-bundle.headers)
  - [bundle runner transcript](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/bundles/pr-bundle-c44e376f-c4ec-459c-bfda-ba646f1e986e-run.log)
  - [group runs after callback convergence](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/guardduty-us-east-1-group-runs-post-callback.json)
  - [group detail after callback convergence](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/guardduty-us-east-1-group-detail-post-callback.json)

## Conclusion

This resumed March 24 post-deploy live E2E no longer fails at the browser-entry/deploy-config gate. The live grouped create path from the real UI is now fixed and deployed, exact duplicate/no-change behavior is truthful for already-generated families, `S3.1` proves deployed bundle download/apply/refresh/reconcile on production data, and `GuardDuty.1` proves fresh grouped create plus callback-driven state convergence for a review-required bundle. The remaining work is matrix completion and any UX polish around duplicate/no-change responses, not re-discovering the root production failures.
