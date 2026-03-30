# Live E2E Run Metadata

- Run ID: `20260326T052354Z-phase5-cloudtrail-postdeploy-recheck`
- Created at (UTC): `2026-03-26T05:31:19Z`
- Frontend URL: `https://ocypheris.com`
- Backend URL: `https://api.ocypheris.com`
- Live tenant: `Valens Local Backup`
- Live account: `696505809372`
- Live region: `eu-north-1`
- Runtime deploy tag: `20260326T052354Z`
- API Lambda image after deploy: `029037611564.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-dev-saas-api:20260326T052354Z`
- Worker Lambda image after deploy: `029037611564.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-dev-saas-worker:20260326T052354Z`
- Rechecked control family: `CloudTrail.1`
- Live rerun result: `PASS`

## Live Run IDs

- `CloudTrail.1`
  - action: `9074eb82-d359-4ce2-9155-1b71699fed8f`
  - run: `0f0a0212-ba3c-40e8-a8b9-9730cc496264`

## Verification Markers

- Present in retained live bundle:
  - `resource "aws_s3_bucket" "cloudtrail_logs"`
  - `resource "aws_s3_bucket_policy" "cloudtrail_logs"`
  - `kms_master_key_id = "alias/aws/s3"`
  - `DenyInsecureTransport`
- Absent from retained live bundle:
  - `resource "aws_s3_bucket_policy" "cloudtrail_managed"`
  - `sse_algorithm = "AES256"`

## Related Phase 5 Evidence

- Full backup-tenant rerun:
  - [20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun/README.md)
- Superseded initial backup-auth canary:
  - [20260326T031724Z-phase5-support-bucket-cluster-canary-backup-auth](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T031724Z-phase5-support-bucket-cluster-canary-backup-auth/README.md)
