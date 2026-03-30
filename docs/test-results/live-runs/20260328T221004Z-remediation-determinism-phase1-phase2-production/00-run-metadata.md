# Run Metadata

## Identity And Scope

- Run ID: `20260328T221004Z-remediation-determinism-phase1-phase2-production`
- Created at (UTC): `2026-03-28T22:10:04Z`
- Completed at (UTC): `2026-03-28T23:12:23Z`
- Branch: `master`
- Commit: `481b5a00f8ec00f26174d20350e2bf740e5d856e`
- Frontend base: `https://ocypheris.com`
- API base: `https://api.ocypheris.com`
- Tenant: `Marco`
- Tenant ID: `e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`
- AWS account: `696505809372`
- AWS region: `eu-north-1`
- AWS profile used for live apply proof: `test28-root`
- Terraform mirror config: `/tmp/terraformrc-codex`

## Intent

Finish the Phase 2 production-only live gate on the real production surface and retain one final evidence package for:

- `WI-1` S3.11 captured additive lifecycle merge
- `WI-2` EC2.53 `ssm_only`
- `WI-8` EC2.53 `bastion_sg_reference`
- one grouped mixed-tier Phase 2 production run

Phase 1 was retained context only:

- `WI-7` is `WAIVED / DEFERRED`
- `WI-13` and `WI-14` are already proven live
- Gate 0 freshness repair is already proven live
- `WI-12` and the earlier retained post-apply lag remain open blockers

## Local Gate 2A Results

The exact March 28, 2026 Phase 2 local gate reran unchanged and passed:

- `01.log`: `10 passed, 31 deselected`
- `02.log`: `11 passed, 32 deselected`
- `03.log`: `25 passed, 134 deselected`
- `04.log`: `7 passed, 114 deselected`
- `05.log`: `3 passed, 20 deselected`
- `06.log`: `1 passed, 13 deselected`
- `07.log`: `3 passed, 47 deselected`
- `08.log`: `12 passed, 12 deselected`

Raw transcripts live under [local-gate/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/local-gate).

## Production Session Facts

- `/health` and `/ready` were both green during preflight.
- `/api/auth/me` and `/api/aws/accounts` matched the expected tenant/account context.
- Initial remediation settings were:
  - `sg_access_path_preference: null`
  - `approved_bastion_security_group_ids: []`
- For `WI-8`, remediation settings were temporarily patched to:
  - `sg_access_path_preference: bastion_sg_reference`
  - `approved_bastion_security_group_ids: ["sg-085d69a76707542b2"]`
- Those remediation settings were restored to their original values at the end of the run.

## Final Decisions

- Gate 2A local regression: `PASS`
- `WI-1`: `BLOCKED`
- `WI-2`: `PASS`
- `WI-8`: `PASS`
- Grouped mixed-tier Phase 2 proof: `PASS`
- Phase 2 overall: `BLOCKED`
- Phase 1 + Phase 2 overall: `NO-GO`
