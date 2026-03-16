# Test 09 - CloudTrail.1 migration boundaries

- Wave: `Wave 6`
- Date (UTC): `2026-03-16T00:25:00Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18020`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`

## Preconditions

- Executable action `0bd41810-447a-4b57-bd09-d729f291b4ad`
- Retained target bucket `security-autopilot-w6-envready-cloudtrail-696505809372`
- Manual/review case used intentionally bad tenant default bucket `config-bucket-696505809372`

## Steps Executed

1. Reviewed executable and manual previews for `CloudTrail.1`.
2. Generated the grouped bundle and inspected the grouped manifest files.
3. Verified pre-state: no trail existed.
4. Executed the bundle manually with `AWS_PROFILE=test28-root`.
5. Verified trail `security-autopilot-trail` existed after apply.
6. Destroyed the executable action folder and verified the trail was removed.

## Key Evidence

- Executable preview: [`../evidence/api/w6-live-09-cloudtrail-exec-preview.json`](../evidence/api/w6-live-09-cloudtrail-exec-preview.json)
- Manual preview: [`../evidence/api/w6-live-09-cloudtrail-manual-preview.json`](../evidence/api/w6-live-09-cloudtrail-manual-preview.json)
- Group contract: [`../evidence/api/w6-live-09-cloudtrail-bundle-contract-check.json`](../evidence/api/w6-live-09-cloudtrail-bundle-contract-check.json)
- Apply log: [`../evidence/bundles/w6-live-09-cloudtrail-group/run_all-apply.log`](../evidence/bundles/w6-live-09-cloudtrail-group/run_all-apply.log)
- Destroy log: [`../evidence/bundles/w6-live-09-cloudtrail-group/terraform-destroy.log`](../evidence/bundles/w6-live-09-cloudtrail-group/terraform-destroy.log)
- AWS state: [`../evidence/aws/w6-live-09-cloudtrail-pre-describe-trails.json`](../evidence/aws/w6-live-09-cloudtrail-pre-describe-trails.json), [`../evidence/aws/w6-live-09-cloudtrail-post-describe-trails.json`](../evidence/aws/w6-live-09-cloudtrail-post-describe-trails.json), [`../evidence/aws/w6-live-09-cloudtrail-rollback-describe-trails.json`](../evidence/aws/w6-live-09-cloudtrail-rollback-describe-trails.json)

## Assertions

- The executable CloudTrail branch was truthful and changed AWS state.
- The incompatible-default manual branch stayed `review_required_bundle`.
- Cleanup removed the trail and preserved the retained bucket policy.

## Result

- Status: `PASS`
- Severity: `N/A`
- Tracker mapping: `W6-LIVE-09`
