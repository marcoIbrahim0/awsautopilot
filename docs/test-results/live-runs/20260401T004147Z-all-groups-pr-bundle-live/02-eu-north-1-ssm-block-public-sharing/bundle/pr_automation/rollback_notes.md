# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## SSM documents should have the block public sharing setting enabled
- Action ID: `9444d745-69a6-49f2-9c39-43387ca52af4`
- Control ID: `SSM.7`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|SSM.7`
- Rollback command: `aws ssm update-service-setting --setting-id /ssm/documents/console/public-sharing-permission --setting-value Enable`
