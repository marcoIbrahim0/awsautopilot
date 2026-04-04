# S3.2 production-ready grouped rerun

Status: `PASS` on April 2, 2026 UTC.

This retained package is the authoritative production-ready proof for the remaining live `S3.2` grouped edge case on action group `9200b6d5-b209-443f-9d78-28a4e60f6fb1`.

It proves all of the following on a fresh April 2, 2026 UTC grouped rerun after deploying the repo-side callback precision fix:

- the old website bucket blocker `da0d429e-6f16-461e-be2f-09ea7997e30a` is downgraded truthfully to `manual_guidance_only` before execution
- the real affected customer action `1dc66e7e-efe9-4fd6-9335-3197211b289f` remains executable and finishes `success`
- grouped callback persistence now preserves exact per-action truth instead of flattening executable members to coarse `bundle_runner_failed`
- the final group run finishes through `bundle_callback` with `31` executable `success` results and `2` non-executable metadata-only results

The earlier package [20260402T182613Z-s32-website-bpa-downgrade-rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T182613Z-s32-website-bpa-downgrade-rerun/README.md) remains the direct predecessor that closed the website-policy/BPA product bug but still reflected pre-redeploy callback flattening and unrelated AWS endpoint instability.

Primary retained summary:

- [notes/final-summary.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/notes/final-summary.md)

Key evidence:

- [api/create-group-run-request.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/api/create-group-run-request.json)
- [api/create-group-run-response.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/api/create-group-run-response.json)
- [api/group-run-before-local-apply.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/api/group-run-before-local-apply.json)
- [api/group-run-after-local-apply.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/api/group-run-after-local-apply.json)
- [api/remediation-run-before-local-apply.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/api/remediation-run-before-local-apply.json)
- [api/remediation-run-after-local-apply.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/api/remediation-run-after-local-apply.json)
- [api/callback-finished-response.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/api/callback-finished-response.json)
- [bundle/pr-bundle.zip](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/bundle/pr-bundle.zip)
- [bundle/extracted/manual_guidance/actions/02-arn-aws-s3-arch1-bucket-website-a1-696505809372--da0d429e/decision.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/bundle/extracted/manual_guidance/actions/02-arn-aws-s3-arch1-bucket-website-a1-696505809372--da0d429e/decision.json)
- [bundle/extracted/executable/actions/06-arn-aws-s3-security-autopilot-dev-serverless-src-1dc66e7e/decision.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/bundle/extracted/executable/actions/06-arn-aws-s3-security-autopilot-dev-serverless-src-1dc66e7e/decision.json)
- [recompute/recompute-result.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/recompute/recompute-result.json)
- [apply/run_tail.stdout.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T192426Z-s32-production-ready-rerun/apply/run_tail.stdout.log)
