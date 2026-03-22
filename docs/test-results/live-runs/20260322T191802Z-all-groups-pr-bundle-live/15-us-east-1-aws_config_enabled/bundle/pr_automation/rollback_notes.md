# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## AWS Config should be enabled and use the service-linked role for resource recording
- Action ID: `202e02c7-f2c1-4c24-b81a-11168acad054`
- Control ID: `Config.1`
- Target: `696505809372|us-east-1|AWS::::Account:696505809372|Config.1`
- Rollback command: `aws configservice stop-configuration-recorder --configuration-recorder-name default`

## Synthetic Config finding with trusted threat intel
- Action ID: `73097c11-174c-4597-85a2-9af793842e8d`
- Control ID: `Config.1`
- Target: `696505809372|us-east-1|arn:aws:config:us-east-1:696505809372:config-rule/ocypheris-p2-config-fresh-kev|Config.1`
- Rollback command: `aws configservice stop-configuration-recorder --configuration-recorder-name default`

## Synthetic Config finding with low-confidence threat intel
- Action ID: `5acc7d0e-e361-474f-9efa-c200a0358f0d`
- Control ID: `Config.1`
- Target: `696505809372|us-east-1|arn:aws:config:us-east-1:696505809372:config-rule/ocypheris-p2-config-lowconf|Config.1`
- Rollback command: `aws configservice stop-configuration-recorder --configuration-recorder-name default`

## Synthetic Config finding without trusted threat intel
- Action ID: `a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1`
- Control ID: `Config.1`
- Target: `696505809372|us-east-1|arn:aws:config:us-east-1:696505809372:config-rule/ocypheris-p2-config-no-ti|Config.1`
- Rollback command: `aws configservice stop-configuration-recorder --configuration-recorder-name default`

## Synthetic Config finding with aged trusted threat intel
- Action ID: `18de803d-b7cd-4df8-ad30-1604dcb05cd5`
- Control ID: `Config.1`
- Target: `696505809372|us-east-1|arn:aws:config:us-east-1:696505809372:config-rule/ocypheris-p2-config-aged-kev|Config.1`
- Rollback command: `aws configservice stop-configuration-recorder --configuration-recorder-name default`
