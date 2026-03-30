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
- terraform_plan_timestamp_utc: 2026-03-28T22:56:39+00:00
- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to preserve unrelated existing configuration unless a generated diff explicitly changes it.


EC2.53 post-fix access guidance
-------------------------------
What changes
- Public SSH/RDP ingress on 22/3389 is restricted.
- For `close_and_revoke`, `ssm_only`, and `bastion_sg_reference`, run `scripts/sg_capture_state.py` before apply to snapshot exact public ingress pre-state under `.sg-rollback/sg_ingress_snapshot.json`.
- For `close_and_revoke`, `ssm_only`, and `bastion_sg_reference`, `rollback/sg_restore.py` restores the captured ingress rules, including rule descriptions, after `terraform destroy`.
- `ssm_only` removes public SSH/RDP ingress and does not add replacement SSH/RDP allowlists.
- `bastion_sg_reference` removes public SSH/RDP ingress and replaces it with source-security-group access from the approved bastion SG list.

How to access now
- Use SSM Session Manager for operator access instead of public SSH/RDP:
  aws ssm start-session --target <instance-id> --region <region>
- Keep bastion/VPN as fallback for non-SSM-managed workloads.
- When using `bastion_sg_reference`, connect through instances or services attached to the approved bastion security groups instead of direct public admin ingress.

Verify
- Confirm no 0.0.0.0/0 or ::/0 remains for 22/3389:
  aws ec2 describe-security-group-rules --region <region> --filters Name=group-id,Values=<security-group-id> --query "SecurityGroupRules[?(IsEgress==`false`) && ((FromPort==`22` || FromPort==`3389`) && (CidrIpv4=='0.0.0.0/0' || CidrIpv6=='::/0'))]" --output json

Rollback
- Standard rollback for `close_and_revoke`, `ssm_only`, and `bastion_sg_reference`: run `terraform destroy`, then `python3 rollback/sg_restore.py`.
- Emergency-only fallback if no snapshot exists:
  aws ec2 authorize-security-group-ingress --region <region> --group-id <security-group-id> --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=<admin-cidr>}]'


Selected strategy
-----------------
- strategy_id: sg_restrict_public_ports_guided

Risk recommendation
-------------------
- review_and_acknowledge

Dependency review checklist
---------------------------
- [unknown] risk_evaluation_not_specialized: No specialized dependency checks are available for this strategy yet.
