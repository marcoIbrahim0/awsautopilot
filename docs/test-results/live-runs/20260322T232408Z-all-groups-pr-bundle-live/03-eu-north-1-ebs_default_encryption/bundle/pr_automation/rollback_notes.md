# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## EBS default encryption should be enabled
- Action ID: `d8da3698-230f-44e3-9c11-cc9e4099b7f6`
- Control ID: `EC2.7`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|EC2.7`
- Rollback command: `aws ec2 disable-ebs-encryption-by-default`
