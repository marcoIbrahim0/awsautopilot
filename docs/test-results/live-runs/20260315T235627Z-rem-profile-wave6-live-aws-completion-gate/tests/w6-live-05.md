# Test 05 - S3.5 preservation-evidence gating

- Wave: `Wave 6`
- Date (UTC): `2026-03-16T00:21:00Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18020`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`

## Preconditions

- Executable candidate action `38a640b1-62eb-4deb-bd64-2d8aeb249982`
- Manual/review account action `0242a107-32fa-44f3-bca8-820d14c20aff`

## Steps Executed

1. Reviewed executable and review/manual previews for `S3.5`.
2. Attempted to collapse the family with an exception-only override and confirmed it failed closed.
3. Generated the whole-family grouped bundle and inspected the grouped manifest files.
4. Confirmed the bundle contained both executable and review-only outputs.

## Key Evidence

- Executable preview: [`../evidence/api/w6-live-05-s35-exec-preview.json`](../evidence/api/w6-live-05-s35-exec-preview.json)
- Manual/review preview: [`../evidence/api/w6-live-05-s35-manual-preview.json`](../evidence/api/w6-live-05-s35-manual-preview.json)
- Failed exception-only create: [`../evidence/api/w6-live-05-s35-group-create-response.json`](../evidence/api/w6-live-05-s35-group-create-response.json)
- Successful grouped bundle contract: [`../evidence/api/w6-live-05-s35-bundle-contract-check.json`](../evidence/api/w6-live-05-s35-bundle-contract-check.json)

## Assertions

- Preservation-evidence gating failed closed for the exception-only strategy path.
- The family produced a truthful mixed executable-plus-review bundle contract.
- No live executable apply plus rollback was completed in this final gate run.

## Result

- Status: `PARTIAL`
- Severity: `BLOCKING`
- Tracker mapping: `W6-LIVE-05`
