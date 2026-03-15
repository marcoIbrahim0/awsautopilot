# Remediation-profile Wave 6 environment-readiness summary

- Wave: `Wave 6 environment readiness for the next live AWS validation`
- Date (UTC): `2026-03-15T20:18:21Z`
- Environment used: `local master against isolated runtime`
- Branch tested: `master`
- Exact HEAD tested: `b6952f2ab9c7a3ae2aa7a17faa7104312f6402e5`
- AWS accounts and regions:
  - SaaS queue/runtime account `029037611564` in `eu-north-1`
  - Isolated AWS test account `696505809372` in `eu-north-1` and `us-east-1`
- Fresh/live data note: `Fresh ingest was used for this readiness run. No live records were restored.`
- Supported execution model exercised: `customer-run PR bundles only; archived public SaaS-managed plan/apply remained archived`
- Wave 6 complete: `no`
- Final Wave 6 E2E gate executed: `no`

Related notes:

- [Family readiness matrix](./family-readiness-matrix.md)
- [AWS cleanup summary](./aws-cleanup-summary.md)

## Readiness outcome

- Families now ready for executable proof in the next live run:
  - `EC2.53`
  - `S3.9`
  - `CloudTrail.1`
  - `Config.1`
- Families now ready for downgrade/manual proof in the next live run:
  - `IAM.4`
  - `EC2.53`
  - `S3.2`
  - `S3.5`
  - `S3.9`
  - `CloudTrail.1`
  - `Config.1`
- IAM.4 runtime authority path: `resolved`
  - Generic remediation-profile surfaces still fail closed with `root_key_execution_authority`
  - `/api/root-key-remediation-runs` returned `201` and created run `a850f4a0-b25d-4fe4-8593-6b50e8bdb94f`
- Customer-run executable credential path for the next live run:
  - Read path remains `arn:aws:iam::696505809372:role/CodexP2SecurityHubImportRole`
  - Apply/rollback path is local AWS CLI profile `test28-root`
  - `role_write_arn` remains `null` and was not used
- Next Wave 6 live E2E can now run meaningfully: `yes`
  - The next run can start from concrete family/action/resource IDs instead of exploratory searching

## Highest-signal fresh evidence

| Area | Fresh March 15 evidence | Impact on next live run |
| --- | --- | --- |
| `IAM.4` | Root-key flags were enabled in the isolated runtime only, and the authoritative route created run `a850f4a0-b25d-4fe4-8593-6b50e8bdb94f`. | The next run can validate IAM.4 through the intended route instead of stopping on runtime gating. |
| `EC2.53` | Direct `EC2.53` Security Hub control status is `DISABLED`, but the seeded public-admin SGs produced live `EC2.18` and `EC2.19` findings that the product canonicalized into `EC2.53` actions `7eba03c7-2145-43fe-9b64-acc313aa5dfe` and `a58547f3-4e20-49c7-8fea-360ab1e6811b`. | The next run can use the canonicalized product actions for executable and downgrade proof, but the direct control-status nuance must be documented. |
| `S3.9` / `CloudTrail.1` / `Config.1` | Dedicated proof-friendly buckets were created and verified reachable by the import role. Bucket-scoped executable previews and bundle runs now exist for S3.9, CloudTrail.1, and Config.1. | These families now have concrete, reusable executable-ready targets in `eu-north-1`. |
| `S3.2` | Fresh ingest still produced only account-scoped action `5b2c153e-ab45-4436-9113-35cffa16dc4a`, and executable proof still lacks bucket identity plus privacy evidence. | Keep S3.2 classified as downgrade/manual only unless a bucket-scoped case materializes or an AWS-backed record is intentionally restored. |
| `S3.5` | Seeded bucket-scoped action `0bb3dc7b-fcbd-42b9-8ea8-ffa37a0b6fcb` now exists, but create/run detail still downgraded to non-executable review bundle `caa4c343-369f-4a32-9d66-03a2cef9f1a2`. | The next run can validate downgrade behavior directly, but executable proof is still blocked on the create-time support-tier mismatch. |
| `S3.11` / `S3.15` | Direct Security Hub control status in `eu-north-1` is `DISABLED` for both families, and the current control titles are `event notifications` and `Object Lock`, not the product's current `lifecycle` and `SSE-KMS` semantics. No product actions materialized after seeding. | These families remain blocked for the next live run with an exact actionable reason instead of vague "missing data". |

## Environment preparation completed

- Built a disposable isolated runtime on local `master` with:
  - isolated Postgres on port `55438`
  - temporary SaaS-account SQS queues in `029037611564`
  - isolated tenant `4cc07fb3-c45f-4be3-936d-2253d3e69548`
  - isolated account registration for `696505809372`
- Enabled IAM.4 in the isolated runtime only through env overrides; defaults in `backend/config.py` remain unchanged.
- Repaired the customer-run apply/rollback path by creating a temporary root access key in the signed-in target account and updating local profile `test28-root` until `aws sts get-caller-identity --profile test28-root` returned `arn:aws:iam::696505809372:root`.
- Seeded dedicated target-account resources in `eu-north-1` for the next live run:
  - security groups `sg-06f6252fa8a95b61d` and `sg-0ef32ca8805a55a8b`
  - buckets `security-autopilot-w6-envready-accesslogs-696505809372`, `security-autopilot-w6-envready-cloudtrail-696505809372`, `security-autopilot-w6-envready-config-696505809372`, `security-autopilot-w6-envready-s311-exec-696505809372`, `security-autopilot-w6-envready-s311-review-696505809372`, and `security-autopilot-w6-envready-s315-exec-696505809372`
- Verified the import-role proof path on the seeded buckets:
  - `HeadBucket` now succeeds on the dedicated access-logs, CloudTrail, and Config buckets
  - `GetBucketLogging` succeeds on the access-logs bucket
  - `GetLifecycleConfiguration` distinguishes the S3.11 executable vs downgrade buckets
  - `GetBucketEncryption` succeeds on the seeded S3.15 bucket
- Cleaned the disposable runtime after evidence capture:
  - backend stopped
  - worker stopped
  - disposable Postgres stopped
  - five temporary SaaS-account queues deleted and probed as `NonExistentQueue`

## Recommended next-step framing

- Recommended next step: run the next Wave 6 live AWS validation from this readiness matrix
- Recommended gate framing for that run: `meaningful live rerun`, not `Wave 6 complete`
- Families that still need product or AWS-side follow-up before they can be marked ready:
  - `S3.2` executable case
  - `S3.5` executable case
  - `S3.11`
  - `S3.15`
- Fresh residual product risks to watch during the next live run:
  - `S3.9` account-scoped preview still mis-parses `source_bucket_name`
  - `S3.5` preview vs create support-tier mismatch still exists on the seeded bucket-scoped case
