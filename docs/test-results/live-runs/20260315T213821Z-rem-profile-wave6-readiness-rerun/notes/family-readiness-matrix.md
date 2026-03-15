# Wave 6 Family Readiness Matrix

- Run ID: `20260315T213821Z-rem-profile-wave6-readiness-rerun`
- Date (UTC): `2026-03-15T21:38:21Z`
- Environment used: `local master against resumed isolated runtime`
- Branch tested: `master`
- Exact HEAD tested: `1039467ef3ae84ea1f99fbca7ee6dc25be813f0b`
- AWS accounts and regions:
  - SaaS queue/runtime account `029037611564` in `eu-north-1`
  - Isolated AWS test account `696505809372` in `eu-north-1` and `us-east-1`
- Supported execution model: `customer-run PR bundles only; archived public SaaS-managed plan/apply stayed archived`
- Credential path for customer-run validation:
  - Product/runtime read path: `arn:aws:iam::696505809372:role/CodexP2SecurityHubImportRole`
  - Customer-run apply/rollback path: local AWS CLI profile `test28-root`
  - `role_write_arn` remains `null` and was not used

## Summary

| Family | Executable case ready | Downgrade case ready | Fully ready for full gate | Notes |
| --- | --- | --- | --- | --- |
| `EC2.53` | `Yes` | `Yes` | `Yes` | Unchanged from the March 15 environment-readiness package. |
| `IAM.4` | `Yes` | `Yes` | `Yes` | Unchanged from the March 15 environment-readiness package; `/api/root-key-remediation-runs` remains the only execution authority. |
| `S3.2` | `Yes` | `Yes` | `Yes` | Fresh post-seeding recompute created bucket-scoped canonical `S3.2` actions from live `S3.8` findings. |
| `S3.5` | `Yes` | `Yes` | `Yes` | Create/run-detail now preserve executable resolution; downgrade path remains fail-closed when evidence is under-proven. |
| `S3.11` | `Yes` | `No` | `No` | Executable path restored through live `S3.13` aliasing, but the review bucket currently passes `S3.13`, so no truthful failing downgrade case exists. |
| `S3.9` | `Yes` | `Yes` | `Yes` | Unchanged from the March 15 environment-readiness package. |
| `S3.15` | `No` | `No` | `No` | Still no live Security Hub control/finding mapping to the product’s SSE-KMS family semantics. |
| `CloudTrail.1` | `Yes` | `Yes` | `Yes` | Unchanged from the March 15 environment-readiness package. |
| `Config.1` | `Yes` | `Yes` | `Yes` | Unchanged from the March 15 environment-readiness package. |

## Families closed in this rerun

### `S3.2`

- Executable case ready: `Yes`
- Downgrade case ready: `Yes`
- Root cause:
  - Fresh bucket-scoped public-access failures currently surface from Security Hub control `S3.8`, not `S3.2`.
  - The product already canonicalizes `S3.8` into the `S3.2` family, but the stale saved action snapshot hid the post-seeding bucket-scoped actions.
- Target action IDs / resource IDs:
  - Executable action `1166ca21-3d37-4bfc-96d8-4362bacf6f47`
  - Executable resource `arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372`
  - Executable run `726e95b9-c33c-4bf6-8f27-ccfe0e84b882`
  - Downgrade action `540f1cd9-1087-46f8-ae79-dcf746acf206`
  - Downgrade resource `arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372`
- Region: `eu-north-1`
- Proof summary:
  - Executable preview and run detail kept `profile_id = s3_bucket_block_public_access_standard` and `support_tier = deterministic_bundle`.
  - Downgrade preview switched to `profile_id = s3_bucket_block_public_access_manual_preservation` and `support_tier = manual_guidance_only`.
  - Safety boundary remained intact:
    - executable only when `bucket_policy_public=false`, `website_configured=false`, and `access_path_evidence_available=true`
    - manual preservation when website hosting is enabled

### `S3.5`

- Executable case ready: `Yes`
- Downgrade case ready: `Yes`
- Root cause:
  - Create-time resolution was overriding the already-approved executable preview because `_preserve_selection_support_tier()` did not preserve S3.5 strategy support tiers.
- Target action IDs / resource IDs:
  - Executable action `9c67856d-10d4-4359-aef2-059fb3be9edc`
  - Executable resource `arn:aws:s3:::security-autopilot-w6-envready-config-696505809372`
  - Executable run `0c7045dd-3745-4bce-b452-e796ce4b67a8`
  - Downgrade action `230d6326-f361-4a57-b38a-7be3a16ca99b`
  - Downgrade resource `AWS::::Account:696505809372`
- Region: `eu-north-1`
- Proof summary:
  - Executable preview, create response, and run detail all now resolve to `profile_id = s3_enforce_ssl_strict_deny` with `support_tier = deterministic_bundle`.
  - Downgrade preview on the account-scoped under-proven case resolves to `review_required_bundle` with blocked reasons:
    - `Bucket policy preservation evidence is missing for merge-safe SSL enforcement.`
    - `Could not derive bucket name from action target.`
    - `Missing bucket identifier for SSL policy analysis.`

### `S3.11`

- Executable case ready: `Yes`
- Downgrade case ready: `No`
- Root cause:
  - Current live lifecycle findings are emitted on enabled control `S3.13`, not the old direct `S3.11` lifecycle mapping.
- Target action IDs / resource IDs:
  - Executable action `3b03726e-a29f-473c-a7ae-ecac0f1ee1c5`
  - Executable resource `arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372`
  - Executable run `c2aab0c4-ed7d-4320-a7d7-34e6c059f2b1`
  - Review resource investigated: `arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372`
- Region: `eu-north-1`
- Proof summary:
  - Live `S3.13` findings now materialize as canonical `S3.11` lifecycle actions, and the executable case persists `deterministic_bundle`.
  - Review bucket currently has lifecycle configured and returns `S3.13 PASSED`.
  - Post-seeding action inventory contains no `s3_bucket_lifecycle_configuration` action for the review bucket.
- Truthful conclusion:
  - The family is executable-ready.
  - The family is not downgrade-ready under current live AWS semantics because no failing lifecycle-present case exists to materialize.

### `S3.15`

- Executable case ready: `No`
- Downgrade case ready: `No`
- Root cause:
  - The isolated account still has no current enabled Security Hub control/finding that maps to the product’s `s3_bucket_encryption_kms` family.
- Region: `eu-north-1`
- Proof summary:
  - Fresh control inventory still contains only:
    - `S3.13` `S3 general purpose buckets should have Lifecycle configurations`
    - `S3.2` `S3 general purpose buckets should block public read access`
    - `S3.8` `S3 general purpose buckets should block public access`
  - Fresh `S3.15` findings count remains `0`.
  - Post-seeding action inventory contains `[]` for `s3_bucket_encryption_kms`.
- Truthful conclusion:
  - The family remains blocked by live AWS/product drift.
  - No alias or scenario generation should be invented from shadow or inventory-only data.

## Carry-over families from the March 15 environment-readiness package

- `EC2.53`, `IAM.4`, `S3.9`, `CloudTrail.1`, and `Config.1` keep the ready/not-ready status and exact proof references already recorded in:
  - [`../20260315T201821Z-rem-profile-wave6-environment-readiness/notes/family-readiness-matrix.md`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T201821Z-rem-profile-wave6-environment-readiness/notes/family-readiness-matrix.md)
- This rerun did not invalidate any of those earlier ready cases.
- Net full-gate status after combining the March 15 baseline and this blocker-closure rerun:
  - `7` families fully ready
  - `1` family executable-ready only (`S3.11`)
  - `1` family still blocked (`S3.15`)
