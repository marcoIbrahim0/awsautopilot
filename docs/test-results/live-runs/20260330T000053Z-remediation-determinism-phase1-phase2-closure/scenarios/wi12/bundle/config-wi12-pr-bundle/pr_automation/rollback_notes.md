# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## AWS Config should be enabled and use the service-linked role for resource recording
- Action ID: `80499866-2447-4d0d-bcb4-88e903797ca1`
- Control ID: `Config.1`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|Config.1`
- Rollback command: `python3 ./rollback/aws_config_restore.py`
