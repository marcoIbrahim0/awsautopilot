# Final Summary

- Run ID: `20260401T004147Z-all-groups-pr-bundle-live`
- Account: `696505809372`
- Groups processed: `14`

## Status Counts

- APPLY NOT SUCCESSFUL: `10`
- GENERATION NOT SUCCESSFUL: `2`
- Needs review before apply: `2`

## Key Blockers

- No-UI live auth now requires a browser-like `User-Agent`; the repo client had to be updated before `POST /api/auth/login` would pass the edge/WAF layer.
- Every executable bundle apply failed against AWS because local profile `test28-root` is no longer valid for account `696505809372`; Terraform/STS calls consistently returned `InvalidClientTokenId`.
- `IAM.4` still cannot be generated through the generic grouped route because production requires the dedicated `/api/root-key-remediation-runs` authority.
- `CloudTrail.1` grouped generation still fails closed when the log bucket cannot be verified from the current account context.

## Per-Group Results

### 01-eu-north-1-aws-config-enabled — APPLY NOT SUCCESSFUL
- Group: `02575097-6342-4ee5-a9e2-737eebcfcc29`
- Action type: `aws_config_enabled`
- Region: `eu-north-1`
- Remediation run: `e862d0fc-1156-48d3-ba4e-4bcba2e1170e`
- Group run: `2b2d0792-766b-471d-b2d5-4cf09205a95e`
- Runnable actions: `1`
- Review-required actions: `0`

### 02-eu-north-1-ssm-block-public-sharing — Needs review before apply
- Group: `ed48e583-8b8e-43b4-ad5e-3641b8276909`
- Action type: `ssm_block_public_sharing`
- Region: `eu-north-1`
- Remediation run: `1e37cf14-5c9f-4b9c-9abd-931b00c1c2e0`
- Group run: `03bf3071-9c86-4a2e-9c76-2daf3085d894`
- Runnable actions: `0`
- Review-required actions: `1`
- Why not runnable: `Compatibility resolver defaulted to the compatible profile 'ssm_disable_public_document_sharing' for strategy 'ssm_disable_public_document_sharing'. Run creation was accepted after risk_acknowledged=true satisfied review-required checks.`

### 03-eu-north-1-enable-guardduty — Needs review before apply
- Group: `c84d5c12-593d-4ab3-b790-ce56e5484f92`
- Action type: `enable_guardduty`
- Region: `eu-north-1`
- Remediation run: `79c80b66-ca47-4215-85d1-f9f9a329b66b`
- Group run: `5fc290b9-b5f2-4db6-8a7c-2dd24e306c24`
- Runnable actions: `0`
- Review-required actions: `1`
- Why not runnable: `Compatibility resolver defaulted to the compatible profile 'guardduty_enable_pr_bundle' for strategy 'guardduty_enable_pr_bundle'. Run creation was accepted after risk_acknowledged=true satisfied review-required checks.`

### 04-eu-north-1-s3-bucket-lifecycle-configuration — APPLY NOT SUCCESSFUL
- Group: `9a904e6a-3ab8-4eca-be92-b727b0aacf67`
- Action type: `s3_bucket_lifecycle_configuration`
- Region: `eu-north-1`
- Remediation run: `f6b84600-f8b2-4db8-a727-972afba3dd34`
- Group run: `4f565434-eeb2-42b6-97f9-3cee16fb9535`
- Runnable actions: `23`
- Review-required actions: `0`
- Why not runnable: `Lifecycle preservation evidence is missing for additive merge review.`

### 05-eu-north-1-s3-bucket-access-logging — APPLY NOT SUCCESSFUL
- Group: `984e6f5e-d1e6-44aa-90e6-1a3ddc152a2c`
- Action type: `s3_bucket_access_logging`
- Region: `eu-north-1`
- Remediation run: `a8d2e440-7218-4366-92a1-7575cc024157`
- Group run: `46a7f9d0-a0a0-437a-a305-2923110f6b8b`
- Runnable actions: `14`
- Review-required actions: `2`
- Why not runnable: `Source bucket scope could not be proven for S3 access logging; review the affected bucket relationship manually.`
- Why not runnable: `Log destination must be a dedicated bucket and cannot match the source bucket.`

### 06-eu-north-1-s3-bucket-encryption-kms — APPLY NOT SUCCESSFUL
- Group: `97e52204-f7f6-40c1-b2ac-acb99308e241`
- Action type: `s3_bucket_encryption_kms`
- Region: `eu-north-1`
- Remediation run: `97865f8a-92aa-4d50-99f5-3a4353187e63`
- Group run: `be367b61-af64-4b17-ae0a-79fa81f1f3de`
- Runnable actions: `15`
- Review-required actions: `0`

