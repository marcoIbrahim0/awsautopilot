# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## EBS default encryption should be enabled
- Action ID: `c400ae42-865c-4808-8aa0-11450b717714`
- Control ID: `EC2.7`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|EC2.7`
- Rollback command: `aws ec2 disable-ebs-encryption-by-default`
