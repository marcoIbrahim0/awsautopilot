# Live E2E Run Metadata

- Run ID: `20260326T025813Z-phase5-support-bucket-cluster-canary-blocked`
- Created at (UTC): `2026-03-26T02:58:13Z`
- Frontend URL: `https://ocypheris.com`
- Backend URL: `https://api.ocypheris.com`
- Phase 5 target controls: `Config.1`, `S3.9`, `CloudTrail.1`
- Default canary account: `029037611564`
- Default canary region: `eu-north-1`
- Local cluster validation result: `PASS`
- Live canary result: `BLOCKED`

## Local Validation Results

- Full cluster suite:
  `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_support_bucket.py tests/test_remediation_runtime_checks.py tests/test_remediation_profile_options_preview.py tests/test_remediation_runs_api.py tests/test_step7_components.py tests/test_remediation_profile_catalog.py`
  - result: `353 passed in 1.47s`
- Focused `Config.1` slice:
  - result: `16 passed`
- Focused `S3.9` slice:
  - result: `6 passed`
- Focused `CloudTrail.1` slice:
  - result: `8 passed`

## Live Rollout Blockers Observed On March 26, 2026

- Decrypted retained Chrome cookie bearer for `api.ocypheris.com`:
  - `GET /api/auth/me` -> `401 {"detail":"User not found"}`
- Browser login on `https://ocypheris.com/login`:
  - `maromaher54@gmail.com / <REDACTED_PASSWORD>` -> `Verify your email before signing in`
  - `marco.ibrahim@ocypheris.com / <REDACTED_PASSWORD>` -> `Login failed`
- Read-only production DB lookup for same-operator bearer minting:
  - blocked by Neon error `Your project has exceeded the data transfer quota. Upgrade your plan to increase limits.`
- Retained March 23, 2026 live `Valens` bearer from [login.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260323T190500Z-ssm7-cloudtrail1-live-e2e/evidence/api/login.json):
  - `GET /api/auth/me` -> `401 {"detail":"User not found"}`
