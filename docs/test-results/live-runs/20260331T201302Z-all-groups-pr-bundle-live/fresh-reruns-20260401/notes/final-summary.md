# Fresh Signature Rerun Summary

## Scope

- Parent run: `20260331T201302Z-all-groups-pr-bundle-live`
- Follow-up date: April 1, 2026 UTC
- Goal: force fresh grouped PR-bundle generation for one `S3.9` group and one `SSM.7` group without reusing stale successful grouped runs

## Method

- Used `POST /api/action-groups/{group_id}/bundle-run` on live SaaS.
- Changed the grouped request signature by adding a unique `repo_target` for each request.
- Left the action family and primary strategy unchanged.

## Results

### `S3.9` `s3_bucket_access_logging`

- Group: `984e6f5e-d1e6-44aa-90e6-1a3ddc152a2c`
- Fresh group run: `d7f5db9e-68dd-4df8-8efc-bfa8c1901413`
- Fresh remediation run: `a5dd16fc-5628-42b5-b858-2a49dadcfe33`
- Outcome: fresh generation succeeded and the ZIP is now a mixed-tier bundle:
  - `14` executable action folders
  - `2` review-required action folders
- Representative executable action evidence now shows:
  - `outcome=executable_bundle_generated`
  - `has_runnable_terraform=true`
  - `profile_id=s3_enable_access_logging_guided`

Residual review-only members in the same fresh bundle:
- action `0fd42f91-d019-4b8b-a9ae-cdf93b99cdeb`
  - blocked reason: `Source bucket scope could not be proven for S3 access logging; review the affected bucket relationship manually.`
- action `bed34478-fc8a-4714-bb40-e52cfbc8bf9b`
  - blocked reason: `Log destination must be a dedicated bucket and cannot match the source bucket.`

### `SSM.7` `ssm_block_public_sharing`

- Group: `ed48e583-8b8e-43b4-ad5e-3641b8276909`
- Fresh group run: `fd7b8ba5-f5e6-4bdb-a42c-64ce2ede59c9`
- Fresh remediation run: `f5eb6579-6901-4374-b4ff-3bd466d29958`
- Outcome: fresh generation succeeded, but the ZIP remained metadata-only:
  - `0` executable action folders
  - `1` review-required action folder
- Fresh decision still records:
  - `support_tier=review_required_bundle`
  - `outcome=review_required_metadata_only`
  - `blocked_reasons=[]`
  - rationale: `Run creation was accepted after risk_acknowledged=true satisfied review-required checks.`

## Interpretation

- `S3.9` was previously masked by duplicate-run reuse. Once the request signature changed, the live system generated a fresh mixed executable bundle and proved that most current members are executable.
- `SSM.7` was not just stale duplicate reuse. Even with a fresh request signature, the live grouped path still produces a review-required metadata-only bundle for this family.

## Evidence Pointers

- Fresh rerun summary: [summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260331T201302Z-all-groups-pr-bundle-live/fresh-reruns-20260401/summary.json)
- Fresh `S3.9` create response: [create.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260331T201302Z-all-groups-pr-bundle-live/fresh-reruns-20260401/s3-9/create.json)
- Fresh `S3.9` ZIP: [pr-bundle.zip](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260331T201302Z-all-groups-pr-bundle-live/fresh-reruns-20260401/s3-9/pr-bundle.zip)
- Fresh `SSM.7` create response: [create.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260331T201302Z-all-groups-pr-bundle-live/fresh-reruns-20260401/ssm-7/create.json)
- Fresh `SSM.7` ZIP: [pr-bundle.zip](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260331T201302Z-all-groups-pr-bundle-live/fresh-reruns-20260401/ssm-7/pr-bundle.zip)
