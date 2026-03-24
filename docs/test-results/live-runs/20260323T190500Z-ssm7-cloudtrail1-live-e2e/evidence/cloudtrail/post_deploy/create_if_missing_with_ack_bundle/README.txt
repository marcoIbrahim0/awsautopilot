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
- terraform_plan_timestamp_utc: 2026-03-23T15:58:31+00:00
- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to preserve unrelated existing configuration unless a generated diff explicitly changes it.


Selected strategy
-----------------
- strategy_id: cloudtrail_enable_guided

Risk recommendation
-------------------
- review_and_acknowledge

Dependency review checklist
---------------------------
- [warn] cloudtrail_cost_impact: CloudTrail log delivery and retention increase S3 storage and request costs.
- [warn] cloudtrail_log_bucket_prereq: This PR bundle requires a log-delivery S3 bucket. Create or identify the bucket and set trail_bucket_name before apply.
