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
- terraform_plan_timestamp_utc: 2026-03-18T02:47:41+00:00
- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to preserve unrelated existing configuration unless a generated diff explicitly changes it.


EC2.53 post-fix access guidance
-------------------------------
What changes
- Public SSH/RDP ingress on 22/3389 is restricted; optional preflight may revoke broad rules before adding restricted rules.

How to access now
- Use SSM Session Manager for operator access instead of public SSH/RDP:
  aws ssm start-session --target <instance-id> --region <region>
- Keep bastion/VPN as fallback for non-SSM-managed workloads.

Verify
- Confirm no 0.0.0.0/0 or ::/0 remains for 22/3389:
  aws ec2 describe-security-group-rules --region <region> --filters Name=group-id,Values=<security-group-id> Name=is-egress,Values=false --query "SecurityGroupRules[?((FromPort==`22`||FromPort==`3389`) && (CidrIpv4=='0.0.0.0/0' || CidrIpv6=='::/0'))]" --output json

Rollback
- Re-authorize only temporary, scoped admin ingress if lockout occurs:
  aws ec2 authorize-security-group-ingress --region <region> --group-id <security-group-id> --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=<admin-cidr>}]'


Selected strategy
-----------------
- strategy_id: sg_restrict_public_ports_guided
