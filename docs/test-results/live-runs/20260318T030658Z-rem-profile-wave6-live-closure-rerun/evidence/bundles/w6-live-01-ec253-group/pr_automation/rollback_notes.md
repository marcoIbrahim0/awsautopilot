# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## Security groups should not allow unrestricted access to ports with high risk
- Action ID: `2a1c9d2f-b05d-48b3-bcec-d7645c5fd017`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-0ef32ca8805a55a8b|EC2.53`
- Rollback command: `aws ec2 authorize-security-group-ingress --group-id sg-0ef32ca8805a55a8b --ip-permissions '[{"IpProtocol":"tcp","FromPort":22,"ToPort":22,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":3389,"ToPort":3389,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'`

## Security groups should not allow unrestricted access to ports with high risk
- Action ID: `ad9328e1-faf2-4fd4-9885-c7f8c50c7d14`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-06f6252fa8a95b61d|EC2.53`
- Rollback command: `python3 ./executable/actions/02-arn-aws-ec2-eu-north-1-696505809372-security-gro-ad9328e1/rollback/sg_restore.py`
