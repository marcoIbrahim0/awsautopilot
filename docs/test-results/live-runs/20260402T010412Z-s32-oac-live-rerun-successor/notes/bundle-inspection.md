# Bundle inspection notes

## Scope

- Evidence package: `20260402T010412Z-s32-oac-live-rerun-successor`
- Fresh remediation run: `2c4d0e45-c55c-4451-a633-56ea07895aee`
- Fresh group run: `d0fbee4a-96d0-4473-98ff-58aa6e78c14c`

## Real affected action outcome in the fresh bundle

- The real affected action moved from manual-only downgrade to executable bundle output.
- Retained file:
  - `bundle/extracted/executable/actions/05-arn-aws-s3-security-autopilot-dev-serverless-src-1dc66e7e/decision.json`
- Key facts from that decision:
  - `profile_id = s3_migrate_cloudfront_oac_private`
  - `support_tier = deterministic_bundle`
  - `blocked_reasons = []`
  - `target_bucket_exists = true`
  - `target_bucket_verification_available = true`
  - `existing_bucket_policy_json_captured = true`

## Fresh grouped bundle shape

- Manual guidance actions: `1`
- Executable action folders: `32`
- The only remaining manual-guidance entry is the account-scoped action:
  - `manual_guidance/actions/01-aws-account-696505809372-19337c80/decision.json`
- The real affected bucket is not in manual guidance anymore.

## Fresh customer-run execution result

- `run_all.sh` correctly defaulted to:
  - `parallel executions=1`
  - `cloudfront_oac_bundles=1`
- The first executable action still failed locally before plan completion because Terraform could not start the `hashicorp/external` provider schema load.

## Outcome

- The bucket-verification `403` blocker for the real affected action is closed.
- The remaining blocker is now isolated to local Terraform execution of the generated executable bundle.
