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
- terraform_plan_timestamp_utc: 2026-03-16T00:13:49+00:00
- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to preserve unrelated existing configuration unless a generated diff explicitly changes it.


S3.2 post-fix access guidance
-----------------------------
What changes
- This bundle enforces S3 Block Public Access on the target bucket.
- It is NOT a full CloudFront + OAC + private S3 migration.

How to access now
- CloudFront usage note: serve user traffic through a CloudFront HTTPS endpoint, not direct public S3 website/object URLs.
- Example HTTPS check:
  curl -I https://<cloudfront-domain>/<object-key>

Verify
- Confirm all four block-public-access flags are true:
  aws s3api get-public-access-block --bucket <bucket-name> --query 'PublicAccessBlockConfiguration' --output json
- Validate clients are using CloudFront (or another approved private path) and monitor for 4xx/AccessDenied spikes.

Rollback
- Restore the prior bucket policy/ACL backup if application access breaks.
- Emergency-only unblock command:
  aws s3api put-public-access-block --bucket <bucket-name> --public-access-block-configuration BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false


Selected strategy
-----------------
- strategy_id: s3_bucket_block_public_access_standard
