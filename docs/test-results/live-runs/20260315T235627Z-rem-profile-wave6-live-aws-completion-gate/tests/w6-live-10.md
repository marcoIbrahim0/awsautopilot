# Test 10 - Config.1 migration boundaries

- Wave: `Wave 6`
- Date (UTC): `2026-03-16T00:55:00Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18020`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`

## Preconditions

- Executable action `0e4108d7-3985-416d-b6cd-7659e8e45113`
- Pre-existing default AWS Config recorder existed and was already recording.
- Pre-existing default delivery channel targeted `config-bucket-696505809372`.

## Steps Executed

1. Reviewed executable and manual previews for `Config.1`.
2. Captured pre-state for recorder, recorder status, delivery channel, and retained config-bucket policy.
3. Executed the grouped bundle manually with `AWS_PROFILE=test28-root`.
4. Verified the default delivery channel moved to `security-autopilot-w6-envready-config-696505809372`.
5. Ran the documented rollback sequence.
6. Observed that rollback deleted the default recorder and delivery channel instead of restoring them.
7. Manually recreated the default recorder and delivery channel from the captured pre-state and restarted recording.

## Key Evidence

- Executable preview: [`../evidence/api/w6-live-10-config-exec-preview.json`](../evidence/api/w6-live-10-config-exec-preview.json)
- Manual preview: [`../evidence/api/w6-live-10-config-manual-preview.json`](../evidence/api/w6-live-10-config-manual-preview.json)
- Apply log: [`../evidence/bundles/w6-live-10-config-group/run_all-apply.log`](../evidence/bundles/w6-live-10-config-group/run_all-apply.log)
- Pre-state: [`../evidence/aws/w6-live-10-config-pre-recorders.json`](../evidence/aws/w6-live-10-config-pre-recorders.json), [`../evidence/aws/w6-live-10-config-pre-delivery-channels.json`](../evidence/aws/w6-live-10-config-pre-delivery-channels.json)
- Broken rollback state: [`../evidence/aws/w6-live-10-config-rollback-recorders.json`](../evidence/aws/w6-live-10-config-rollback-recorders.json), [`../evidence/aws/w6-live-10-config-rollback-delivery-channels.json`](../evidence/aws/w6-live-10-config-rollback-delivery-channels.json)
- Manual recovery: [`../evidence/aws/w6-live-10-config-cleanup-recorders.json`](../evidence/aws/w6-live-10-config-cleanup-recorders.json), [`../evidence/aws/w6-live-10-config-cleanup-delivery-channels.json`](../evidence/aws/w6-live-10-config-cleanup-delivery-channels.json), [`../evidence/aws/w6-live-10-config-cleanup-recorder-status-final.json`](../evidence/aws/w6-live-10-config-cleanup-recorder-status-final.json)

## Assertions

- The executable branch was truthful and changed AWS state.
- The downgrade/manual branch was truthful and non-executable.
- The bundle/manual rollback was not safe: it removed pre-existing Config state instead of restoring it.
- The test account was manually repaired to exact pre-state after the failed rollback.

## Result

- Status: `FAIL`
- Severity: `HIGH`
- Tracker mapping: `W6-LIVE-10`
