# Final Summary

1. Deployment succeeded. The standard serverless runtime deploy completed cleanly via `./scripts/deploy_saas_serverless.sh --region eu-north-1`, and the post-deploy normalization kept the worker enabled at reserved concurrency `10`.
2. Exact live image tag before and after:
   - before: API `029037611564.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-dev-saas-api:20260311T181012Z`; worker `029037611564.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-dev-saas-worker:20260311T181012Z`
   - after: API `029037611564.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-dev-saas-api:20260311T224136Z`; worker `029037611564.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-dev-saas-worker:20260311T224136Z`
   - before `LastModified`: `2026-03-11T18:12:59.000+0000`
   - after `LastModified`: `2026-03-11T22:44:07.000+0000`
3. Scoped backfill and recompute both ran:
   - dry-run: `scanned=26`, `updated=26`, `complete=26`, `recomputed_actions=false`
   - live run: `scanned=26`, `updated=26`, `complete=26`, `recomputed_actions=true`
4. Exact findings inspected:
   - `EC2.182` finding `720d2ebe-07d3-4564-834b-b27736727a90`
   - `SSM.7` finding `cc4e2b7a-a2d1-443d-9bd6-5fb0ac2d7e25`
5. Exact action inspected:
   - anchor action `442e46ac-f31c-4242-82ca-9e47081a3adb` (`ebs_snapshot_block_public_access`)
6. Final P0.3 result: `PASS`
7. Exact blocker if not passing: none. Validation used the same-operator bearer fallback path recorded in `../evidence/api/auth-me-fallback.body.json`; no additional blocker remained once the runtime tag moved and the scoped backfill/recompute completed.
8. AWS-side scenario still required after deploy: none for this scoped P0.3 validation. A fresh Security Hub re-ingest would be an optional extra proof point for the worker ingest path, but it is not required for this post-deploy PASS result because live findings now expose complete relationship context and the anchor action shows the expected toxic-combination promotion/explainability.
