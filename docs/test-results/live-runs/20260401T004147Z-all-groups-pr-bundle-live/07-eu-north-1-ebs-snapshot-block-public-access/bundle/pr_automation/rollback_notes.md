# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## Amazon EBS Snapshots should not be publicly accessible
- Action ID: `087eaa5d-4fdf-4139-9b4c-104de2608fbb`
- Control ID: `EC2.182`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|EC2.182`
- Rollback command: `aws ec2 disable-snapshot-block-public-access`

## Amazon EBS Snapshots should not be publicly accessible
- Action ID: `4c3876e4-8260-4897-a8a4-4fb7f683d357`
- Control ID: `EC2.182`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:snapshotblockpublicaccess/696505809372|EC2.182`
- Rollback command: `aws ec2 disable-snapshot-block-public-access`
