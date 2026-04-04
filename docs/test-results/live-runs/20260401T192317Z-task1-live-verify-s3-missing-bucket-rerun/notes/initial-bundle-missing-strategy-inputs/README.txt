AWS Security Autopilot — Terraform bundle

Credentials and region
--------------------
- Use your normal AWS credentials: a named profile from ~/.aws/config (e.g. default) or environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY).
- Do NOT set AWS_PROFILE to your account ID. Use a profile name (e.g. default) or leave unset to use the default profile.
- Set the region: export AWS_REGION=eu-north-1 (or your action's region).

Commands
--------
terraform init
terraform plan
terraform apply

Terraform proof metadata (C2/C5)
-------------------------------
- terraform_plan_timestamp_utc: 2026-04-01T19:29:11+00:00
- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to preserve unrelated existing configuration unless a generated diff explicitly changes it.


S3.15 rollback safeguards
-------------------------
- This executable Terraform path snapshots the exact pre-remediation bucket encryption state under `.s3-encryption-rollback/`.
- Run `python3 scripts/s3_encryption_capture.py` before `terraform apply`. The generated helper already targets this bundle's bucket and region; `BUCKET_NAME` and `REGION` are optional overrides only.
- After `terraform destroy`, run `python3 rollback/s3_encryption_restore.py` to restore the captured encryption exactly.
- If the bucket originally had no default encryption configuration, the restore helper deletes the post-remediation config instead of forcing a fallback encryption mode.


Selected strategy
-----------------
- strategy_id: s3_enable_sse_kms_guided

Risk recommendation
-------------------
- safe_to_proceed

Dependency review checklist
---------------------------
- [pass] s3_sse_kms_bucket_scope_confirmed: Bucket-scoped target was identified for S3 SSE-KMS enforcement.
- [pass] s3_sse_kms_aws_managed_branch_ready: AWS-managed SSE-KMS remains executable on this branch.
