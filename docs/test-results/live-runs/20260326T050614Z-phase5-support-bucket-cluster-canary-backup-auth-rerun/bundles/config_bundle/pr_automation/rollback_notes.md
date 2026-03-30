# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## AWS Config should be enabled and use the service-linked role for resource recording
- Action ID: `84f874b0-d2fd-405f-87fb-edc3264601a2`
- Control ID: `Config.1`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|Config.1`
- Rollback command: `python3 ./rollback/aws_config_restore.py`
