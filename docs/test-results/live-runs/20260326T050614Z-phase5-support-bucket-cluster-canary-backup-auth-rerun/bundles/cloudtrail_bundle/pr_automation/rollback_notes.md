# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## CloudTrail should be enabled and configured with at least one multi-Region trail that includes read and write management events
- Action ID: `9074eb82-d359-4ce2-9155-1b71699fed8f`
- Control ID: `CloudTrail.1`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|CloudTrail.1`
- Rollback command: `aws cloudtrail stop-logging --name 696505809372|eu-north-1|AWS::::Account:696505809372|CloudTrail.1`
