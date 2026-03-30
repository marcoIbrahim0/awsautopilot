# WI-7 Production Authoritative-Path Investigation

- Run ID: `20260328T205427Z-wi7-production-authoritative-path`
- Date (UTC): `2026-03-28`
- Scope: `WI-7` only
- Required live surface: `https://api.ocypheris.com`
- Tenant: `Marco` (`e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`)
- Canary account: `696505809372`
- Region: `eu-north-1`
- Outcome: `WAIVED`

## Summary

This retained run was the bounded authoritative-path follow-up for `WI-7`.

It confirmed three things:

- the landed `WI-7` fallback logic is still present in the current code path
- the current recompute path selected the configured fallback database after the primary Neon probe failed on quota
- one truthful AWS-side `S3.9` seed attempt plus authenticated production ingest and recompute still did not surface any S3-family action whose `resource_id` stayed bucket-truthful while `target_id` was stale or account-scoped

Under the production-only signoff contract, that means `WI-7` is not a truthful `PASS`, but it is also no longer honest to describe it as an unfixed runtime defect. The retained decision for `WI-7` is `WAIVED / DEFERRED`: implemented and test-covered, but not live-provable on the current production data path.

## What This Run Proved

- Current code shape still normalizes modern S3 action creation around bucket-truthful `resource_id`, and the shipped fallback remains in the runtime and bundle paths:
  - runtime probe fallback in `backend/services/remediation_runtime_checks.py`
  - PR-bundle bucket fallback in `backend/services/pr_bundle.py`
  - recompute target construction from `resource_id` in `backend/services/action_engine.py`
- The configured primary Neon endpoint was not usable at investigation time:
  - direct probe returned `ERROR: Your project has exceeded the data transfer quota`
- The scoped production recompute path then selected the configured fallback database:
  - retained stderr shows `database_failover selected source=fallback ... after primary probe failure`
- The live production API row for action `19a9b0f0-de47-4a5b-982f-8d3c876c2064` matched the fallback row during this run:
  - `target_id=696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001|S3.9`
  - `resource_id=arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001`
- One bounded truthful seed was attempted on the canary account with real AWS mutation:
  - verified `AWS_PROFILE=test28-root` resolved to account `696505809372`
  - created temporary bucket `sa-wi7-seed-696505809372-20260328205857`
  - triggered authenticated production ingest
  - waited through `8` ingest polls and reran scoped recompute after each poll
  - final ingest completed with `updated_findings_count=20`
  - no production finding or action ever surfaced for the seed bucket ARN
  - the temporary bucket was deleted after the attempt

## Decision

- `WI-7`: `WAIVED / DEFERRED`
  - implemented in code
  - bounded truthful production seed attempt completed
  - no truthful stale-`target_id` candidate surfaced on the real production path
  - synthetic DB mutation remains out of contract

This package is specific to `WI-7`. It does not close overall Phase 1 by itself because `WI-12` and the earlier retained post-apply finding/action lag still remain open.

## Key Artifacts

- [Structured summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/summary.json)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/notes/final-summary.md)
- [Production login response](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/evidence/api/login-response.json)
- [Current live S3.9 action detail (`19a9...`)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/evidence/api/action-19a9-current.json)
- [Primary DB probe failure](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/evidence/db/primary-db-probe.stderr.txt)
- [Recompute fallback-selection proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/evidence/db/recompute-fallback-proof.stderr.txt)
- [Fallback/API S3-family comparison TSV](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/evidence/db/fallback-actions-open-s3-family-compare.tsv)
- [Canary root-account proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/evidence/aws/test28-root-sts.json)
- [Seed bucket create proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/evidence/aws/wi7-seed-bucket-create.json)
- [Seed ingest trigger](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/evidence/api/wi7-seed-ingest-trigger.json)
- [Final ingest-complete poll](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/evidence/api/wi7-seed-ingest-progress-8.json)
- [Final seed action query (`0` results)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/evidence/api/wi7-seed-actions-8.json)
- [Final seed finding query (`0` results)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/evidence/api/wi7-seed-findings-8.json)
- [Seed bucket delete proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/evidence/aws/wi7-seed-bucket-delete.json)
