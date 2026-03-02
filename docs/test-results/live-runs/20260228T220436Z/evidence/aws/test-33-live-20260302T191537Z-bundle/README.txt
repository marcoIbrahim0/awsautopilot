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
- terraform_plan_timestamp_utc: 2026-03-02T19:15:43+00:00
- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to preserve unrelated existing configuration unless a generated diff explicitly changes it.


S3.2 guardrail (read before apply)
----------------------------------
- This bundle is control-level hardening: it enforces S3 Block Public Access on a bucket.
- It is NOT a full CloudFront + OAC + private S3 migration.
- Applying this can break workloads that rely on public S3 access (public object URLs, website endpoint, public ACLs/policies).

Pre-apply checks (required)
---------------------------
- Capture current bucket policy and ACL.
- Confirm whether bucket website hosting is enabled.
- Confirm whether this bucket is a log sink (CloudTrail / Config / ELB / CloudFront / S3 access logs).
- Confirm encryption mode (SSE-S3 vs SSE-KMS). If SSE-KMS, identify required KMS key policy updates.
- Identify cross-account principals and access points that need to keep access.
- If available, review CloudTrail S3 data events for recent GetObject/ListBucket/PutObject callers.

Apply sequence (recommended)
----------------------------
- Deploy CloudFront + OAC + bucket policy updates (and KMS policy updates if needed).
- Update clients/apps to use CloudFront instead of direct S3 public access.
- Then apply S3 Block Public Access.
- Monitor for AccessDenied/KMS errors and CloudFront 4xx spikes.

Rollback plan
-------------
- Keep a backup of prior bucket policy/ACL and restore quickly if needed.
- Temporarily re-enable only minimum required access to recover service.


Selected strategy
-----------------
- strategy_id: s3_bucket_block_public_access_standard

Risk recommendation
-------------------
- review_and_acknowledge

Dependency review checklist
---------------------------
- [warn] s3_public_access_dependency: Validate direct bucket access dependencies before applying this strategy. Analyze the affected S3 bucket policy/ACL/public-access-block settings, the bucket KMS key policy/grants (if SSE-KMS), CloudFront OAC/OAI configuration, and any VPC endpoint or cross-account IAM principals that access the bucket. If IAM Access Analyzer is enabled in this account/region, this validation can be automated.
