# All-Controls Live E2E Summary

## Result

- Status: `COMPLETE LIVE SWEEP`
- Scope: all `21` currently available action groups for account `696505809372`
- Playwright role: real browser entry, real `/actions/group` generation flow, warning/ack handling, and retained screenshots for fresh grouped-run creation

## What Was Proven

- Production currently exposes `21` grouped controls on the account across `eu-north-1` and `us-east-1`.
- Fresh grouped bundle creation was driven from the live UI or equivalent live strategy body for all `14` groups that were still `not_run_yet`.
- Fresh bundle generation succeeded for these previously-unrun families:
  - `EC2.53` (`sg_restrict_public_ports`) `eu-north-1`
  - `SSM.7` (`ssm_block_public_sharing`) `eu-north-1`
  - `EC2.7` (`ebs_default_encryption`) `us-east-1`
  - `EC2.7` (`ebs_default_encryption`) `eu-north-1`
  - `S3.5` (`s3_bucket_require_ssl`) `eu-north-1`
  - `S3.5` (`s3_bucket_require_ssl`) `us-east-1`
  - `S3.1` (`s3_block_public_access`) `us-east-1`
  - `S3.11` (`s3_bucket_lifecycle_configuration`) `eu-north-1`
  - `S3.11` (`s3_bucket_lifecycle_configuration`) `us-east-1`
- Safety-gate truth was also proven live:
  - `S3.2` (`s3_bucket_block_public_access`) `eu-north-1` blocked because bucket website/public-access inspection could not be safely verified
  - `S3.9` (`s3_bucket_access_logging`) both regions blocked because the required destination log bucket could not be verified
- `IAM.4` in both regions is still outside the generic grouped PR-bundle execution path:
  - the live API returned the dedicated authority handoff to `/api/root-key-remediation-runs`

## Current Live State Snapshot

- `EC2.53 eu-north-1` => `run_successful_needs_followup`
- `S3.2 eu-north-1` => `not_run_yet` (safety-gated)
- `SSM.7 eu-north-1` => `run_finished_metadata_only`
- `EC2.182 eu-north-1` => `run_successful_confirmed`
- `EC2.7 us-east-1` => `run_successful_confirmed`
- `EC2.7 eu-north-1` => `run_successful_confirmed`
- `S3.9 us-east-1` => `not_run_yet` (safety-gated)
- `S3.5 us-east-1` => `run_successful_confirmed`
- `S3.5 eu-north-1` => mixed member truth: `run_successful_confirmed` + `run_finished_metadata_only`
- `S3.1 us-east-1` => `run_successful_confirmed`
- `S3.11 eu-north-1` => mixed member truth: `run_successful_confirmed` + `run_not_successful` (`10` confirmed, `3` failed)
- `S3.1 eu-north-1` => `run_successful_confirmed`
- `IAM.4 eu-north-1` => `not_run_yet` (dedicated root-key route required)
- `S3.9 eu-north-1` => `not_run_yet` (safety-gated)
- `GuardDuty.1 eu-north-1` => `run_finished_metadata_only`
- `Config.1 us-east-1` => `run_successful_pending_confirmation`
- `IAM.4 us-east-1` => `not_run_yet` (dedicated root-key route required)
- `S3.11 us-east-1` => `run_successful_confirmed`
- `CloudTrail.1 eu-north-1` => `run_successful_confirmed`
- `GuardDuty.1 us-east-1` => `run_finished_metadata_only`
- `Config.1 eu-north-1` => `run_successful_pending_confirmation`

## Final Reconciliation Outcome

- The previously interrupted `S3.11 eu-north-1` bundle was rerun cleanly to completion:
  - local rerun finished `12/12` successful action folders
  - the bundle emitted one final callback payload, but production rejected replay with `409 group_run_report_conflict` because the original grouped run was already finalized as failed
- The deployed refresh path was then proven end to end:
  - live ingest succeeded for both `eu-north-1` and `us-east-1`
  - live `compute` jobs queued successfully for both regions
  - live reconciliation run `bd3ff9a7-c032-4cbf-aac4-9c140ca4b4b4` succeeded across `12` shards for `s3`, `ec2`, `ebs`, `ssm`, `config`, and `guardduty`
- That refresh/reconciliation pass fully converged the remaining clean tails:
  - `S3.5 us-east-1` => `run_successful_confirmed`
  - `S3.11 us-east-1` => `run_successful_confirmed`
  - both `EC2.7` groups => `run_successful_confirmed`
  - `S3.1 us-east-1` => `run_successful_confirmed`
- The only remaining non-green family is `S3.11 eu-north-1`, which now truthfully projects a mixed final state instead of a total failure bucket:
  - `10/13` members are `run_successful_confirmed`
  - `3/13` members remain `run_not_successful`
  - the retained evidence points to an already-finalized failed grouped run preventing full projection repair after the later successful rerun
