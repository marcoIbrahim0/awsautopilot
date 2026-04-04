# S3.2 website-policy/BPA grouped rerun

Status: `PARTIAL` on April 2, 2026 UTC.

This retained package proves the remaining live `S3.2` website-policy plus `BlockPublicPolicy` edge case is closed truthfully for action group `9200b6d5-b209-443f-9d78-28a4e60f6fb1`:

- the old website bucket blocker `da0d429e-6f16-461e-be2f-09ea7997e30a` is no longer emitted as executable Terraform
- the real affected customer action `1dc66e7e-efe9-4fd6-9335-3197211b289f` remains executable

The same retained rerun also exposed two separate follow-ons:

- transient live AWS endpoint/DNS failures caused `3/31` executable folders to fail locally
- the deployed grouped callback wrapper still flattened executable results to coarse `bundle_runner_failed` rows once the bundle exited non-zero

The repo code now includes a narrow follow-on fix for that grouped callback persistence issue, but this package reflects the pre-redeploy live behavior.

Primary retained summary:

- [notes/final-summary.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T182613Z-s32-website-bpa-downgrade-rerun/notes/final-summary.md)

Key evidence:

- [api/create-group-run-request.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T182613Z-s32-website-bpa-downgrade-rerun/api/create-group-run-request.json)
- [api/create-group-run-response.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T182613Z-s32-website-bpa-downgrade-rerun/api/create-group-run-response.json)
- [api/remediation-run-before-local-apply.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T182613Z-s32-website-bpa-downgrade-rerun/api/remediation-run-before-local-apply.json)
- [api/group-run-after-local-apply.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T182613Z-s32-website-bpa-downgrade-rerun/api/group-run-after-local-apply.json)
- [bundle/pr-bundle.zip](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T182613Z-s32-website-bpa-downgrade-rerun/bundle/pr-bundle.zip)
- [bundle/extracted/manual_guidance/actions/02-arn-aws-s3-arch1-bucket-website-a1-696505809372--da0d429e/decision.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T182613Z-s32-website-bpa-downgrade-rerun/bundle/extracted/manual_guidance/actions/02-arn-aws-s3-arch1-bucket-website-a1-696505809372--da0d429e/decision.json)
- [bundle/extracted/executable/actions/06-arn-aws-s3-security-autopilot-dev-serverless-src-1dc66e7e/decision.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T182613Z-s32-website-bpa-downgrade-rerun/bundle/extracted/executable/actions/06-arn-aws-s3-security-autopilot-dev-serverless-src-1dc66e7e/decision.json)
- [apply/run_all.stdout.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T182613Z-s32-website-bpa-downgrade-rerun/apply/run_all.stdout.log)
- [apply/run_all.tail.final.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T182613Z-s32-website-bpa-downgrade-rerun/apply/run_all.tail.final.log)
- [recompute/recompute-result.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T182613Z-s32-website-bpa-downgrade-rerun/recompute/recompute-result.json)
