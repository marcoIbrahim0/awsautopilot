# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## Security groups should not allow unrestricted access to ports with high risk
- Action ID: `0abc603d-b75a-4b49-9a5f-431a0aa82a4e`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-06f6252fa8a95b61d|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-06f6252fa8a95b61d --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should not allow unrestricted access to ports with high risk
- Action ID: `647784a7-f84b-4f64-b2f9-9e1998a86376`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-0ef32ca8805a55a8b|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-0ef32ca8805a55a8b --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should only allow unrestricted incoming traffic for authorized ports
- Action ID: `970a2bf8-e01b-4a2c-a699-cec968652acb`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|sg-0ef32ca8805a55a8b|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-0ef32ca8805a55a8b --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should only allow unrestricted incoming traffic for authorized ports
- Action ID: `9a8a19b3-b1c4-44af-9c66-a3b01432a116`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|sg-06f6252fa8a95b61d|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-06f6252fa8a95b61d --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`
