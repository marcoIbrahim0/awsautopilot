# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## Amazon EBS Snapshots should not be publicly accessible
- Action ID: `b1c592c0-de9c-43d0-bf40-883d8ae1623d`
- Control ID: `EC2.182`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:snapshotblockpublicaccess/696505809372|EC2.182`
- Rollback command: `aws ec2 disable-snapshot-block-public-access`

## Amazon EBS Snapshots should not be publicly accessible
- Action ID: `3eeb0195-44e3-4df6-9ae3-78e020348e42`
- Control ID: `EC2.182`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|EC2.182`
- Rollback command: `aws ec2 disable-snapshot-block-public-access`
