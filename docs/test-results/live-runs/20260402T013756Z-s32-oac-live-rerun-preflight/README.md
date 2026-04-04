# S3.2 grouped rerun with CloudFront/OAC preflight removal of Terraform `external`

- Final outcome: `FAIL`
- Fresh group run: `d92861be-cbb7-4508-8f3e-2ddaf87df362`
- Fresh remediation run: `f124f569-9391-4f74-85df-23e64b83fa92`
- Live scope: account `696505809372`, region `eu-north-1`, action group `9200b6d5-b209-443f-9d78-28a4e60f6fb1`
- Real affected action: `1dc66e7e-efe9-4fd6-9335-3197211b289f`

## What this package proves

- The old `OriginAccessControlAlreadyExists` blocker did not reproduce on the fresh rerun.
- The real affected customer action became executable and completed successfully through the new CloudFront/OAC reuse preflight path.
- The grouped rerun still ended terminal `failed` because one different executable action hit a new bounded blocker:
  - `PutBucketPolicy` on `arch1-bucket-website-a1-696505809372-eu-north-1`
  - rejected with `403 AccessDenied`
  - reason: S3 Block Public Access `BlockPublicPolicy` prevented the generated policy from being accepted as written

## Key files

- [notes/final-summary.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/notes/final-summary.md)
- [notes/bundle-inspection.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/notes/bundle-inspection.md)
- [notes/deploy-summary.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/notes/deploy-summary.md)
- [apply/run_all.stdout.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/apply/run_all.stdout.log)
- [apply/run_all.tail.final.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/apply/run_all.tail.final.log)
- [api/group-run-terminal.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/api/group-run-terminal.json)
- [api/group-run-results-terminal.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/api/group-run-results-terminal.json)
- [bundle/extracted/executable/actions/05-arn-aws-s3-security-autopilot-dev-serverless-src-1dc66e7e/decision.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/bundle/extracted/executable/actions/05-arn-aws-s3-security-autopilot-dev-serverless-src-1dc66e7e/decision.json)
- [bundle/extracted/executable/actions/23-arn-aws-s3-arch1-bucket-website-a1-696505809372--da0d429e/decision.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/bundle/extracted/executable/actions/23-arn-aws-s3-arch1-bucket-website-a1-696505809372--da0d429e/decision.json)

## Important interpretation note

The server-side group run status is truthfully `failed`, but the persisted per-action `action_group_run_results` rows flatten every executable member to `bundle_runner_failed` once `run_actions.sh` exits non-zero. The local retained runner log is therefore the authoritative per-folder breakdown for this run, and it shows `31/32` executable folders succeeded with only one concrete apply failure.
