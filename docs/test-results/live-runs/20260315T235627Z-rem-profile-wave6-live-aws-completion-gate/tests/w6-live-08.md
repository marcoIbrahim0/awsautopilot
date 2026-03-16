# Test 08 - S3.15 AWS-managed vs customer-managed KMS branching

- Wave: `Wave 6`
- Date (UTC): `2026-03-16T00:24:00Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18020`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`

## Preconditions

- Executable action `080ad0ec-b379-4cb5-9f7a-aecdd997ab11`
- Manual/review action `31381d3c-04f9-4613-a897-ba95ddbdc0bd`
- Customer-managed key used in the review path: `arn:aws:kms:eu-north-1:696505809372:key/ef0cca31-8328-41e6-ab28-64cbedc1a44c`

## Steps Executed

1. Reviewed executable preview for the AWS-managed KMS branch.
2. Reviewed manual/review preview for the customer-managed KMS branch.
3. Generated and inspected the grouped bundle.
4. Confirmed the grouped customer-run bundle emitted `11` executable AWS-managed actions.

## Key Evidence

- Executable preview: [`../evidence/api/w6-live-08-s315-exec-preview.json`](../evidence/api/w6-live-08-s315-exec-preview.json)
- Manual preview: [`../evidence/api/w6-live-08-s315-manual-preview.json`](../evidence/api/w6-live-08-s315-manual-preview.json)
- Group bundle contract: [`../evidence/api/w6-live-08-s315-bundle-contract-check.json`](../evidence/api/w6-live-08-s315-bundle-contract-check.json)

## Assertions

- AWS-managed KMS stayed executable in the supported grouped bundle path.
- Customer-managed KMS stayed review-only and non-executable.
- No live executable apply plus rollback was completed in this final gate run.

## Result

- Status: `PARTIAL`
- Severity: `BLOCKING`
- Tracker mapping: `W6-LIVE-08`
