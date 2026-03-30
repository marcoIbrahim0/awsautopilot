# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## Security groups should not allow unrestricted access to ports with high risk
- Action ID: `6f3dd905-6941-4742-aff4-96f262d8948d`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-06f6252fa8a95b61d|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-06f6252fa8a95b61d --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should not allow unrestricted access to ports with high risk
- Action ID: `75d10e83-0907-4a6a-af2a-0356b45172ad`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-0ef32ca8805a55a8b|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-0ef32ca8805a55a8b --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should only allow unrestricted incoming traffic for authorized ports
- Action ID: `719d9e88-e83c-4fab-9f25-29cd6bae10a7`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|sg-06f6252fa8a95b61d|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-06f6252fa8a95b61d --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should only allow unrestricted incoming traffic for authorized ports
- Action ID: `df16aa74-7a65-4e30-b5ee-688853936ae2`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|sg-0ef32ca8805a55a8b|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-0ef32ca8805a55a8b --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`
