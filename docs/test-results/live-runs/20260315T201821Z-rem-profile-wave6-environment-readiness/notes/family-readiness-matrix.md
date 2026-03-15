# Wave 6 Family Readiness Matrix

- Run ID: `20260315T201821Z-rem-profile-wave6-environment-readiness`
- Date (UTC): `2026-03-15T20:18:21Z`
- Environment used: `local master against isolated runtime`
- Branch tested: `master`
- Exact HEAD tested: `b6952f2ab9c7a3ae2aa7a17faa7104312f6402e5`
- AWS accounts and regions:
  - SaaS queue/runtime account `029037611564` in `eu-north-1`
  - Isolated AWS test account `696505809372` in `eu-north-1` and `us-east-1`
- Supported execution model: `customer-run PR bundles only; archived public SaaS-managed plan/apply stayed archived`
- Credential path for executable customer-run validation:
  - Read path: `arn:aws:iam::696505809372:role/CodexP2SecurityHubImportRole`
  - Apply/rollback path: local AWS CLI profile `test28-root`
  - `role_write_arn` remains `null` and was not used

## Fresh authoritative live-AWS differences from the earlier March 15 gate

- `IAM.4` is no longer runtime-blocked in the isolated environment. `/api/root-key-remediation-runs` returned `201` and created root-key run `a850f4a0-b25d-4fe4-8593-6b50e8bdb94f`.
- `EC2.53` direct Security Hub control status in `eu-north-1` is `DISABLED`, but the seeded public-admin security groups produced live `EC2.18` and `EC2.19` findings that the product canonicalized into `EC2.53` actions.
- `S3.11` direct Security Hub control status in `eu-north-1` is `DISABLED` and currently represents `S3 Event Notifications`, not the product's current `lifecycle configuration` family semantics.
- `S3.15` direct Security Hub control status in `eu-north-1` is `DISABLED` and currently represents `Object Lock`, not the product's current `SSE-KMS` family semantics.
- `S3.2` remained account-scoped only after the fresh ingest. No bucket-scoped executable-ready case materialized from the current live data.
- `S3.9` bucket-scoped seeded cases are authoritative for readiness. The account-scoped preview currently mis-parses `source_bucket_name` as `eu-north-1` and should not be used for executable proof.

## Summary

| Family | Executable case ready | Downgrade case ready | Notes |
| --- | --- | --- | --- |
| `EC2.53` | `Yes` | `Yes` | Runnable bundle exists, but the live source findings are `EC2.18`/`EC2.19` canonicalized to `EC2.53`. |
| `IAM.4` | `Yes` | `Yes` | Special case: authoritative route is ready; generic remediation-profile surfaces remain manual-guidance only by design. |
| `S3.2` | `No` | `Yes` | Still account-scoped only; executable branch lacks bucket identity plus privacy proof. |
| `S3.5` | `No` | `Yes` | Fresh bucket-scoped case exists, but create/run detail still downgraded to a non-executable review bundle. |
| `S3.11` | `No` | `No` | Blocked by current Security Hub control drift and no materialized product action. |
| `S3.9` | `Yes` | `Yes` | Bucket-scoped executable and downgrade-ready cases exist on dedicated seeded buckets. |
| `S3.15` | `No` | `No` | Blocked by current Security Hub control drift and no materialized product action. |
| `CloudTrail.1` | `Yes` | `Yes` | Dedicated proof-friendly log bucket is reachable and bucket-scoped runtime proof now passes. |
| `Config.1` | `Yes` | `Yes` | Centralized-delivery branch is executable with the seeded bucket and repaired operator profile. |

## Family Details

### `EC2.53`

- Executable case ready: `Yes`
- Downgrade case ready: `Yes`
- Target action ID / group ID / resource ID:
  - Executable candidate action `7eba03c7-2145-43fe-9b64-acc313aa5dfe`
  - Downgrade candidate action `a58547f3-4e20-49c7-8fea-360ab1e6811b`
  - Resources `arn:aws:ec2:eu-north-1:696505809372:security-group/sg-06f6252fa8a95b61d` and `arn:aws:ec2:eu-north-1:696505809372:security-group/sg-0ef32ca8805a55a8b`
  - Runnable proof bundle run `9910cdcd-253d-478e-847f-4f8f0112a0cd`
