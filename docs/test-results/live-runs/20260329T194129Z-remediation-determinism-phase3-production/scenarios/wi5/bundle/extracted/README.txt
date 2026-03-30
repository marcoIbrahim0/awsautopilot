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
- terraform_plan_timestamp_utc: 2026-03-29T20:37:17+00:00
- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to preserve unrelated existing configuration unless a generated diff explicitly changes it.


S3 website migration variant (CloudFront + private S3 + Route53)
---------------------------------------------------------------
What changes
- Creates CloudFront + OAC for the private S3 REST origin, updates Route53 aliases, removes S3 website hosting, and then enables S3 Block Public Access.
- Intended only for buckets currently using simple S3 website hosting (`IndexDocument` plus optional `ErrorDocument`).

How to access now
- Validate each hostname in `aliases` resolves to the new CloudFront distribution after apply.
- Example HTTPS check:
  curl -I https://<alias-hostname>/

Verify
- `terraform.auto.tfvars.json` includes the captured S3 website configuration for rollback documentation.
- Confirm Route53 aliases point to CloudFront and website hosting is removed:
  aws s3api get-bucket-website --bucket <bucket-name>
- Confirm all four block-public-access flags are true:
  aws s3api get-public-access-block --bucket <bucket-name> --query 'PublicAccessBlockConfiguration' --output json

Rollback
- Restore Route53 aliases and S3 website hosting before reopening direct public access.
- Use the captured `existing_bucket_website_configuration_json` value in `terraform.auto.tfvars.json` with `aws s3api put-bucket-website` if emergency rollback is required.
- Keep rollback temporary and re-apply private-origin controls after traffic is restored.


Selected strategy
-----------------
- strategy_id: s3_migrate_website_cloudfront_private

Risk recommendation
-------------------
- safe_to_proceed

Dependency review checklist
---------------------------
- [pass] s3_public_access_dependency: Runtime probes captured a simple S3 website configuration and explicit Route53/ACM inputs, so the CloudFront website migration path can preserve access during cutover.
