# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## GuardDuty should be enabled
- Action ID: `7555c02e-ed92-4674-b6f3-2b02b52150ee`
- Control ID: `GuardDuty.1`
- Target: `696505809372|us-east-1|AWS::::Account:696505809372|GuardDuty.1`
- Rollback command: `aws guardduty delete-detector --detector-id 696505809372|us-east-1|AWS::::Account:696505809372|GuardDuty.1`
