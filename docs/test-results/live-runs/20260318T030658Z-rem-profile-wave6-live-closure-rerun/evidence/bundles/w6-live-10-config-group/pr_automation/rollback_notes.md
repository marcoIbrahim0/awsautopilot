# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## AWS Config should be enabled and use the service-linked role for resource recording
- Action ID: `322fbb9e-09be-4f66-9859-0a94159a839b`
- Control ID: `Config.1`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|Config.1`
- Rollback command: `python3 ./executable/actions/01-aws-account-696505809372-322fbb9e/rollback/aws_config_restore.py`
