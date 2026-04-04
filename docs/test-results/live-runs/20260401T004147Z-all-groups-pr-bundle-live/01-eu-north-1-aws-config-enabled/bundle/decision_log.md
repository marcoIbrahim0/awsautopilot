# Decision Log

## 1. AWS Config should be enabled and use the service-linked role for resource recording
- Action ID: 80499866-2447-4d0d-bcb4-88e903797ca1
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: config_enable_account_local_delivery / config_enable_account_local_delivery
- Summary: Family resolver kept compatibility profile 'config_enable_account_local_delivery' executable for strategy 'config_enable_account_local_delivery'. Runtime AWS Config recorder evidence showed a selective/custom scope, so the resolver auto-promoted recording_scope to 'all_resources' for Config.1 compliance. Run creation did not require additional risk-only acceptance.

