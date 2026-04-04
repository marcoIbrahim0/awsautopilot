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
- terraform_plan_timestamp_utc: 2026-04-02T01:39:22+00:00
- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to preserve unrelated existing configuration unless a generated diff explicitly changes it.


S3.2 migration variant (CloudFront + OAC + private S3)
-------------------------------------------------------
What changes
- Creates CloudFront + OAC, enforces S3 Block Public Access, and updates bucket policy for CloudFront-origin read access.
- Intended to replace direct public S3 access.

How to access now
- Use the CloudFront HTTPS domain output for clients/apps.
- Example HTTPS check:
  curl -I https://<cloudfront-domain>/<object-key>

Verify
- Existing bucket policy statements are preloaded into `terraform.auto.tfvars.json` when evidence is available.
- If additional internal/cross-account roles still need direct S3 reads, set `additional_read_principal_arns`.
- Validate key object paths and monitor CloudFront 4xx plus S3/KMS AccessDenied signals.

Rollback
- Restore previous bucket policy JSON if needed, then roll back CloudFront origin-routing changes.
- Keep rollback scoped and temporary; re-apply least-privilege policy once access is restored.


Selected strategy
-----------------
- strategy_id: s3_migrate_cloudfront_oac_private
