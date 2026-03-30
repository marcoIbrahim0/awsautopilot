# Live E2E Run Metadata

> ⚠️ Superseded: this metadata records the initial backup-auth canary before the remaining Phase 5 closure fixes were deployed. Use [20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun/README.md) for the full rerun and [20260326T052354Z-phase5-cloudtrail-postdeploy-recheck](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T052354Z-phase5-cloudtrail-postdeploy-recheck/README.md) for the final CloudTrail bundle proof.

- Run ID: `20260326T031724Z-phase5-support-bucket-cluster-canary-backup-auth`
- Created at (UTC): `2026-03-26T03:17:24Z`
- Frontend URL: `https://ocypheris.com`
- Backend URL: `https://api.ocypheris.com`
- Auth path: isolated authenticated browser/API session using a freshly minted bearer for `maromaher54+backup-local@example.com`
- Live tenant: `Valens Local Backup`
- Live account: `696505809372`
- Live region: `eu-north-1`
- Phase 5 target controls in this run: `Config.1`, `S3.9`, `CloudTrail.1`
- Default Phase 5 canary account from the plan: `029037611564`
- Default Phase 5 canary region from the plan: `eu-north-1`
- Local cluster validation reference: [20260326T025813Z-phase5-support-bucket-cluster-canary-blocked](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T025813Z-phase5-support-bucket-cluster-canary-blocked/README.md)
- Live canary result: `PARTIAL`

## Live Run IDs

- `Config.1`
  - action: `84f874b0-d2fd-405f-87fb-edc3264601a2`
  - run: `f5858299-3f08-4100-8c32-130736e427db`
- `S3.9`
  - action: `0c490240-f3b5-42b2-94ce-010ae67bd79f`
  - run: `cd1b5f43-a971-4c78-ba37-1492804d66e7`
- `CloudTrail.1`
  - action: `9074eb82-d359-4ce2-9155-1b71699fed8f`
  - run: `91176ee9-6db1-42c1-aaa8-036b2f2b0d94`

## Executed Local AWS Validation

- Terraform bundle execution used:
  - `AWS_PROFILE=test28-root`
  - `AWS_REGION=eu-north-1`
- `aws sts get-caller-identity` for `test28-root`:
  - account: `696505809372`
  - arn: `arn:aws:iam::696505809372:root`

## Key Observations

- `Config.1` generated an executable bundle and `terraform apply` completed successfully.
- The post-apply AWS Config recorder still preserves `EXCLUSION_BY_RESOURCE_TYPES` for:
  - `AWS::IAM::Policy`
  - `AWS::IAM::User`
  - `AWS::IAM::Role`
  - `AWS::IAM::Group`
- The live `Config.1` finding therefore remained `NEW` with `CONFIG_RECORDER_MISSING_REQUIRED_RESOURCE_TYPES`.
- `S3.9` and `CloudTrail.1` both accepted fresh live runs but emitted non-executable guidance bundles with `support_tier=review_required_bundle`.

## Primary Remaining Questions

> ❓ Needs verification: should the executable `Config.1` account-local path overwrite an existing selective recorder group when the preserved exclusions still violate `Config.1`, or should that live state downgrade to `review_required_bundle` instead of claiming an executable canary pass?

> ❓ Needs verification: should the final Phase 5 live gate require rerunning on the original `Valens`/`029037611564` target after auth recovery, or can the retained `Valens Local Backup`/`696505809372` canary evidence count as the live family proof for this rollout?
