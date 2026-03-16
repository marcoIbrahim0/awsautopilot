# Test 11 - Cross-family regression and archived-SaaS boundary

- Wave: `Wave 6`
- Date (UTC): `2026-03-16T01:05:00Z`
- Tester: `Codex`
- Backend URL: `customer-run bundle callbacks embedded `run_all.sh` against local API URLs`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`

## Preconditions

- Grouped customer-run bundles were generated for `S3.2`, `S3.9`, `CloudTrail.1`, `Config.1`, `S3.11`, `S3.15`, and `EC2.53`.
- No archived public SaaS-managed execution route was used in this run.

## Steps Executed

1. Inspected grouped `run_all.sh` in multiple bundles.
2. Executed grouped bundles for `S3.2`, `S3.9`, `CloudTrail.1`, and `Config.1`.
3. Compared AWS-side success with group-run callback/finalization behavior.
4. Verified this run used only customer-run bundles and IAM.4 authoritative API execution, not archived SaaS-managed plan/apply routes.

## Key Evidence

- Broken grouped wrapper logs:
  - [`../evidence/bundles/w6-live-04-s32-group/run_all-apply.log`](../evidence/bundles/w6-live-04-s32-group/run_all-apply.log)
  - [`../evidence/bundles/w6-live-07-s39-group/run_all-apply.log`](../evidence/bundles/w6-live-07-s39-group/run_all-apply.log)
  - [`../evidence/bundles/w6-live-09-cloudtrail-group/run_all-apply.log`](../evidence/bundles/w6-live-09-cloudtrail-group/run_all-apply.log)
  - [`../evidence/bundles/w6-live-10-config-group/run_all-apply.log`](../evidence/bundles/w6-live-10-config-group/run_all-apply.log)
- Stale grouped run state after truthful apply: [`../evidence/api/w6-live-04-s32-group-runs.json`](../evidence/api/w6-live-04-s32-group-runs.json)
- Customer-run grouped manifests proving the supported path used in this run:
  - [`../evidence/bundles/w6-live-04-s32-group/bundle_manifest.json`](../evidence/bundles/w6-live-04-s32-group/bundle_manifest.json)
  - [`../evidence/bundles/w6-live-09-cloudtrail-group/bundle_manifest.json`](../evidence/bundles/w6-live-09-cloudtrail-group/bundle_manifest.json)

## Assertions

- Grouped `run_all.sh` is currently malformed on current `master`.
- The defect occurs in the supported customer-run bundle path, not an archived SaaS-managed execution path.
- Terraform can still mutate AWS successfully, but callback reporting is broken and grouped run finalization becomes unreliable.
- Because this regression sits in the supported execution model, it blocks any strict `Wave 6 complete` claim even for families that reached truthful AWS apply plus cleanup.

## Result

- Status: `FAIL`
- Severity: `HIGH`
- Tracker mapping: `W6-LIVE-11`
