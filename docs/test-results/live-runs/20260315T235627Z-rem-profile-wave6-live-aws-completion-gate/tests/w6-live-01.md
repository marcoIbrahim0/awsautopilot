# Test 01 - EC2.53 executable profile branch

- Wave: `Wave 6`
- Date (UTC): `2026-03-16T00:10:00Z`
- Tester: `Codex`
- Backend URL: `http://127.0.0.1:18020`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`

## Preconditions

- Ingest completed with `1169` updated findings.
- Action group `5ec0ef59-9ceb-40de-945a-eaf89b9fd78b` existed for `EC2.53`.
- Executable candidate action: `fb98ee94-f68b-41c0-84af-64afbbb014b4`
- Manual candidate action: `baa158fa-53f5-4a61-a226-e25779c49fa7`

## Steps Executed

1. Reviewed `EC2.53` group detail and both standalone previews.
2. Generated the supported customer-run grouped PR bundle.
3. Inspected `bundle_manifest.json`, `decision_log.md`, `finding_coverage.json`, `README_GROUP.txt`, and `run_all.sh`.
4. Compared standalone executable preview output with grouped executable contract output.

## Key Evidence

- Standalone executable preview: [`../evidence/api/w6-live-01-ec253-exec-preview.json`](../evidence/api/w6-live-01-ec253-exec-preview.json)
- Standalone manual preview: [`../evidence/api/w6-live-02-ec253-manual-preview.json`](../evidence/api/w6-live-02-ec253-manual-preview.json)
- Group bundle contract check: [`../evidence/api/w6-live-01-ec253-bundle-contract-check.json`](../evidence/api/w6-live-01-ec253-bundle-contract-check.json)
- Group bundle tree: [`../evidence/bundles/w6-live-01-ec253-group-tree.txt`](../evidence/bundles/w6-live-01-ec253-group-tree.txt)
- Group runs snapshot: [`../evidence/api/w6-live-01-ec253-group-runs.json`](../evidence/api/w6-live-01-ec253-group-runs.json)

## Assertions

- Standalone preview resolved `close_and_revoke` as `deterministic_bundle`.
- The supported grouped customer-run bundle downgraded that same action to `review_required_bundle`.
- `runnable_action_count` was `0`, so no truthful supported-path executable proof could be produced.
- The manual branch stayed truthful and non-executable.

## Result

- Status: `FAIL`
- Severity: `BLOCKING`
- Tracker mapping: `W6-LIVE-01`

## Notes

- This is a supported-path contract mismatch, not a missing-data blocker.
