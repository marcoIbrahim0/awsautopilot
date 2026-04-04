# Grouped Runner / Support-Bucket Live Validation

- Run ID: `20260401T213210Z-grouped-runner-support-bucket-live-validation`
- Date: `2026-04-01` UTC
- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- Account: `696505809372`
- Region: `eu-north-1`
- Mutation profile: `test28-root`
- Final deployed runtime tag: `20260401T215310Z`
- Final result: `FAIL`

Primary retained summary:

- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/notes/final-summary.md)
- [Next-agent handoff](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/notes/next-agent-handoff.md)

Key evidence folders:

- [predeploy](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/predeploy)
- [postdeploy](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy)
- [postdeploy-final-s39](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/postdeploy-final-s39)
- [config-live](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T213210Z-grouped-runner-support-bucket-live-validation/config-live)

High-level outcome:

- Live production redeploy was required because the first April 1 production bundle still shipped `embedded_mixed_tier`.
- The operator deploy path itself was missing `infrastructure/templates/run_all.sh`; this run fixed the packaging path in the repo and redeployed live.
- Fresh postdeploy `S3.9` grouped bundles now prove `runner_template_source=repo:infrastructure/templates/run_all.sh` on the deployed runtime.
- Fresh grouped `Config.1` bundle generation and customer-run apply succeeded on live, including helper-bucket tags and callback completion.
- Acceptance still failed because the helper-bucket outcome did not stay clean:
  - raw Security Hub shows failed `S3.11` and `S3.15` on the helper bucket
  - product findings remained stale/open for `S3.5` and `S3.9` after refresh

Trust-drift note:

- This run did not perform a bounded stale-trust repro. The earlier trust-repair history remains referenced from the live E2E docs, and the current account was healthy enough to complete this validation without another trust break.
