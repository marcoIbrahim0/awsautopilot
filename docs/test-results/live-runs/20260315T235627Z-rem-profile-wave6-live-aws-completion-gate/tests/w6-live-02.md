# Test 02 - EC2.53 downgraded profile branch

- Wave: `Wave 6`
- Date (UTC): `2026-03-16T00:11:00Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18020`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`

## Preconditions

- Action `baa158fa-53f5-4a61-a226-e25779c49fa7` existed in `EC2.53`.

## Steps Executed

1. Requested standalone remediation preview for the non-revoking branch.
2. Confirmed the branch stayed manual/non-executable.
3. Cross-checked the grouped bundle output so the downgrade branch remained truthful in the supported customer-run model.

## Key Evidence

- Manual preview: [`../evidence/api/w6-live-02-ec253-manual-preview.json`](../evidence/api/w6-live-02-ec253-manual-preview.json)
- Grouped manifest: [`../evidence/bundles/w6-live-01-ec253-group/bundle_manifest.json`](../evidence/bundles/w6-live-01-ec253-group/bundle_manifest.json)

## Assertions

- `ssm_only` stayed `manual_guidance_only`.
- No runnable Terraform was emitted for the downgraded branch.
- The downgrade/manual proof is truthful even though the family failed its executable proof.

## Result

- Status: `PASS`
- Severity: `N/A`
- Tracker mapping: `W6-LIVE-02`
