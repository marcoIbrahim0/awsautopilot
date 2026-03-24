# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## CloudTrail should be enabled and configured with at least one multi-Region trail that includes read and write management events
- Action ID: `2ea6f141-6134-4dcd-8c82-4f0d0b6e582d`
- Control ID: `CloudTrail.1`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|CloudTrail.1`
- Rollback command: `aws cloudtrail stop-logging --name 696505809372|eu-north-1|AWS::::Account:696505809372|CloudTrail.1`
