# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## EBS default encryption should be enabled
- Action ID: `cdbe5eda-ae70-4d31-815c-35fce06c1596`
- Control ID: `EC2.7`
- Target: `696505809372|us-east-1|AWS::::Account:696505809372|EC2.7`
- Rollback command: `aws ec2 disable-ebs-encryption-by-default`
