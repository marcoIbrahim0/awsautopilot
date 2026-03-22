# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## Security groups should not allow unrestricted access to ports with high risk
- Action ID: `0d5b9a29-bd79-4454-a9c4-c0a5c62479e0`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-0ef32ca8805a55a8b|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-0ef32ca8805a55a8b --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should not allow unrestricted access to ports with high risk
- Action ID: `d740b079-2fe0-40ec-baa0-efe3e0e01a2b`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-06f6252fa8a95b61d|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-06f6252fa8a95b61d --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`
