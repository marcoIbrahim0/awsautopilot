# Phase 2 Live Test C Results (Rerun)

- C1: PASS
- C2: PASS
- C3: PASS
- C4: PASS
- C5: PASS

## C1 (CloudTrail fresh bucket)
- `IsLogging=True` after ~5 minutes (`raw/c1_trail_status_after_5m.json`).
- `LatestDeliveryError` and `LatestNotificationError` not present (no delivery errors reported).
- Objects observed under CloudTrail prefix: see `raw/c1_bucket_objects_after_5m.json`.

## C2 (CloudTrail existing bucket with pre-existing policy)
- Before SIDs: `['C2PreExistingDenyDeleteBucket']`
- After SIDs: `['C2PreExistingDenyDeleteBucket', 'AWSCloudTrailAclCheck', 'AWSCloudTrailWrite']`
- Delivery health after ~5 min: `IsLogging=True`, `LatestDeliveryError=None` (`raw/c2_trail_status_after_5m.json`).

## C3 (S3.5 with existing Deny statement)
- Before SIDs: `['C3PreExistingDenyDeleteBucket']`
- After SIDs: `['C3PreExistingDenyDeleteBucket', 'DenyInsecureTransport']`
- Result basis: original deny preserved and SSL deny added.

## C4 (S3.5 with no prior policy)
- Pre-check `get-bucket-policy` returned `NoSuchBucketPolicy` (exit code in `raw/c4_policy_before.exitcode`).
- After SIDs: `['DenyInsecureTransport']`

## C5 (S3.5 fail-closed generation)
- Expected error: `bucket_policy_preservation_evidence_missing`
- Actual: `bucket_policy_preservation_evidence_missing` with `raised=True` (`raw/c5_generation_probe.json`).

## Regression Risk Notes
- CloudTrail and S3.5 bundles now merge existing policies via local AWS CLI + Python in a null_resource local-exec; regression risk concentrates around local execution environment availability (python3/aws cli) and runner IAM permissions for get/put-bucket-policy.
- Trail name remains static (security-autopilot-trail), so repeated tests must continue to destroy/import between isolated runs to avoid cross-run collisions.
- Terraform provider installation can stall in restricted networks; this run used plugin-dir from previously initialized providers to ensure deterministic execution.

## Cleanup
- Deleted test trail `security-autopilot-trail`; post-delete verification in `raw/cleanup_describe_trail_after_delete.json`.
- Verified all four test buckets are absent in `raw/cleanup_bucket_head_checks.txt`.
