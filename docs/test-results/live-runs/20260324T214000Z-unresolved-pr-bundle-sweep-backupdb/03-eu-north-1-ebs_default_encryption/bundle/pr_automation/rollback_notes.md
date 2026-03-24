# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## EBS default encryption should be enabled
- Action ID: `dd810aea-8c89-4782-8e1f-2d2140e9c08d`
- Control ID: `EC2.7`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|EC2.7`
- Rollback command: `aws ec2 disable-ebs-encryption-by-default`
