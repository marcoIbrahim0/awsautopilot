# March 23, 2026 Live E2E: `SSM.7` and `CloudTrail.1`

## Scope

- Live API: `https://api.ocypheris.com`
- Account: `696505809372`
- Regions:
  - `SSM.7`: `us-east-1`
  - `CloudTrail.1`: `eu-north-1`, `us-east-1`

## Outcome

- `SSM.7`: PASS
- `CloudTrail.1`: PASS after deploy

## `SSM.7`

- Target live action: `e6b1eac2-041c-4fb3-9a47-2525a3afa908`
- Strategy: `ssm_disable_public_document_sharing`
- Remediation run: `cea5c507-fbc1-41a9-941b-131429704ff3`
- Run creation returned `201`
- Remediation run reached terminal `success`
- PR bundle downloaded successfully
- Local Terraform apply succeeded with `AWS_PROFILE=test28-root`
- Post-apply live refresh succeeded:
  - ingest triggered
  - action compute triggered
  - reconciliation run `96a6078e-6f02-44b0-ad4b-47f01ee35eea` reached `succeeded`
- First verification poll already showed:
  - action status `resolved`
  - matching `SSM.7` finding status `RESOLVED`

Conclusion: the current production `SSM.7` path is live-valid end to end for the tested `us-east-1` action.

## `CloudTrail.1`

### Current default live behavior

- `eu-north-1` action: `2ea6f141-6134-4dcd-8c82-4f0d0b6e582d`
- `us-east-1` action: `3301b44c-8846-49c2-9f27-823e6a77e559`
- Both live option/preview surfaces still show unresolved bucket prerequisites:
  - missing default `cloudtrail.default_bucket_name`
  - blocked reason `CloudTrail log bucket name is unresolved...`
- Single-run create behavior is still not the grouped fail-closed path:
  - `eu-north-1` accepted run `0730bf95-34f7-40a6-87b5-c11d593b705d`
  - run reached `success`
  - downloaded bundle contains only:
    - `README.txt`
    - `decision.json`
    - `pr_automation/*`
  - resolution support tier is `review_required_bundle`
  - outcome is `Non-executable remediation guidance bundle generated`
- `us-east-1` single-run create hit an existing duplicate-active-run guard:
  - `409 duplicate_active_run`
  - existing run `92e67c82-926f-4847-a7ab-eb0d2cd23230`

### New bucket-toggle live check before deploy

Safe live check only; no bundle was applied.

- Sent `strategy_inputs.trail_bucket_name`
- Sent `strategy_inputs.create_bucket_if_missing=true`
- Tested both with and without `bucket_creation_acknowledged=true`
- Production API returned `400` both times:
  - `Invalid strategy selection`
  - `strategy_inputs contains unknown field(s): create_bucket_if_missing, trail_bucket_name.`

This proved the new CloudTrail bucket-toggle contract implemented locally was not deployed on the live API yet at the start of this run. Production still behaved as the older unresolved-bucket single-run contract, where the default path downgraded to a review-only bundle.

### Post-deploy verification

After deploying the current backend runtime to production, the same live checks changed as expected:

- default preview now includes additive resolved input `create_bucket_if_missing = false`
- default preview `preservation_summary` now includes:
  - `trail_bucket_source`
  - `trail_bucket_mode`
  - `bucket_creation_requested`
- `create_bucket_if_missing=true` without approval now fails closed as:
  - `400 Bucket creation acknowledgement required`
- `create_bucket_if_missing=true` with `bucket_creation_acknowledged=true` now succeeds:
  - remediation run `3a6200f9-919d-43a4-a53c-92c79380329a`
  - terminal status `success`
  - outcome `PR bundle generated`
  - support tier `deterministic_bundle`
  - resolved inputs include:
    - `trail_bucket_name = ocypheris-live-e2e-cloudtrail-20260323-eu-north-1`
    - `create_bucket_if_missing = true`
- downloaded bundle now contains executable Terraform:
  - `cloudtrail_enabled.tf`
  - `providers.tf`

No live Terraform apply was executed for the post-deploy create-if-missing CloudTrail bundle in this run. The live validation here proves the contract is deployed and the executable bundle path is now available on production.

## Key Takeaways

- `SSM.7` is green on live for the tested action.
- `CloudTrail.1` default live path remains review-only and non-executable when no bucket is resolved.
- After deploy, the new additive CloudTrail inputs are accepted by production and the approval-gated create-if-missing path now generates an executable bundle.
