AWS Security Autopilot — Group action artifact

Action: AWS Config should be enabled and use the service-linked role for resource recording
Action ID: 80499866-2447-4d0d-bcb4-88e903797ca1
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: config_enable_account_local_delivery
Profile: config_enable_account_local_delivery

Decision summary: Family resolver kept compatibility profile 'config_enable_account_local_delivery' executable for strategy 'config_enable_account_local_delivery'. Runtime AWS Config recorder evidence showed a selective/custom scope, so the resolver auto-promoted recording_scope to 'all_resources' for Config.1 compliance. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
