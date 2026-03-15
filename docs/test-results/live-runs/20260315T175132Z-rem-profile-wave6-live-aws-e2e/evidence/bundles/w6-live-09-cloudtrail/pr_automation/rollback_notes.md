# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## CloudTrail should be enabled and configured with at least one multi-Region trail that includes read and write management events
- Action ID: `4c4f4b3b-90d5-4682-a94a-1cfdc673bdc6`
- Control ID: `CloudTrail.1`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|CloudTrail.1`
- Rollback command: `aws cloudtrail stop-logging --name 696505809372|eu-north-1|AWS::::Account:696505809372|CloudTrail.1`
