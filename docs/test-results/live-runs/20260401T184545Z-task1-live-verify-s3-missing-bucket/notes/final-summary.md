# Task 1 Live Verification

## Scope

This run tested the April 1, 2026 current-head Task 1 implementation against the real customer AWS account for one of the exact retained deleted-bucket failures from the earlier rerun package:

- Control: `S3.15`
- Action type: `s3_bucket_encryption_kms`
- Strategy: `s3_enable_sse_kms_guided`
- Account: `696505809372`
- Region: `eu-north-1`
- Deleted bucket replay target: `phase2-wi1-lifecycle-696505809372-20260329004157`

Related retained handoff:

- [Failed executable bundle fix handoff on April 1, 2026 UTC](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T022058Z-rerun-2-stream/notes/failed-bundles-fix-handoff.md)

## What was exercised

1. Attempted a scoped live recompute for tenant `9f7616d8-af04-43ca-99cd-713625357b70`, account `696505809372`, region `eu-north-1`.
2. Replayed the exact deleted bucket through current-head runtime selection and PR-bundle generation.
3. Generated and retained the Terraform PR bundle under this run folder.
4. Tried to execute the generated bundle against the live customer mutation profile immediately after confirming the bucket is still absent.

## Retained evidence

- [runtime_signals.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T184545Z-task1-live-verify-s3-missing-bucket/runtime_signals.json)
- [resolved_inputs.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T184545Z-task1-live-verify-s3-missing-bucket/resolved_inputs.json)
- [resolution.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T184545Z-task1-live-verify-s3-missing-bucket/resolution.json)
- [risk_snapshot.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T184545Z-task1-live-verify-s3-missing-bucket/risk_snapshot.json)
- [bundle_metadata.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T184545Z-task1-live-verify-s3-missing-bucket/bundle_metadata.json)
- [pr-bundle.zip](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T184545Z-task1-live-verify-s3-missing-bucket/pr-bundle.zip)
- [summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T184545Z-task1-live-verify-s3-missing-bucket/summary.json)

## Observed live outcome

- The deleted bucket still does not exist from the customer execution context.
- Current-head runtime did not mark the bucket as missing.
- Current-head runtime emitted `s3_target_bucket_probe_error` instead:
  - `Target bucket existence could not be verified because ReadRole runtime probe is unavailable.`
- Resolver output stayed on the existing-bucket branch:
  - `profile_id = s3_enable_sse_kms_guided`
  - `create_bucket_if_missing = false`
- The generated Terraform bundle therefore defaulted to the non-create path for the deleted bucket target.
- The attempted live Terraform execution then failed before proving the new branch:
  - `Access denied when assuming role arn:aws:iam::696505809372:role/SecurityAutopilotReadRole`

## Additional source inspection from this run

The live run exposed a second issue in the generated S3 create-if-missing Terraform for `S3.15`:

- [backend/services/pr_bundle.py:4099](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py#L4099)
- [backend/services/pr_bundle.py:4101](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py#L4101)

The generated resource `aws_s3_bucket_server_side_encryption_configuration.security_autopilot` depends on `aws_s3_bucket_server_side_encryption_configuration.target_bucket`, which is not declared. The same pattern also appears in the lifecycle generator:

- [backend/services/pr_bundle.py:3702](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py#L3702)
- [backend/services/pr_bundle.py:3704](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/pr_bundle.py#L3704)

## Verdict

`FAIL`

Task 1 is not yet successful on the live path tested here.

The missing-bucket preflight did not actually drive the live run onto the new create-if-missing branch because the runtime probe failed closed when the ReadRole session was unavailable:

- [backend/services/remediation_runtime_checks.py:267](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_runtime_checks.py#L267)
- [backend/services/remediation_runtime_checks.py:269](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/remediation_runtime_checks.py#L269)

As a result, the retained live replay proves:

1. The exact deleted bucket is still a truthful missing-target case.
2. Current head still resolves that case to `create_bucket_if_missing=false` when the ReadRole probe is unavailable.
3. The generated `S3.15` create-if-missing Terraform also still needs dependency wiring repair before a clean live rerun.

## Required follow-up

1. Change the runtime/resolver behavior so ReadRole-unavailable missing-target cases do not silently remain executable on the existing-bucket branch.
2. Fix the generated create-if-missing Terraform dependency target for at least `S3.15` and `S3.11`.
3. Re-run this same deleted-bucket live replay and retain:
   - pre-apply missing proof,
   - post-apply bucket existence proof,
   - destroy proof,
   - post-destroy missing proof.
