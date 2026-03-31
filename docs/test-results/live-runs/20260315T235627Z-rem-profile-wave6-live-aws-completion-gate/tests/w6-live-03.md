# Test 03 - IAM.4 additive metadata and authority boundary

- Wave: `Wave 6`
- Date (UTC): `2026-03-16T13:01:00Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18021` for authoritative root-key execution, `http://127.0.0.1:18021` for generic IAM.4 metadata checks
- AWS Account: `696505809372`
- Region(s): `eu-north-1`

## Preconditions

- Generic IAM.4 action: `6d495cf7-358b-45a6-9dd0-d047adc50445`
- Root access key present before the test: `<REDACTED_AWS_ACCESS_KEY_ID>` (`Active`)
- Root MFA enabled before the test: `AccountMFAEnabled = 1`

## Steps Executed

1. Queried generic IAM.4 remediation options and preview.
2. Confirmed both generic surfaces stayed metadata-only and pointed to ``/api/root-key-remediation-runs`` as the sole execution authority.
3. Started a dedicated API instance on `127.0.0.1:18021` with `AWS_PROFILE=test28-root` so the authoritative route used isolated-account root credentials.
4. Created root-key remediation run `20543195-f548-4c68-ba70-414729357535`.
5. Called the authoritative `disable` transition.
6. Queried run detail, artifact metadata, and live access-key state after the disable attempt.

## Key Evidence

- Generic options: [`../evidence/api/w6-live-03-iam4-options.json`](../evidence/api/w6-live-03-iam4-options.json)
- Generic preview: [`../evidence/api/w6-live-03-iam4-preview.json`](../evidence/api/w6-live-03-iam4-preview.json)
- Create request/response: [`../evidence/api/w6-live-03-iam4-create-request.json`](../evidence/api/w6-live-03-iam4-create-request.json), [`../evidence/api/w6-live-03-iam4-create-response.json`](../evidence/api/w6-live-03-iam4-create-response.json)
- Disable response: [`../evidence/api/w6-live-03-iam4-disable-response.json`](../evidence/api/w6-live-03-iam4-disable-response.json)
- Run detail: [`../evidence/api/w6-live-03-iam4-run-detail.json`](../evidence/api/w6-live-03-iam4-run-detail.json)
- Stored artifact metadata: [`../evidence/api/w6-live-03-iam4-artifact-metadata.tsv`](../evidence/api/w6-live-03-iam4-artifact-metadata.tsv)
- Root key pre/post state: [`../evidence/aws/w6-live-03-iam4-pre-list-access-keys.json`](../evidence/aws/w6-live-03-iam4-pre-list-access-keys.json), [`../evidence/aws/w6-live-03-iam4-post-list-access-keys.json`](../evidence/aws/w6-live-03-iam4-post-list-access-keys.json)

## Assertions

- Generic IAM.4 routes remained additive metadata only and did not expose a generic executable path.
- The authoritative route created the live run and advanced it to `migration`.
- The live disable transition moved the run to `needs_attention` with stored reason `self_cutoff_guard_not_guaranteed:observer_credentials_overlap_with_mutation_target`.
- The root access key remained `Active`, so no truthful executable IAM.4 proof was produced.

## Result

- Status: `FAIL`
- Severity: `BLOCKING`
- Tracker mapping: `W6-LIVE-03`

## Notes

- No IAM root-key mutation occurred in this run.
