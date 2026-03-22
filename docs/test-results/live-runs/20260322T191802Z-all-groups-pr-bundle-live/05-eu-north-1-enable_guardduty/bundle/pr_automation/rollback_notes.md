# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## GuardDuty should be enabled
- Action ID: `bdc592bd-3165-4e28-9e48-0851fcd59c3d`
- Control ID: `GuardDuty.1`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|GuardDuty.1`
- Rollback command: `aws guardduty delete-detector --detector-id 696505809372|eu-north-1|AWS::::Account:696505809372|GuardDuty.1`
