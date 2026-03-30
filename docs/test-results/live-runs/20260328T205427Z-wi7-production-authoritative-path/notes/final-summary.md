# Final Summary

## Outcome

- Run ID: `20260328T205427Z-wi7-production-authoritative-path`
- Final decision: `WAIVED`
- Required surface: `https://api.ocypheris.com`

## What This Run Proved

- `WI-7` fallback logic is still implemented in the current code path.
- The configured primary Neon endpoint was not usable during this run because it returned a data-transfer quota error.
- Scoped production recompute selected the configured fallback database after that primary probe failure.
- The live API row for action `19a9b0f0-de47-4a5b-982f-8d3c876c2064` matched the fallback DB row during this investigation.

## Truthful Seed Attempt

- Verified `AWS_PROFILE=test28-root` resolved to canary account `696505809372`.
- Created temporary bucket `sa-wi7-seed-696505809372-20260328205857`.
- Triggered authenticated production ingest and waited through `8` retained polls.
- Re-ran scoped recompute after each poll.
- Final ingest completed with `updated_findings_count=20`.
- Production still returned `0` findings and `0` actions for the seed bucket ARN on the live API.
- Deleted the temporary bucket after the attempt.

## Why WI-7 Is Waived / Deferred

1. Current production data and recompute behavior did not emit any truthful stale-`target_id` S3-family candidate.
2. The bounded AWS-side seed attempt also failed to surface one.
3. Synthetic database mutation is outside the production-only signoff contract.
4. The retained evidence therefore supports `implemented but not live-provable`, not `PASS` and not `unfixed`.
