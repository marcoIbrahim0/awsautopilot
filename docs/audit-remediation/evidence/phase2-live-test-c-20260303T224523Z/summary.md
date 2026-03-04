# Phase 2 Live Test C Results

- C1: FAIL
- C2: FAIL
- C3: FAIL
- C4: PASS
- C5: FAIL

## C1 (CloudTrail fresh bucket)
- First apply: **FAILED** with `InsufficientS3BucketPolicyException` (`raw/c1_first_apply_error_excerpt.txt`).
- Retry apply + 5 min check: `IsLogging=true`, `LatestDeliveryError=null`, `LatestNotificationError=null` (`raw/c1_retry_status_after_5m.json`).
- Result basis: case marked FAIL because initial one-shot apply on fresh bucket did not satisfy acceptance.

## C2 (CloudTrail existing bucket with pre-existing policy)
- Delivery health after 5 min: `IsLogging=true`, `LatestDeliveryError=null` (`raw/c2_rerun_trail_status_after_5m.json`).
- Policy preservation check:
  - Before SIDs: `['C2PreExistingDenyDeleteBucket', 'AWSCloudTrailAclCheck', 'AWSCloudTrailWrite']`
  - After SIDs: `['AWSCloudTrailAclCheck', 'AWSCloudTrailWrite']`
- Result: **FAIL** (pre-existing `C2PreExistingDenyDeleteBucket` was removed).

## C3 (S3.5 with existing Deny statement)
- Policy preservation check:
  - Before SIDs: `['C3PreExistingDenyDeleteBucket']`
  - After SIDs: `['DenyInsecureTransport']`
- Result: **FAIL** (original deny removed; only SSL deny remains).

## C4 (S3.5 with no prior policy)
- Pre-check: `get-bucket-policy` returned `NoSuchBucketPolicy` (exit `254`).
- After apply SIDs: `['DenyInsecureTransport']`
- Result: **PASS**.

## C5 (S3.5 fail-closed generation)
- Expected: `bucket_policy_preservation_evidence_missing`.
- Actual: bundle generated (`providers.tf`, `s3_bucket_require_ssl.tf`, `README.txt`).
- Result: **FAIL**.

## Regression Risk Notes
- CloudTrail fresh-bucket one-shot apply has a policy-order race and can fail before trail creation.
- CloudTrail existing-bucket behavior replaces policy instead of supplementing.
- S3.5 behavior replaces policy instead of preserving existing statements.
- S3.5 fail-closed guard for missing preservation evidence is not enforced.
- Hardcoded CloudTrail trail name causes cross-run collisions in repeated live tests.

## Cleanup
- Deleted test trail `security-autopilot-trail` and verified absent in `raw/cleanup_describe_trail_after_delete.json`.
- Deleted test buckets (`c1`..`c4`) and verified absent in `raw/cleanup_bucket_head_checks.txt`.
