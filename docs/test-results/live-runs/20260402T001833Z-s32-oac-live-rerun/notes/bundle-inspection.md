# Bundle Inspection Notes

## Scope

- Evidence package: `20260402T001833Z-s32-oac-live-rerun`
- Affected customer scope: account `696505809372`, region `eu-north-1`
- Target action: `1dc66e7e-efe9-4fd6-9335-3197211b289f`
- Target bucket: `security-autopilot-dev-serverless-src-696505809372-eu-north-1`
- Known retained duplicate-OAC resource:
  - OAC name: `security-autopilot-oac-3b3503236fd8`
  - Distribution: `E3T188CQ1IH26W`

## First generated bundle

- Group run: `b880d21e-eabc-4e93-aa2e-ffec9a84b9fc`
- Remediation run: `07e907d7-2cf0-4fbc-9c5b-31bcc888296a`
- Result: bundle generation succeeded, but the shipped executable S3.2 Terraform had invalid multiline ternary syntax in `locals`.
- Observed in retained apply transcript:
  - `Error: Argument or block definition required`
  - `on s3_cloudfront_oac_private_s3.tf line 138`

## Post-fix generated bundle

- Group run: `a42ffced-c41c-449e-9b0e-66621947b3f1`
- Remediation run: `fff01518-2143-4a26-a6f7-830a3630709f`
- Post-deploy image tag: `20260402T002927Z`

### Confirmed shipped S3.2 reuse logic

- Extracted executable S3.2 bundles now include `scripts/cloudfront_oac_discovery.py`.
- Extracted executable S3.2 bundles now include `data "external" "cloudfront_reuse"`.
- Extracted executable S3.2 bundles now wrap the conditional reuse locals correctly, for example:
  - `effective_oac_id = (`
  - `effective_distribution_id = (`
- Extracted runner still fail-closes `OriginAccessControlAlreadyExists` instead of masking it as a duplicate-only success.

### Affected customer action result

- The real affected customer action did not reach executable S3.2 after redeploy.
- Retained decision file:
  - `manual_guidance/actions/05-arn-aws-s3-security-autopilot-dev-serverless-src-1dc66e7e/decision.json`
- Current bounded blocker:
  - `Target bucket 'security-autopilot-dev-serverless-src-696505809372-eu-north-1' existence could not be verified from this account context (403).`
- This is a different blocker from the April 1 retained `OriginAccessControlAlreadyExists` failure.

### Executable S3.2 live runner result

- Other executable S3.2 action folders now ship the new discovery helper and enter real Terraform execution.
- Live execution no longer reproduced `OriginAccessControlAlreadyExists`.
- New runtime blocker from the retained transcript:
  - `Error: timeout while waiting for plugin to start`
  - `ERROR: command timed out after 300s: terraform plan -input=false`
  - `ERROR: command timed out after 300s: terraform apply -auto-approve`
- Direct operator probing under `AWS_PROFILE=test28-root` proved the helper script itself is responsive:
  - `cloudfront_oac_discovery.py` returned `{"mode": "create"}` for an executable S3.2 folder
  - `aws cloudfront list-origin-access-controls --no-cli-pager`
  - `aws cloudfront list-distributions --no-cli-pager`

## Outcome

- The old duplicate-OAC defect is closed in bundle generation and no longer reproduced on the live rerun.
- The real affected customer path is still blocked, but now by bundle-generation fail-closed downgrade on bucket verification (`403`) before executable S3.2 is emitted.
- Executable S3.2 bundles for other targets hit a separate live Terraform/external-provider timeout blocker.
