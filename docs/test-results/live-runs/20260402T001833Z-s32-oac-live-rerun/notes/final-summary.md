# FAIL: S3.2 duplicate-OAC live rerun replaced the old defect with new bounded blockers

## Scope

- Account: `696505809372`
- Region: `eu-north-1`
- Action group: `9200b6d5-b209-443f-9d78-28a4e60f6fb1`
- Strategy: `s3_migrate_cloudfront_oac_private`
- Affected action: `1dc66e7e-efe9-4fd6-9335-3197211b289f`
- Target bucket: `security-autopilot-dev-serverless-src-696505809372-eu-north-1`

## Request / run IDs

- First live attempt:
  - group run `b880d21e-eabc-4e93-aa2e-ffec9a84b9fc`
  - remediation run `07e907d7-2cf0-4fbc-9c5b-31bcc888296a`
- Post-fix live attempt:
  - group run `a42ffced-c41c-449e-9b0e-66621947b3f1`
  - remediation run `fff01518-2143-4a26-a6f7-830a3630709f`

## What changed

- The S3.2 bundle now ships CloudFront OAC adopt/reuse discovery logic through `scripts/cloudfront_oac_discovery.py` and `data "external" "cloudfront_reuse"`.
- The checked-in runner no longer treats `OriginAccessControlAlreadyExists` as a duplicate-only success.
- Focused local tests passed before redeploy:
  - `11 passed` for `tests/test_step7_components.py -k 'cloudfront_oac_private or s3_2'`
  - `1 passed` for `tests/test_remediation_run_worker.py -k 'duplicate_tolerance or run_all'`

## Live result

- The retained April 1 duplicate-OAC error did not reappear on the post-fix live rerun.
- The real affected customer action is now downgraded before executable bundle emission:
  - `Target bucket 'security-autopilot-dev-serverless-src-696505809372-eu-north-1' existence could not be verified from this account context (403).`
- Other executable S3.2 folders in the same grouped bundle now enter the new Terraform path, but the local customer-run execution hit a new runtime blocker:
  - `Error: timeout while waiting for plugin to start`
  - `ERROR: command timed out after 300s: terraform plan -input=false`
  - `ERROR: command timed out after 300s: terraform apply -auto-approve`

## Final status

- `FAIL`
- The old `OriginAccessControlAlreadyExists` defect is no longer the blocker.
- The remaining bounded blockers are:
  - affected customer action downgraded by bucket-verification `403`
  - executable S3.2 folders timing out in Terraform/provider startup during live local bundle execution
- Because the callback never completed after the local timeout/interruption, the control plane still shows the post-fix group run as `started` in `api/group-run-status-during-hang.json`.

## Key retained files

- Request inputs:
  - `api/create-group-run-request.json`
  - `api/create-group-run-request-retry.json`
- Run creation:
  - `api/create-group-run-response.json`
  - `api/create-group-run-response-retry.json`
- Polling:
  - `api/group-run-final.json`
  - `api/group-run-final-retry.json`
  - `api/group-run-status-during-hang.json`
- Bundle artifacts:
  - `bundle/retry/pr-bundle.zip`
  - `bundle/retry/extracted/`
- Inspection:
  - `notes/bundle-inspection.md`
  - `notes/deploy-summary.md`
  - `notes/next-agent-handoff.md`
- Apply transcript:
  - `apply/retry/run_all.stdout.log`
  - `apply/retry/run_all.tail.final.log`
