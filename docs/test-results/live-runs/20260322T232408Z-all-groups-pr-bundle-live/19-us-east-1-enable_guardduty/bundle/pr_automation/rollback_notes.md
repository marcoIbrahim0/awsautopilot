# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## GuardDuty should be enabled
- Action ID: `0b8c765a-62b0-4f80-8271-2bb1bbd4b353`
- Control ID: `GuardDuty.1`
- Target: `696505809372|us-east-1|AWS::::Account:696505809372|GuardDuty.1`
- Rollback command: `aws guardduty delete-detector --detector-id 696505809372|us-east-1|AWS::::Account:696505809372|GuardDuty.1`
