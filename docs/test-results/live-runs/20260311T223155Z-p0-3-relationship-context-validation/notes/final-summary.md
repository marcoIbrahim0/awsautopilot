## Final Summary

1. Was the new producer path validated on live: `NO`

2. Whether prod deploy was already present
- `NO`
- Live Lambda runtime evidence shows both functions still on image tag `20260311T181012Z`, last modified `2026-03-11T18:12:59.000+0000`, which predates the March 12 producer-path implementation.

3. Whether backfill/recompute was executed
- Dry-run only: `YES`
- Live write path with `--recompute-actions`: `NO`

4. Exact findings inspected
- No live finding detail payloads were inspected because the run stopped at the deployment blocker.
- Non-mutating scope proof only: the dry-run scanned `26` Security Hub findings for tenant `9f7616d8-af04-43ca-99cd-713625357b70`, account `696505809372`, region `us-east-1`.
- Intended live validation pair after deploy remains:
  - anchor finding/control: `EC2.182`
  - support finding/control: `SSM.7`

5. Exact action inspected
- No live action detail payload was inspected because the run stopped at the deployment blocker.
- Intended anchor action after deploy remains `ebs_snapshot_block_public_access`.

6. Exact PASS / FAIL result for P0.3
- `BLOCKED`

7. Exact blocker if not passing
- Production backend and worker are not deployed with the March 12 relationship-context producer-path fix, so a scoped prod backfill would not prove the new live ingest path works.
- The normal operator login attempt also still fails with `401 Invalid email or password`, but deployment is the primary blocker for this run.

8. Whether another AWS-side scenario is still required
- `NO` before redeploy.
- Deploy the March 12 runtime first, then rerun this same tenant/account/region slice and validate the intended `EC2.182` + `SSM.7` pair before introducing any new AWS-side scenario.

Evidence:
- [deployment-check.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260311T223155Z-p0-3-relationship-context-validation/evidence/api/deployment-check.txt)
- [backfill-dry-run.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260311T223155Z-p0-3-relationship-context-validation/evidence/api/backfill-dry-run.txt)
- [login-attempt.headers.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260311T223155Z-p0-3-relationship-context-validation/evidence/api/login-attempt.headers.txt)
- [login-attempt.body.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260311T223155Z-p0-3-relationship-context-validation/evidence/api/login-attempt.body.json)
