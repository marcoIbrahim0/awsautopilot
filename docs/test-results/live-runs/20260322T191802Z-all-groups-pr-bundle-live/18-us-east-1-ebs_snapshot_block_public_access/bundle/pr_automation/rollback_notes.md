# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## Amazon EBS Snapshots should not be publicly accessible
- Action ID: `442e46ac-f31c-4242-82ca-9e47081a3adb`
- Control ID: `EC2.182`
- Target: `696505809372|us-east-1|arn:aws:ec2:us-east-1:696505809372:snapshotblockpublicaccess/696505809372|EC2.182`
- Rollback command: `aws ec2 disable-snapshot-block-public-access`
