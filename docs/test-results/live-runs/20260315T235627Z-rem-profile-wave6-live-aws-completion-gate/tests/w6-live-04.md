# Test 04 - S3.2 executable and manual-fallback branches

- Wave: `Wave 6`
- Date (UTC): `2026-03-16T00:18:00Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18020`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`

## Preconditions

- Action group `43d8b7e5-6cd5-4d31-915e-f22fc49ebd08`
- Executable action `638c6b43-32ab-4104-a1da-29be5cd9a35a`
- Manual action `4b9462e5-2391-4d1d-9d8f-425e124ac9cf`
- Retained bucket under executable proof: `security-autopilot-w6-envready-s315-exec-696505809372`

## Steps Executed

1. Reviewed executable and manual previews for the grouped family.
2. Created the grouped bundle, hit the expected risk-acknowledgement gate, and re-ran with acknowledgement.
3. Inspected the grouped manifest files and executed the bundle manually with `AWS_PROFILE=test28-root`.
4. Verified the executable bucket public-access-block state changed on AWS.
5. Ran cleanup and restored the exact pre-state with explicit AWS CLI because bundle destroy removed the public-access-block object.
6. Verified the manual/fallback branch stayed non-executable.

## Key Evidence

- Executable preview: [`../evidence/api/w6-live-04-s32-exec-preview.json`](../evidence/api/w6-live-04-s32-exec-preview.json)
- Manual preview: [`../evidence/api/w6-live-04-s32-manual-preview.json`](../evidence/api/w6-live-04-s32-manual-preview.json)
- Group bundle contract: [`../evidence/api/w6-live-04-s32-bundle-contract-check.json`](../evidence/api/w6-live-04-s32-bundle-contract-check.json)
- Apply log: [`../evidence/bundles/w6-live-04-s32-group/run_all-apply.log`](../evidence/bundles/w6-live-04-s32-group/run_all-apply.log)
- Pre/post/rollback AWS state: [`../evidence/aws/w6-live-04-s32-pre-public-access-block.json`](../evidence/aws/w6-live-04-s32-pre-public-access-block.json), [`../evidence/aws/w6-live-04-s32-post-public-access-block.json`](../evidence/aws/w6-live-04-s32-post-public-access-block.json), [`../evidence/aws/w6-live-04-s32-rollback-public-access-block.json`](../evidence/aws/w6-live-04-s32-rollback-public-access-block.json)

## Assertions

- The executable branch was truthful and changed AWS state.
- The downgrade/manual branch remained truthful and non-executable.
- Exact bucket state was restored after the test.
- Group callback finalization was still broken, but that regression is tracked separately in `W6-LIVE-11`.

## Result

- Status: `PASS`
- Severity: `N/A`
- Tracker mapping: `W6-LIVE-04`
