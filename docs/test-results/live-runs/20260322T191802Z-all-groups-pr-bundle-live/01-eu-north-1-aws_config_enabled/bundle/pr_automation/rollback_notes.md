# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## AWS Config should be enabled and use the service-linked role for resource recording
- Action ID: `7d51a23a-9af2-4a82-ae75-67561c01cf8e`
- Control ID: `Config.1`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|Config.1`
- Rollback command: `aws configservice stop-configuration-recorder --configuration-recorder-name default`
