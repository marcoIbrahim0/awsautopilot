# WI-4 S3.5 Apply-Time Merge Canary

- Run ID: `20260328T021002Z-wi4-s35-apply-time-merge-canary`
- Date (UTC): `2026-03-28`
- Primary target attempted first: `https://ocypheris.com` / `https://api.ocypheris.com`
- Retained proof environment used: isolated current-head local API/worker at `http://127.0.0.1:18031` against real AWS account `696505809372` in `eu-north-1`
- Outcome: `PASS`
- WI-4 scope closed: `yes`

## Summary

This retained package closes WI-4 for its intended Terraform-only scope by proving the shipped S3.5 apply-time merge branch on a real AWS account where runtime bucket-policy capture fails concretely with `AccessDenied`.

The run used the documented fallback path from the completion plan. Production was attempted first, but the currently deployed production surface did not expose the WI-4 branch on the target S3.5 candidate, so the proof pivoted to an isolated current-head runtime connected to the same real AWS account. That fallback is within the approved WI-4 closure contract.

## What This Run Proved

- Single-run S3.5 preview/create stayed `deterministic_bundle` with:
  - `preservation_summary.apply_time_merge=true`
  - `merge_safe_policy_available=false`
  - `executable_policy_merge_allowed=true`
  - concrete capture failure reasoning tied to runtime `AccessDenied`
- The generated single-run ZIP omitted `terraform.auto.tfvars.json`, emitted `data "aws_s3_bucket_policy" "existing"`, and still shipped the capture/restore helper scripts plus rollback metadata.
- Local `terraform init`, `plan`, and `apply` succeeded against the real target bucket `security-autopilot-access-logs-696505809372-r221001` with `AWS_PROFILE=test28-root`.
- Single-run rollback restored the bucket policy exactly to the pre-apply three-statement policy.
- Grouped bundle generation kept the three bucket-scoped S3.5 members executable under `executable/actions` and kept the account-scoped S3.5 member metadata-only under `review_required/actions`.
- Executing the grouped bundle via `run_all.sh` succeeded and the callback finalized the group run with:
  - `3` executable successes
  - `1` metadata-only member
  - final group counters `run_successful=3`, `metadata_only=1`

## Non-Blocking Run Note

The grouped runner executes each action inside an isolated temporary Terraform workspace and cleans that workspace up after apply. Because of that, the execution-time `.s3-rollback` snapshots were not retained in the extracted grouped artifact after the run. WI-4 itself only required exact rollback proof for the single-run path, so this did not block closure, but the retained grouped restore for `r222018` and `r94854` used a functionally equivalent manual restore that removed only the managed `DenyInsecureTransport` statement added by the grouped apply.

## Rollout Decision

- WI-4 code + tests: complete
- WI-4 retained live proof: complete through the approved isolated-runtime fallback
- CloudFormation without captured policy JSON: still intentionally fail-closed
- Production deployment status: separate from WI-4 closure; the retained package proves current-head behavior, not that production had already been redeployed

## Key Artifacts

- [Run metadata](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/00-run-metadata.md)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/notes/final-summary.md)
- [Structured summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/summary.json)
- [Single-run deterministic preview/options proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/evidence/api/local-s35-r221001-options-principalarn.json)
- [Single-run final remediation run detail](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/evidence/api/local-s35-r221001-run-final-direct.json)
- [Single-run applied Terraform policy file proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/evidence/bundle/extracted/s3_bucket_require_ssl.tf)
- [Single-run rollback verification](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/evidence/terraform/12-single-run-restore-verification-summary.json)
- [Grouped run create response](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/evidence/api/local-s35-group-run-create.json)
- [Grouped remediation run detail](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/evidence/api/local-s35-group-remediation-run-1.json)
- [Grouped mixed-tier layout summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/evidence/grouped_bundle/group-layout-summary.json)
- [Grouped final group detail projection](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/evidence/api/local-s35-group-detail-final.json)
- [Grouped restore verification summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/evidence/grouped_bundle/logs/13-restore-verification-summary.json)
