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
- terraform_plan_timestamp_utc: 2026-03-28T02:43:16+00:00
- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to preserve unrelated existing configuration unless a generated diff explicitly changes it.


S3.5 post-fix access guidance
-----------------------------
What changes
- Adds `DenyInsecureTransport` to the bucket policy and preserves unrelated existing policy statements.

How to access now
- HTTPS requirement: all clients must use `https://` for S3 requests; `http://` requests are denied.

Verify
- Confirm bucket policy contains `DenyInsecureTransport`:
  aws s3api get-bucket-policy --bucket <bucket-name> --query Policy --output text
- Confirm HTTPS succeeds and HTTP is denied:
  curl -I https://<bucket-name>.s3.<region>.amazonaws.com/<object-key>
  curl -I http://<bucket-name>.s3.<region>.amazonaws.com/<object-key>

Rollback
- Before apply, if the bucket already has a policy, capture it:
  aws s3api get-bucket-policy --bucket <bucket-name> --query Policy --output text > pre-remediation-policy.json
- Restore prior bucket policy JSON backup if needed:
  aws s3api put-bucket-policy --bucket <bucket-name> --policy file://pre-remediation-policy.json


Selected strategy
-----------------
- strategy_id: s3_enforce_ssl_strict_deny
