# Live E2E Run Metadata

- Run ID: `20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun`
- Created at (UTC): `2026-03-26T05:06:14Z`
- Frontend URL: `https://ocypheris.com`
- Backend URL: `https://api.ocypheris.com`
- Auth path: isolated authenticated browser/API session using a freshly minted bearer for `maromaher54+backup-local@example.com`
- Live tenant: `Valens Local Backup`
- Live account: `696505809372`
- Live region: `eu-north-1`
- Phase 5 target controls in this run: `Config.1`, `S3.9`, `CloudTrail.1`
- Runtime state for this rerun: serverless runtime restored to fallback DB connectivity before run start; initial rerun images were later superseded by the focused clean-snapshot deploy tag `20260326T052354Z`
- Live canary result: `PARTIAL`

## Live Run IDs

- `Config.1`
  - action: `84f874b0-d2fd-405f-87fb-edc3264601a2`
  - run: `63fd9b08-8d5c-41ea-9ca8-7905a61f94dd`
- `S3.9`
  - action: `5f5d8617-4da8-4830-a1dc-6b4e98f6b0b0`
  - run: `7fe2766d-7c8e-41de-b0ab-bc616b53978a`
- `CloudTrail.1`
  - action: `9074eb82-d359-4ce2-9155-1b71699fed8f`
  - run: `adb3a9c6-5a17-4a9a-bc7b-05830bc46953`

## Executed Local AWS Validation

- Terraform bundle execution used:
  - `AWS_PROFILE=test28-root`
  - `AWS_REGION=eu-north-1`
- `aws sts get-caller-identity` for `test28-root`:
  - account: `696505809372`
  - arn: `arn:aws:iam::696505809372:root`

## Current Follow-On References

- Focused CloudTrail postdeploy recheck:
  - [20260326T052354Z-phase5-cloudtrail-postdeploy-recheck](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T052354Z-phase5-cloudtrail-postdeploy-recheck/README.md)
  - remediation run: `0f0a0212-ba3c-40e8-a8b9-9730cc496264`
- Superseded initial backup-auth canary:
  - [20260326T031724Z-phase5-support-bucket-cluster-canary-backup-auth](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T031724Z-phase5-support-bucket-cluster-canary-backup-auth/README.md)

## Key Observations

- `Config.1` now uses the explicit full-scope branch and fixes the AWS recorder state in the target account.
- `S3.9` now keeps the planned create-destination path executable and emits the shared support-bucket baseline in the live bundle.
- `CloudTrail.1` now keeps the managed create path executable, but the initial rerun bundle content still reflected the old family-local bucket fragment until the focused postdeploy recheck.
- The remaining live rollout blocker is source-of-truth reevaluation of `Config.1`, not a known remaining runtime or bundle-generation contract defect.