- Region: `eu-north-1`
- Required credentials to finish live validation: `test28-root` for manual PR-bundle apply/rollback; import-role read access is already sufficient for scenario confirmation
- Cleanup/rollback plan:
  - If the bundle is applied, rollback can re-authorize the public `22/3389` rules temporarily
  - After the next live run, delete both dedicated security groups because they are seeded test-only resources
- Remaining blocker if not ready: `none for readiness`
- Important note: direct Security Hub `EC2.53` is disabled in this account; the ready case is backed by live `EC2.18` and `EC2.19` findings that the product canonicalizes to `EC2.53`

### `IAM.4`

- Executable case ready: `Yes`
- Downgrade case ready: `Yes`
- Target action ID / group ID / resource ID:
  - Action `3d40bb66-ab31-4946-8b48-a97fded7710e`
  - Resource `AWS::::Account:696505809372`
  - Authoritative root-key run `a850f4a0-b25d-4fe4-8593-6b50e8bdb94f`
- Region: `eu-north-1`
- Required credentials to finish live validation:
  - Isolated runtime env overrides for `ROOT_KEY_SAFE_REMEDIATION_ENABLED`, `ROOT_KEY_SAFE_REMEDIATION_API_ENABLED`, and `ROOT_KEY_SAFE_REMEDIATION_STRICT_TRANSITIONS`
  - Local profile `test28-root` for target-account root-key cleanup after validation
- Cleanup/rollback plan:
  - Generic remediation-profile surfaces remain guidance only and require no cleanup
  - After the next live run, delete or rotate the temporary root access key from the AWS console and repair the local `test28-root` profile
- Remaining blocker if not ready: `none for runtime authority readiness`
- Important note: generic create stays fail-closed with `reason=root_key_execution_authority`; `/api/root-key-remediation-runs` remains the only execution authority

### `S3.2`

- Executable case ready: `No`
- Downgrade case ready: `Yes`
- Target action ID / group ID / resource ID:
  - Account-scoped action `5b2c153e-ab45-4436-9113-35cffa16dc4a`
  - Resource `AWS::::Account:696505809372`
- Region: `eu-north-1`
- Required credentials to finish live validation:
  - Import-role read path is sufficient for the current downgrade/manual proof
  - A future executable proof would still need `test28-root`, but no executable-ready case exists yet
- Cleanup/rollback plan:
  - No seeded S3.2-specific bucket was adopted as the live action target
  - If a dedicated S3.2 case is seeded later, delete the bucket or restore its original public-access configuration after proof
- Remaining blocker if not ready:
  - `Runtime evidence could not prove the bucket is private and website hosting is disabled.`
  - `Missing bucket identifier for access-path validation.`

### `S3.5`

- Executable case ready: `No`
- Downgrade case ready: `Yes`
- Target action ID / group ID / resource ID:
  - Seeded bucket-scoped action `0bb3dc7b-fcbd-42b9-8ea8-ffa37a0b6fcb`
  - Resource `arn:aws:s3:::security-autopilot-w6-envready-config-696505809372`
  - Downgrade/reference run `caa4c343-369f-4a32-9d66-03a2cef9f1a2`
- Region: `eu-north-1`
- Required credentials to finish live validation:
  - Import-role read path is sufficient for the current review/manual proof
  - A future runnable executable proof would need `test28-root`
- Cleanup/rollback plan:
  - If later executable output lands and is applied, rollback is `delete-bucket-policy` on the seeded config bucket
  - After the next live run, empty and delete the seeded config bucket if it is no longer needed for Config.1 or S3.9 validation
- Remaining blocker if not ready:
  - Preview resolves `deterministic_bundle`, but create/run detail persists `review_required_bundle`
  - The saved bundle is `non_executable_bundle=true`, so there is still no runnable executable proof case

### `S3.11`

- Executable case ready: `No`
- Downgrade case ready: `No`
- Target action ID / group ID / resource ID:
  - No action materialized from the fresh ingest
  - Seeded buckets for future investigation: `arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372` and `arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372`
- Region: `eu-north-1`
- Required credentials to finish live validation:
  - Current blocker is not credentials; it is missing compatible live control/action materialization
  - `test28-root` would be sufficient if a future executable case existed
- Cleanup/rollback plan:
  - Delete the two seeded S3.11 buckets after the mapping/data issue is resolved and the next live run no longer needs them
  - Remove the lifecycle rule from the `s311-review` bucket before deleting it
