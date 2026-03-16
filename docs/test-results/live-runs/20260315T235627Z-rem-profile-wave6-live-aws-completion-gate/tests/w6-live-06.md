# Test 06 - S3.11 preservation-evidence gating

- Wave: `Wave 6`
- Date (UTC): `2026-03-16T15:05:00Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18020`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`

## Preconditions

- Executable candidate action `1df0126d-d424-41cd-b05f-c3079742e4b4`
- Manual action `d6eb9cb9-3325-4a5e-a250-760c0026ff10`

## Steps Executed

1. Reviewed executable and manual previews for `S3.11`.
2. Generated the grouped bundle and inspected the grouped manifest files.
3. Captured per-bucket lifecycle pre-state for the executable buckets.
4. Started the grouped bundle with operator-owned credentials.
5. Stopped the attempt when Terraform remained in provider init and had not reached the first AWS mutation.

## Key Evidence

- Executable preview: [`../evidence/api/w6-live-06-s311-exec-preview.json`](../evidence/api/w6-live-06-s311-exec-preview.json)
- Manual preview: [`../evidence/api/w6-live-06-s311-manual-preview.json`](../evidence/api/w6-live-06-s311-manual-preview.json)
- Group bundle contract: [`../evidence/api/w6-live-06-s311-bundle-contract-check.json`](../evidence/api/w6-live-06-s311-bundle-contract-check.json)
- Pre-state capture: [`../evidence/aws/w6-live-06-s311-pre/`](../evidence/aws/w6-live-06-s311-pre/)
- Incomplete execution log: [`../evidence/bundles/w6-live-06-s311-group/run_all-apply.log`](../evidence/bundles/w6-live-06-s311-group/run_all-apply.log)

## Assertions

- The downgrade/manual branch is truthful and non-executable.
- The grouped executable contract exists and is bundle-backed.
- No truthful live executable proof was completed in this gate because execution was stopped before first mutation.

## Result

- Status: `PARTIAL`
- Severity: `BLOCKING`
- Tracker mapping: `W6-LIVE-06`

## Notes

- No target-account lifecycle configuration was intentionally changed during this aborted attempt.
