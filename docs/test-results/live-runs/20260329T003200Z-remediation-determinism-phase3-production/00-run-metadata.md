# Run Metadata

- Run ID: `20260329T003200Z-remediation-determinism-phase3-production`
- Date (UTC): `2026-03-29`
- Surface: `https://api.ocypheris.com`
- Tenant: `Marco`
- Tenant ID: `e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`
- Canary account: `696505809372`
- Region: `eu-north-1`

## Scope

- `WI-4` S3.5 apply-time policy merge
- `WI-5` S3.2 website-to-CloudFront private-origin migration
- `WI-9` S3.2 OAC apply-time policy capture
- `WI-10` S3.2 public-policy scrub review bundle
- `WI-11` S3.11 apply-time lifecycle fallback

## Environment Notes

- Production health and readiness passed during this run.
- Production operator auth for tenant `Marco` succeeded.
- Local tooling proved available:
  - `terraform`
  - `aws`
- Canary root credentials resolved to account `696505809372`.
- The canary read-role policy was updated during this run so `SecurityAutopilotReadRolePolicy` default version `v10` now includes `s3:GetBucketWebsite`. This was required to truthfully exercise `WI-5` parity on production.

## Retained Outputs

- `local-gate/` retains the exact Gate 3B pytest transcripts.
- `evidence/api/` retains production auth, action/options/preview/create/run-detail, and parity captures.
- `evidence/aws/` retains AWS CLI state checks, Terraform transcripts, rollback transcripts, and cleanup verification.
- `evidence/bundles/wi4/` and `evidence/bundles/wi11/` retain extracted production PR bundles plus bundle-local rollback snapshots.
