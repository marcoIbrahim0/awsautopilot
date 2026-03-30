# Final Summary

## Scope

- Date: March 25, 2026 UTC
- Account: `696505809372`
- Deployed backend image: `20260325T160938Z`
- Frontend/API: `https://ocypheris.com` / `https://api.ocypheris.com`
- Families:
  - `S3.13 -> S3.11` (`s3_bucket_lifecycle_configuration`)
  - `S3.5` (`s3_bucket_require_ssl`)

## Result

- `S3.11` — PASS on the deployed stack.
  - The live grouped page loaded correctly and the deployed risk-ack retry path returned the expected duplicate/no-change response instead of a broken create flow.
  - The latest live-callback bundle `pr-bundle-14cbe174-7e4c-4013-9ae4-3e84b014509a.zip` was downloaded from the live page and executed locally with `AWS_PROFILE=test28-root AWS_REGION=eu-north-1`.
  - The bundle completed `12/12` executable action folders successfully.
  - The deployed callback path updated the existing grouped run `b4644d2d-a8e2-4d97-b8aa-3989c4d58730` to `finished_at=2026-03-25T16:44:07+00:00`.
  - Final truth remains:
    - `12` `run_successful`
    - `1` `metadata_only`
    - `0` `run_not_successful`
    - `0` `not_run_yet`

- `S3.5` — PASS on the deployed stack, with a live/runtime divergence from the localhost proof.
  - The live grouped page loaded correctly, displayed the risk-ack warnings, and the acknowledged retry created a fresh grouped run `791310a6-f60e-4fe7-bc2e-f257f0f4da71` with `POST /api/action-groups/aa087d9a-0547-4d76-bd51-f4eeb0005e83/bundle-run -> 201`.
  - The fresh remediation run `f885729d-0f94-48d7-b400-edf4b155afaf` generated a live-callback bundle with `4` executable members and `1` review-only member.
  - The downloaded live bundle `pr-bundle-f885729d-0f94-48d7-b400-edf4b155afaf.zip` executed locally with `AWS_PROFILE=test28-root AWS_REGION=eu-north-1`.
  - The bundle completed `4/4` executable action folders successfully.
  - The deployed callback path finalized grouped run `791310a6-f60e-4fe7-bc2e-f257f0f4da71` at `2026-03-25T16:53:57+00:00`.
  - Final truth changed from the earlier review-only state to:
    - `4` `run_successful`
    - `1` `metadata_only`
    - `0` `run_not_successful`
    - `0` `not_run_yet`

## Important Interpretation

- The localhost proof and the deployed proof diverged for `S3.5`.
  - Localhost current-head proof earlier on March 25 resolved that family as all review-only.
  - The deployed rerun generated an executable strict-deny bundle for `4` buckets plus `1` retained review-only member.
- The deployed product state should therefore be treated as the current truth for live SaaS on March 25, 2026:
  - `S3.11` is stable at `12 success + 1 review/manual`
  - `S3.5` is now `4 success + 1 review-only`

## Evidence References

- [health.json](../evidence/api/health.json)
- [ready.json](../evidence/api/ready.json)
- [s3_11_group_detail_after_live_rerun.json](../evidence/api/s3_11_group_detail_after_live_rerun.json)
- [s3_11_latest_run_after_live_rerun.json](../evidence/api/s3_11_latest_run_after_live_rerun.json)
- [s3_5_group_detail_after_live_rerun.json](../evidence/api/s3_5_group_detail_after_live_rerun.json)
- [s3_5_latest_run_after_live_rerun.json](../evidence/api/s3_5_latest_run_after_live_rerun.json)
