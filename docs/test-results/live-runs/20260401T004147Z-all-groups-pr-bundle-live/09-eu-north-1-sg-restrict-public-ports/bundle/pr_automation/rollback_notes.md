# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## Security group allows public SSH/RDP access
- Action ID: `9569aa98-af93-4095-a8f6-695867c1b839`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|sg-02dd3aac53025646a|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-02dd3aac53025646a --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security group allows public SSH/RDP access
- Action ID: `4a1e56fe-ba65-4082-a72b-b39a28d70945`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|sg-05394bffb02bf477c|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-05394bffb02bf477c --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should only allow unrestricted incoming traffic for authorized ports
- Action ID: `58a22607-666e-4016-8fe3-4ce62a235a6e`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-06f6252fa8a95b61d|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-06f6252fa8a95b61d --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should not allow ingress from 0.0.0.0/0 or ::/0 to port 22
- Action ID: `d56365fe-16be-4239-9b2f-d6ca7e246d35`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-02279e5f534057980|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-02279e5f534057980 --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should only allow unrestricted incoming traffic for authorized ports
- Action ID: `4694e0cc-99a6-4533-8506-19a7a4710d95`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|sg-06f6252fa8a95b61d|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-06f6252fa8a95b61d --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should only allow unrestricted incoming traffic for authorized ports
- Action ID: `6470a99a-ea73-48a0-ba1d-75c1ebd8ba59`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|sg-0ef32ca8805a55a8b|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-0ef32ca8805a55a8b --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should not allow unrestricted access to ports with high risk
- Action ID: `dfa0a526-87b8-4670-92d7-401a611f58f5`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-0ef32ca8805a55a8b|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-0ef32ca8805a55a8b --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`
