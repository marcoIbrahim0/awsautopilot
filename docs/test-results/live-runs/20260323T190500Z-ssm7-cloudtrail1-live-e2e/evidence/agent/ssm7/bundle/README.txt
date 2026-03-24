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
- terraform_plan_timestamp_utc: 2026-03-23T15:42:37+00:00
- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to preserve unrelated existing configuration unless a generated diff explicitly changes it.


SSM.7 post-fix access guidance
------------------------------
What changes
- Sets SSM service setting to block public document sharing.

How to access now
- SSM sharing guidance: share documents to specific AWS accounts (private share), not publicly:
  aws ssm modify-document-permission --name <document-name> --permission-type Share --account-ids-to-add <account-id>

Verify
- Confirm service setting remains `Disable`:
  aws ssm get-service-setting --setting-id arn:aws:ssm:<region>:<account-id>:servicesetting/ssm/documents/console/public-sharing-permission --query 'ServiceSetting.SettingValue' --output text
- Confirm per-document share targets:
  aws ssm describe-document-permission --name <document-name> --permission-type Share

Rollback
- Emergency-only rollback to re-enable public sharing:
  aws ssm update-service-setting --setting-id arn:aws:ssm:<region>:<account-id>:servicesetting/ssm/documents/console/public-sharing-permission --setting-value Enable


Selected strategy
-----------------
- strategy_id: ssm_disable_public_document_sharing

Risk recommendation
-------------------
- review_and_acknowledge

Dependency review checklist
---------------------------
- [warn] ssm_document_sharing_breakage: Publicly shared SSM document consumers may lose access after enforcement.
