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
- terraform_plan_timestamp_utc: 2026-03-01T19:40:51+00:00
- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to preserve unrelated existing configuration unless a generated diff explicitly changes it.


S3.2 migration variant (CloudFront + OAC + private S3)
-------------------------------------------------------
- This bundle creates CloudFront distribution + OAC, enforces S3 Block Public Access, and applies a bucket policy for CloudFront read access.
- It is intended to replace direct public S3 access with CloudFront.

Before apply
------------
- Existing bucket policy statements are preloaded into `terraform.auto.tfvars.json` when runtime evidence is available.
- If your environment requires a different baseline, set variable existing_bucket_policy_json explicitly.
- If additional internal/cross-account roles need read access, set additional_read_principal_arns.
- If objects use SSE-KMS, confirm KMS key policy allows required principals.

After apply
-----------
- Update clients/apps to use the CloudFront domain output.
- Validate key object paths and monitor CloudFront 4xx/S3 AccessDenied/KMS AccessDenied.


Selected strategy
-----------------
- strategy_id: s3_migrate_cloudfront_oac_private

Risk recommendation
-------------------
- safe_to_proceed

Dependency review checklist
---------------------------
- [pass] s3_public_access_dependency: Bucket policy is not public and website hosting is disabled; no direct-public-access dependency was detected from runtime probes.
