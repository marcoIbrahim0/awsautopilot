# Post-Deploy Live E2E

- Run ID: `20260324T210023Z-post-deploy-live-e2e`
- Date (UTC): `2026-03-24`
- Frontend: `https://ocypheris.com`
- API: `https://api.ocypheris.com`
- Target account: `696505809372`
- Outcome: `BLOCKED`
- Failure bucket: `deploy/config regression`

## Summary

This run attempted the Playwright-led post-deploy live E2E matrix against the deployed runtime after the March 24 fallback-DB recovery. The run stopped before any grouped PR-bundle create because the deployed runtime now serves a different live tenant/admin context than the expected production operator path.

The authenticated fallback-runtime admin resolved as tenant `Valens Local Backup` (`c3351a02-0bc2-4449-beed-d59d7ac937d0`) and the live frontend redirected that tenant to `/onboarding` instead of exposing `/findings` or `/actions`. The core matrix was also incomplete on the deployed API: `s3_block_public_access eu-north-1` and `ebs_snapshot_block_public_access eu-north-1` returned `0` open actions, while `aws_config_enabled us-east-1` and `enable_guardduty us-east-1` returned `1` each.

## Key Artifacts

- [Run metadata](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/00-run-metadata.md)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/notes/final-summary.md)
- [Authenticated onboarding redirect screenshot](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/screenshots/authenticated-onboarding-redirect.png)
- [Authenticated browser network log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/ui/playwright/authenticated-onboarding-network.log)
- [Current runtime auth context](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/auth-me-current-bearer.json)
- [Core matrix counts](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260324T210023Z-post-deploy-live-e2e/evidence/api/matrix-counts.json)
