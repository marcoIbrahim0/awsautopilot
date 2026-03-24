# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## Amazon EBS Snapshots should not be publicly accessible
- Action ID: `12b5bacc-a721-4f05-afc1-2a7aed16048e`
- Control ID: `EC2.182`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:snapshotblockpublicaccess/696505809372|EC2.182`
- Rollback command: `aws ec2 disable-snapshot-block-public-access`

## Amazon EBS Snapshots should not be publicly accessible
- Action ID: `87e9188b-80ff-42cb-8e2a-e6b84eba1389`
- Control ID: `EC2.182`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|EC2.182`
- Rollback command: `aws ec2 disable-snapshot-block-public-access`