### 07-eu-north-1-ebs-snapshot-block-public-access — APPLY NOT SUCCESSFUL
- Group: `957c3871-cad3-4530-aa29-386f6bda5cc6`
- Action type: `ebs_snapshot_block_public_access`
- Region: `eu-north-1`
- Remediation run: `64ffd317-94a9-493a-95f2-a8656154910e`
- Group run: `2448bb81-b5d1-444b-90c3-78e5139a4bf6`
- Runnable actions: `2`
- Review-required actions: `0`

### 08-eu-north-1-s3-block-public-access — APPLY NOT SUCCESSFUL
- Group: `8b81c1a8-a2c7-4250-aaf2-d5ae62f08dda`
- Action type: `s3_block_public_access`
- Region: `eu-north-1`
- Remediation run: `bc7f8fcd-7226-480a-87a6-1f03055455c7`
- Group run: `828038a5-d3a9-4c02-8575-c91d981e4948`
- Runnable actions: `1`
- Review-required actions: `0`

### 09-eu-north-1-sg-restrict-public-ports — APPLY NOT SUCCESSFUL
- Group: `595cb7e3-5f4f-49a4-9c48-9388f139f012`
- Action type: `sg_restrict_public_ports`
- Region: `eu-north-1`
- Remediation run: `39d1ad76-c49d-4db7-92c4-225a4600ac23`
- Group run: `fe667235-6149-4813-8959-8a1c8ae077da`
- Runnable actions: `7`
- Review-required actions: `0`

### 10-eu-north-1-iam-root-access-key-absent — GENERATION NOT SUCCESSFUL
- Group: `549cd627-4bab-4e34-a15a-d9d50d11b3d9`
- Action type: `iam_root_access_key_absent`
- Region: `eu-north-1`
- Runnable actions: `0`
- Review-required actions: `0`
- Failure detail: `{"existing_run_id": null, "payload": {"detail": {"detail": "IAM.4 execution is handled exclusively by /api/root-key-remediation-runs. Generic remediation-run routes expose IAM.4 guidance only.", "error": "Dedicated root-key route required", "execution_authority": "/api/root-key-remediation-runs", "reason": "root_key_execution_authority", "runbook_url": "docs/prod-readiness/root-credentials-require`

### 11-eu-north-1-ebs-default-encryption — APPLY NOT SUCCESSFUL
- Group: `3ff809df-3a5b-4012-b60d-5ffa124b0035`
- Action type: `ebs_default_encryption`
- Region: `eu-north-1`
- Remediation run: `f1ec8c94-63ec-4539-8c2e-3e67dd1101ed`
- Group run: `95b83a1b-5843-47c1-8d5d-7280cce436dd`
- Runnable actions: `1`
- Review-required actions: `0`

### 12-eu-north-1-s3-bucket-require-ssl — APPLY NOT SUCCESSFUL
- Group: `3cf29e81-7d1b-414a-ab78-d2e1c3abad27`
- Action type: `s3_bucket_require_ssl`
- Region: `eu-north-1`
- Remediation run: `38bddb1d-d90c-42d8-95fe-1acd3f71dfa7`
- Group run: `50a03134-1191-426f-8428-bfeefd00cef0`
- Runnable actions: `15`
- Review-required actions: `1`
- Why not runnable: `Bucket policy preservation evidence is missing for merge-safe SSL enforcement.`

### 13-eu-north-1-cloudtrail-enabled — GENERATION NOT SUCCESSFUL
- Group: `2efa04dd-8768-4668-a8a7-666ac895ba6b`
- Action type: `cloudtrail_enabled`
- Region: `eu-north-1`
- Runnable actions: `0`
- Review-required actions: `0`
- Failure detail: `{"existing_run_id": null, "payload": {"detail": {"detail": "CloudTrail log bucket could not be verified from this account context.", "error": "Invalid grouped remediation request", "reason": "invalid_strategy_inputs"}}, "reason": "invalid_strategy_inputs", "request_body": {"bucket_creation_acknowledged": true, "repo_target": {"base_branch": "main", "head_branch": "20260401t004147z-all-groups-pr-bu`

### 14-eu-north-1-s3-bucket-block-public-access — APPLY NOT SUCCESSFUL
- Group: `2990907c-b6bb-4821-9825-a523cb380bf5`
- Action type: `s3_bucket_block_public_access`
- Region: `eu-north-1`
- Remediation run: `64281514-ade2-4081-86ff-cadef9955eb5`
- Group run: `bc628ace-83bf-4709-b013-c042bb3f8798`
- Runnable actions: `14`
- Review-required actions: `0`
- Why not runnable: `Existing bucket policy preservation evidence is missing for CloudFront + OAC migration.; Missing bucket identifier for access-path validation.`
