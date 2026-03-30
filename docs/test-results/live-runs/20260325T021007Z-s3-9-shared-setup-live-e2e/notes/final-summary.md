# 20260325T021007Z S3.9 Shared-Setup Live E2E

## Scope

- Deploy the grouped S3.9 shared destination-bucket setup fix to production.
- Prove the deployed API/worker/callback path with a real live bundle download and operator-style `run_all.sh` execution.
- Re-run the deployed refresh path with live ingest, compute, and reconciliation.

## Deployment

- Serverless deploy completed successfully on March 25, 2026 UTC.
- Live API Lambda image after deploy: `20260325T021017Z`
- Live `/health`: `200`
- Live `/ready`: `200`

## Live grouped-create proof

- Group id: `8d0b831d-8c37-48eb-b1f2-099d6271faaa`
- Browser-led `/actions/group` proof:
  - the real UI still enforces the risk-acknowledgement gate for S3.9
  - a plain repeat click now returns the truthful duplicate/no-change message instead of the old broken create path
- Live options API now recommends the new executable branch:
  - strategy: `s3_enable_access_logging_guided`
  - recommended profile: `s3_enable_access_logging_create_destination_bucket`
  - decision rationale: destination bucket creation with secure defaults

## Fresh live runs

### First fresh proof run

- Group run: `460b4c6c-4657-409b-906a-1d052d899c92`
- Remediation run: `5d0495da-6b22-41d7-be5b-6aa6f8f525da`
- This used the default destination bucket name.
- Bundle generation succeeded and the downloaded ZIP proved the code fix:
  - one shared setup folder under `executable/actions/00-shared-*`
  - one `s3_access_logging_shared_destination.tf`
  - per-action folders contained only `aws_s3_bucket_logging` resources and no repeated destination-bucket creation
- The previously broken default destination bucket already existed in AWS from the older failed live run, so this run was retained as a structural proof, not the clean execution proof.

### Clean-state execution run

- Group run: `d8602e3c-0132-4b42-a335-8e65f9ab9366`
- Remediation run: `2d670d0d-91c6-4ffd-aaf2-a25257c094eb`
- Destination bucket override: `security-autopilot-access-logs-696505809372-s9fix1`
- Bundle download succeeded.
- Bundle execution succeeded with:
  - `14/14` action folders successful
  - `0/14` failed
- Shared setup created the destination bucket once, then all per-bucket logging actions applied successfully.
- Group callback landed correctly:
  - group run `d8602e3c-0132-4b42-a335-8e65f9ab9366` finished
  - grouped state converged immediately to `13` pending-confirmation and `1` metadata-only

## Deployed refresh-path proof

- Live ingest trigger:
  - account `696505809372`
  - region `eu-north-1`
  - queued successfully
- Live compute trigger:
  - account `696505809372`
  - region `eu-north-1`
  - queued successfully
- Live reconciliation run:
  - run id: `ba7ce30f-0b56-466e-a768-cac5a5d8a04d`
  - services: `["s3"]`
  - region: `eu-north-1`
  - final status: `succeeded`

## Final live truth

- After callback, before deployed refresh:
  - `13` actions: `run_successful_pending_confirmation`
  - `1` action: `run_finished_metadata_only`
- After deployed ingest + compute + reconciliation:
  - `13` actions: `run_successful_confirmed`
  - `1` action: `run_finished_metadata_only`
  - `2` new actions: `not_run_yet`

The two new `not_run_yet` members are:

- `arn:aws:s3:::security-autopilot-access-logs-696505809372`
- `arn:aws:s3:::security-autopilot-access-logs-696505809372-s9fix1`

These are both destination log buckets. The grouped S3.9 execution path now works correctly, but recompute truthfully creates new S3.9 actions for the log buckets themselves because they do not have access logging enabled.

## Verdict

- The original S3.9 product bug is fixed in production:
  - grouped bundle generation succeeds
  - the destination bucket is created once per grouped bundle
  - the downloaded bundle runs successfully end to end
  - callback/group-run convergence works
  - deployed ingest/compute/reconciliation succeeds
- The remaining product question is different and narrower:
  - should designated S3 access-log destination buckets be excluded from S3.9 so the system does not recursively generate fresh S3.9 actions for log buckets?

## Evidence

- Health and deploy proof:
  - `evidence/api/health.json`
  - `evidence/api/ready.json`
  - `evidence/api/api-lambda.json`
- Bundle generation and download:
  - `evidence/api/s3_9-clean-create-response.json`
  - `evidence/api/s3_9-clean-remediation-run-final.json`
  - `evidence/api/s3_9-clean-download.headers.txt`
- Extracted bundle:
  - `evidence/bundles/pr-bundle-2d670d0d-91c6-4ffd-aaf2-a25257c094eb/`
- Bundle execution transcript:
  - `evidence/api/s3_9-clean-run-all.log`
- Group/callback proof:
  - `evidence/api/s3_9-group-runs-post-run-all.json`
  - `evidence/api/s3_9-group-detail-after-callback.json`
- Refresh/reconciliation proof:
  - `evidence/api/s3_9-ingest-response.json`
  - `evidence/api/s3_9-compute-response.json`
  - `evidence/api/s3_9-reconciliation-start.json`
  - `evidence/api/s3_9-reconciliation-status-after-wait.json`
  - `evidence/api/s3_9-group-detail-after-wait.json`
- Browser proof:
  - `evidence/playwright/pre-run-group-page.png`
  - `evidence/playwright/post-first-click.png`
  - `evidence/playwright/s3_9-post-refresh.png`
