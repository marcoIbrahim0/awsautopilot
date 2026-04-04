# Grouped Support-Bucket Helper Rerun

- Run ID: `20260402T034144Z-grouped-support-bucket-helper-rerun`
- Date: `2026-04-02` UTC
- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- Account: `696505809372`
- Region: `eu-north-1`
- Mutation profile: `test28-root`
- Final deployed runtime tag: `20260402T033620Z`
- Final result: `PASS`

Primary retained summary:

- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/notes/final-summary.md)

Key evidence folders:

- [api](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/api)
- [bundle](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/bundle)
- [runtime](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T034144Z-grouped-support-bucket-helper-rerun/runtime)

High-level outcome:

- Deployed a narrow runtime fix for the Config helper-bucket baseline plus the S3 inventory shadow-state collision that had blocked truthful helper-bucket refresh.
- Recomputed the target scope, generated a fresh live grouped `Config.1` bundle, downloaded it, verified the shipped helper-bucket inventory and hardening calls, and executed the customer-run bundle successfully on the real target account.
- The grouped callback terminalized truthfully as `finished` with `reporting_source = bundle_callback`.
- The resulting helper bucket `security-autopilot-config-696505809372-eu-north-1` is now clean on raw AWS evidence:
  - versioning enabled
  - EventBridge notifications configured
  - object lock enabled
  - expected support-bucket tags present
  - zero active Security Hub findings for the helper bucket
- Post-apply product refresh is also clean:
  - scoped S3 reconciliation run `d3b11ae4-0493-428b-8f35-c0b034660340` succeeded on the same account/region
  - helper-bucket `S3.5` and `S3.9` findings are `RESOLVED`
  - helper-bucket `S3.11` and `S3.15` findings are absent

Acceptance note:

- This rerun preserves the already-proven canonical grouped runner deployment behavior from April 1 and closes the helper-bucket blocker that remained from `20260401T213210Z-grouped-runner-support-bucket-live-validation`.
