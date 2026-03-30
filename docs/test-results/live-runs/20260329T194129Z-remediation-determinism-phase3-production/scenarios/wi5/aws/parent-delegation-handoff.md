# WI-5 Parent Delegation Handoff

## Current State

- WI-5 action: `352ac9b2-d343-40ac-b427-4c4f285615ef`
- Run package: `20260329T194129Z-remediation-determinism-phase3-production`
- Bucket: `security-autopilot-w6-envready-s311-review-696505809372`
- Real delegated hostname for rerun: `wi5-gate3-696505809372.ocypheris.com`

## Canary Route53 Zone

- Hosted zone id: `Z081885955B6GUR4IL7E`
- Zone name: `wi5-gate3-696505809372.ocypheris.com`
- Route53 nameservers:
  - `ns-1780.awsdns-30.co.uk`
  - `ns-47.awsdns-05.com`
  - `ns-1270.awsdns-30.org`
  - `ns-1018.awsdns-63.net`

## ACM Certificate

- Certificate ARN: `arn:aws:acm:us-east-1:696505809372:certificate/509785ff-eef1-4071-bddc-d275f1dfa6ed`
- Region: `us-east-1`
- Type: `AMAZON_ISSUED`
- Status at capture time: `PENDING_VALIDATION`

The ACM validation CNAME has already been inserted into the Route53 hosted zone:

- Name: `_b1ce87aef1c13e39692e78e5918d8077.wi5-gate3-696505809372.ocypheris.com.`
- Type: `CNAME`
- Value: `_1d3156031ecd2e78d7a69bb88b75b7fe.jkddzztszm.acm-validations.aws.`

## Required Manual DNS Step

Add these `NS` records in the authoritative parent zone for `ocypheris.com` so the delegated subdomain becomes publicly authoritative:

- Record name: `wi5-gate3-696505809372.ocypheris.com`
- Record type: `NS`
- Values:
  - `ns-1780.awsdns-30.co.uk`
  - `ns-47.awsdns-05.com`
  - `ns-1270.awsdns-30.org`
  - `ns-1018.awsdns-63.net`

## After Delegation Propagates

1. Wait for ACM certificate `arn:aws:acm:us-east-1:696505809372:certificate/509785ff-eef1-4071-bddc-d275f1dfa6ed` to move to `ISSUED`.
2. Rerun WI-5 preview/create with:
   - `aliases=["wi5-gate3-696505809372.ocypheris.com"]`
   - `route53_hosted_zone_id="Z081885955B6GUR4IL7E"`
   - `acm_certificate_arn="arn:aws:acm:us-east-1:696505809372:certificate/509785ff-eef1-4071-bddc-d275f1dfa6ed"`
3. Continue the retained local Terraform proof from the existing package using the provider mirror workaround.

## Notes

- Do not reuse the earlier disposable `.net` alias, hosted zone `Z089211911JQN783YLH5I`, or imported certificate `arn:aws:acm:us-east-1:696505809372:certificate/e24f54d8-3a83-4de9-88d4-1dcc3cb9b8eb`.
- The current blocker is parent-zone delegation only. The canary-side Route53 zone and ACM request are already prepared.