- Remaining blocker if not ready:
  - Direct Security Hub `S3.11` is `DISABLED` in this account
  - Current AWS control semantics are `event notifications`, while the product family still expects `lifecycle configuration`
  - No fresh product action materialized even after seeding lifecycle-ready buckets

### `S3.9`

- Executable case ready: `Yes`
- Downgrade case ready: `Yes`
- Target action ID / group ID / resource ID:
  - Bucket-scoped action `f053a0cb-cd59-426c-97b8-8954dbbcab92`
  - Resource `arn:aws:s3:::security-autopilot-w6-envready-config-696505809372`
  - Runnable proof bundle run `a597f78b-47a2-40c0-afd8-512268050aaf`
  - Downgrade preview uses the same source bucket with same-bucket destination safety failure
- Region: `eu-north-1`
- Required credentials to finish live validation: `test28-root` for manual bundle apply/rollback; import-role read path already proves destination-bucket reachability
- Cleanup/rollback plan:
  - If the bundle is applied, remove access logging from the seeded source bucket or revert it to its prior destination
  - After the next live run, empty and delete the dedicated access-logs and config buckets if they are no longer needed
- Remaining blocker if not ready: `none for the bucket-scoped proof path`
- Important note: do not use account-scoped action `f2b47105-830a-4fcf-b27f-2b73f9eb2ad2` for executable proof because the saved preview mis-parsed `source_bucket_name`

### `S3.15`

- Executable case ready: `No`
- Downgrade case ready: `No`
- Target action ID / group ID / resource ID:
  - No action materialized from the fresh ingest
  - Seeded bucket for future investigation: `arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372`
- Region: `eu-north-1`
- Required credentials to finish live validation:
  - Current blocker is not credentials; it is missing compatible live control/action materialization
  - `test28-root` would be sufficient if a future executable case existed
- Cleanup/rollback plan:
  - Delete the seeded S3.15 bucket after the mapping/data issue is resolved and the next live run no longer needs it
- Remaining blocker if not ready:
  - Direct Security Hub `S3.15` is `DISABLED` in this account
  - Current AWS control semantics are `Object Lock`, while the product family still expects `SSE-KMS`
  - No fresh product action materialized even after seeding a bucket with probe-friendly encryption visibility

### `CloudTrail.1`

- Executable case ready: `Yes`
- Downgrade case ready: `Yes`
- Target action ID / group ID / resource ID:
  - Action `b0460b2d-5749-4e93-90e5-e5e7130df47d`
  - Resource `AWS::::Account:696505809372`
  - Runnable proof bundle run `878705c2-dc6b-466a-b562-42b20fb9f785`
  - Executable bucket `security-autopilot-w6-envready-cloudtrail-696505809372`
- Region: `eu-north-1`
- Required credentials to finish live validation: `test28-root` for manual bundle apply/rollback; import-role read path already proves the seeded bucket is reachable
- Cleanup/rollback plan:
  - If the bundle is applied, stop and delete the test trail or restore it to the previous bucket before cleanup
  - Empty and delete the seeded CloudTrail bucket after the next live run if no longer needed
- Remaining blocker if not ready: `none for readiness`
- Important note: downgrade proof should continue to use the blocked old bucket path `config-bucket-696505809372` because it still returns `403`

### `Config.1`

- Executable case ready: `Yes`
- Downgrade case ready: `Yes`
- Target action ID / group ID / resource ID:
  - Action `481a081a-66ee-4320-bc69-4506dc59cfe3`
  - Resource `AWS::::Account:696505809372`
  - Runnable proof bundle run `5dd45a6f-fa8b-4a1b-bd8b-aa55cca84f94`
  - Executable bucket `security-autopilot-w6-envready-config-696505809372`
- Region: `eu-north-1`
- Required credentials to finish live validation: `test28-root` for manual bundle apply/rollback; import-role read path already proves the seeded centralized-delivery bucket is reachable
- Cleanup/rollback plan:
  - If the bundle is applied, stop the recorder or restore the prior delivery-channel bucket after proof
  - Empty and delete the seeded Config bucket after the next live run if it is no longer needed for S3.5 or S3.9 evidence
- Remaining blocker if not ready: `none for readiness`
- Important note: downgrade proof should continue to use the old bucket path `config-bucket-696505809372`, which still fails with `403` plus unproven policy compatibility
